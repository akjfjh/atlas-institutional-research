"""Reproducible, next-open OHLCV research simulator (never places orders).

The ATLAS comparator is a fixed technical-filter proxy, not a historical
reconstruction of an LLM committee, macro releases or current news. The engine
models linear price exposure only; inverse/option contracts are unsupported.
"""
from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from .indicators import validate_candles, ema, rsi, atr, adx


def _percentile(values, p):
    if not values: return None
    s=sorted(values); x=(len(s)-1)*p; lo=int(x); hi=min(lo+1,len(s)-1)
    return s[lo]+(s[hi]-s[lo])*(x-lo)


def block_bootstrap_ci(values: Sequence[float], *, samples: int=500, block_size: int|None=None, seed: int=1729, confidence: float=0.95) -> dict:
    """Circular moving-block bootstrap for a mean; does not establish causation."""
    x=[float(v) for v in values]
    if not x or samples<1 or not 0<confidence<1 or any(not math.isfinite(v) for v in x):
        return {"low":None,"high":None,"n":len(x),"method":"circular_moving_block_bootstrap","reliable":False}
    block=block_size or max(1,round(len(x)**(1/3)))
    if block<1: raise ValueError("block_size must be positive")
    rng=random.Random(seed); means=[]
    for _ in range(samples):
        draw=[]
        while len(draw)<len(x):
            start=rng.randrange(len(x))
            draw.extend(x[(start+j)%len(x)] for j in range(block))
        means.append(statistics.mean(draw[:len(x)]))
    alpha=(1-confidence)/2
    return {"low":_percentile(means,alpha),"high":_percentile(means,1-alpha),"n":len(x),"samples":samples,"block_size":block,"confidence":confidence,"method":"circular_moving_block_bootstrap","reliable":len(x)>=30}


def metrics(equity_curve: list[dict], trades: list[dict], *, periods_per_year: float=365.25) -> dict:
    if not equity_curve:
        return {"trade_count":0,"net_return":0.0,"max_drawdown":0.0,"win_rate":None,"profit_factor":None,"sharpe_ratio":None,"sortino_ratio":None,"calmar_ratio":None,"costs":0.0,"average_pnl":None,"payoff_ratio":None,"expectancy":None}
    eq=[x["equity"] for x in equity_curve]
    ret=[eq[i]/eq[i-1]-1 if eq[i-1]>0 else -1.0 for i in range(1,len(eq))]
    peak=eq[0]; dd=0.0
    for value in eq:
        peak=max(peak,value)
        dd=max(dd,1-value/peak if peak else 0.0)
    pnls=[t["net_pnl"] for t in trades]
    winners=[v for v in pnls if v>0]; losers=[-v for v in pnls if v<0]
    avgwin=statistics.mean(winners) if winners else None
    avgloss=statistics.mean(losers) if losers else None
    std=statistics.stdev(ret) if len(ret)>1 else 0
    mean=statistics.mean(ret) if ret else 0
    downside=math.sqrt(statistics.mean([min(v,0)**2 for v in ret])) if ret else 0
    elapsed=max(1,equity_curve[-1]["ts"]-equity_curve[0]["ts"])
    years=elapsed/(365.25*86_400_000)
    total=eq[-1]/eq[0]-1 if eq[0]>0 else -1
    # Guard numeric overflow for short/high-return fixture intervals.
    log_growth=math.log(eq[-1]/eq[0])/years if eq[0]>0 and eq[-1]>0 else None
    annual=math.expm1(log_growth) if log_growth is not None and -700<log_growth<700 else None
    consecutive=maximum=0
    for value in pnls:
        consecutive=consecutive+1 if value<0 else 0; maximum=max(maximum,consecutive)
    cost=sum(t["total_cost"] for t in trades)
    return {"trade_count":len(trades),"net_return":total,"ending_equity":eq[-1],"max_drawdown":dd,"win_rate":len(winners)/len(trades) if trades else None,"average_win":avgwin,"average_loss":avgloss,"average_pnl":statistics.mean(pnls) if pnls else None,"payoff_ratio":avgwin/avgloss if avgwin is not None and avgloss else None,"expectancy":statistics.mean([t["r_multiple"] for t in trades]) if trades else None,"profit_factor":sum(winners)/sum(losers) if losers else None,"sharpe_ratio":mean/std*math.sqrt(periods_per_year) if std>0 else None,"sortino_ratio":mean/downside*math.sqrt(periods_per_year) if downside>0 else None,"calmar_ratio":annual/dd if annual is not None and dd>0 else None,"annualized_return":annual,"costs":cost,"max_consecutive_losses":maximum,"bar_returns":ret}


def _signals(candles, strategy, fast, slow):
    close=[c["close"] for c in candles]
    f,s=ema(close,fast),ema(close,slow)
    r=rsi(close); a=adx(candles)["adx"]; av=atr(candles)
    signals=[]
    for i,p in enumerate(close):
        direction=0
        if f[i] is not None and s[i] is not None and av[i] is not None:
            if strategy=="baseline":
                direction=1 if f[i]>s[i] else -1 if f[i]<s[i] else 0
            elif a[i] is not None and a[i]>=20 and r[i] is not None and av[i]/p<0.08:
                if p>f[i]>s[i] and 45<=r[i]<=75: direction=1
                elif p<f[i]<s[i] and 25<=r[i]<=55: direction=-1
        signals.append(direction)
    return signals,av


def _funding(events):
    result=[]
    for event in events or []:
        ts=event.get("ts",event.get("fundingTime",event.get("timestamp")))
        rate=event.get("rate",event.get("fundingRate"))
        if ts is None or rate is None: raise ValueError("Funding events require timestamp and rate")
        ts=int(ts); rate=float(rate)
        if not math.isfinite(rate) or abs(rate)>1: raise ValueError("Invalid funding rate")
        result.append((ts,rate))
    if len({t for t,_ in result})!=len(result): raise ValueError("Duplicate funding settlements")
    return sorted(result)


def _simulate(candles, signals, av, *, start, stop, fee_bps, slippage_bps, spread_bps, funding, risk_fraction, initial_capital, max_leverage, stop_atr, reward_risk):
    capital=initial_capital; pos=None; trades=[]; curve=[]; funding_used=set()
    cost_rate=(fee_bps+slippage_bps+spread_bps/2)/10000
    step=statistics.median([candles[i]["ts"]-candles[i-1]["ts"] for i in range(1,len(candles))]) if len(candles)>1 else 86_400_000
    def close_position(price, ts, reason):
        nonlocal capital,pos
        gross=pos["direction"]*pos["qty"]*(price-pos["entry_price"])
        exit_cost=abs(pos["qty"]*price)*cost_rate
        capital+=gross-exit_cost
        total_cost=pos["entry_cost"]+exit_cost+pos["funding_cost"]
        net=gross-total_cost
        trades.append({**pos,"exit_price":price,"exit_ts":int(ts),"exit_reason":reason,"gross_pnl":gross,"net_pnl":net,"exit_cost":exit_cost,"total_cost":total_cost,"r_multiple":net/pos["initial_risk"] if pos["initial_risk"]>0 else 0})
        pos=None
    first_ts=candles[start]["ts"] if start<len(candles) else 0
    curve.append({"ts":int(first_ts),"equity":capital})
    for i in range(start,stop):
        bar=candles[i]; end_ts=int(candles[i+1]["ts"] if i+1<len(candles) else bar.get("available_at",bar["ts"]+step))
        target=signals[i-1] if i>0 else 0
        if pos is not None and target!=pos["direction"]:
            close_position(bar["open"],bar["ts"],"signal_next_open")
        if pos is None and target and i>0 and av[i-1] is not None and capital>0:
            distance=max(av[i-1]*stop_atr,bar["open"]*0.005)
            qty=min(capital*risk_fraction/distance,capital*max_leverage/bar["open"])
            entry_cost=qty*bar["open"]*cost_rate
            if qty>0 and entry_cost<capital:
                pos={"direction":target,"qty":qty,"entry_price":bar["open"],"entry_ts":bar["ts"],"signal_ts":candles[i-1]["ts"],"signal_available_at":candles[i-1].get("available_at",bar["ts"]),"stop_price":bar["open"]-target*distance,"target_price":bar["open"]+target*distance*reward_risk,"initial_risk":qty*distance,"entry_cost":entry_cost,"funding_cost":0.0}
                capital-=entry_cost
        if pos is not None:
            # Funding charged/credited for positions already open strictly before settlement.
            # Intrabar stop time is unknown: all settlements through bar close are
            # conservatively included, with this approximation disclosed in output.
            for j,(ts,rate) in enumerate(funding):
                if j not in funding_used and pos["entry_ts"]<ts<=end_ts:
                    fc=pos["qty"]*bar["open"]*rate*pos["direction"]
                    pos["funding_cost"]+=fc; capital-=fc; funding_used.add(j)
            if pos["direction"]==1:
                hit_stop=bar["low"]<=pos["stop_price"]
                hit_target=bar["high"]>=pos["target_price"]
                if hit_stop: close_position(min(bar["open"],pos["stop_price"]),end_ts,"stop_conservative")
                elif hit_target: close_position(pos["target_price"],end_ts,"target")
            else:
                hit_stop=bar["high"]>=pos["stop_price"]
                hit_target=bar["low"]<=pos["target_price"]
                if hit_stop: close_position(max(bar["open"],pos["stop_price"]),end_ts,"stop_conservative")
                elif hit_target: close_position(pos["target_price"],end_ts,"target")
        equity=capital+(pos["direction"]*pos["qty"]*(bar["close"]-pos["entry_price"]) if pos else 0)
        curve.append({"ts":end_ts,"equity":equity})
        if equity<=0:
            if pos: close_position(bar["close"],end_ts,"insolvent")
            curve[-1]["equity"]=capital
            break
    if pos is not None:
        last=candles[min(stop,len(candles))-1]
        close_position(last["close"],curve[-1]["ts"],"end_of_sample")
        curve[-1]["equity"]=capital
    periods=365.25*86_400_000/step
    return {"metrics":metrics(curve,trades,periods_per_year=periods),"trades":trades,"equity_curve":curve}


def run_backtest(candles, strategy="baseline", fee_bps=10, slippage_bps=5, spread_bps=2, funding_events=None, risk_fraction=0.01, train_fraction=0.6, **kwargs):
    c=validate_candles(candles,min_count=3)
    intervals=[c[i]["ts"]-c[i-1]["ts"] for i in range(1,len(c))]
    typical_step=statistics.median(intervals)
    if len(c)>3 and any(step>1.5*typical_step for step in intervals):
        raise ValueError("Missing candle periods: backtest cannot infer intragap stops or fills")
    if strategy not in {"baseline","atlas"}: raise ValueError("Unknown strategy")
    if not 0<train_fraction<1 or not 0<risk_fraction<=1: raise ValueError("Invalid risk/split fraction")
    for value in (fee_bps,slippage_bps,spread_bps):
        if not math.isfinite(value) or value<0: raise ValueError("Costs must be finite and nonnegative")
    allowed={"fast","slow","initial_capital","max_leverage","stop_atr","reward_risk","bootstrap_samples","walk_forward_splits","include_sensitivity","instrument_type","allow_short"}
    unknown=set(kwargs)-allowed
    if unknown: raise ValueError(f"Unsupported backtest parameter(s): {sorted(unknown)}")
    fast=int(kwargs.get("fast",20)); slow=int(kwargs.get("slow",50))
    if fast<2 or slow<=fast: raise ValueError("Require 2 <= fast < slow")
    initial=float(kwargs.get("initial_capital",10_000)); leverage=float(kwargs.get("max_leverage",1.0))
    stop_atr=float(kwargs.get("stop_atr",2.0)); rr=float(kwargs.get("reward_risk",2.0))
    if not all(math.isfinite(v) and v>0 for v in (initial,leverage,stop_atr,rr)) or leverage>10:
        raise ValueError("Invalid capital, leverage, stop or reward/risk")
    fund=_funding(funding_events)
    instrument_type=str(kwargs.get("instrument_type","LINEAR")).upper()
    if instrument_type not in {"LINEAR","SPOT","SWAP","FUTURES"}: raise ValueError("Unsupported instrument type: linear, spot, swap or futures only")
    allow_short=bool(kwargs.get("allow_short",instrument_type!="SPOT"))
    if instrument_type=="SPOT" and allow_short: raise ValueError("Spot shorting requires borrowing, which this engine does not model")
    signals,av=_signals(c,strategy,fast,slow)
    if not allow_short: signals=[max(0,x) for x in signals]
    params=dict(fee_bps=fee_bps,slippage_bps=slippage_bps,spread_bps=spread_bps,funding=fund,risk_fraction=risk_fraction,initial_capital=initial,max_leverage=leverage,stop_atr=stop_atr,reward_risk=rr)
    split=max(1,min(len(c)-1,int(len(c)*train_fraction)))
    result=_simulate(c,signals,av,start=0,stop=len(c),**params)
    ins=_simulate(c,signals,av,start=0,stop=split,**params)
    oos=_simulate(c,signals,av,start=split,stop=len(c),**params)
    windows=[]; count=max(1,min(10,int(kwargs.get("walk_forward_splits",3))))
    remaining=len(c)-split
    for j in range(count):
        start=split+remaining*j//count; end=split+remaining*(j+1)//count
        if end<=start: continue
        run=_simulate(c,signals,av,start=start,stop=end,**params)
        windows.append({"start_ts":c[start]["ts"],"end_ts":c[end-1]["ts"],"training_end_ts":c[start-1]["ts"] if start else None,"parameters_fixed_in_advance":True,"metrics":run["metrics"]})
    nboot=int(kwargs.get("bootstrap_samples",500))
    ci=block_bootstrap_ci(oos["metrics"].get("bar_returns",[]),samples=nboot)
    warnings=[]
    if len(c)<max(slow+30,200): warnings.append("Short history: cannot characterize multiple market regimes reliably")
    if oos["metrics"]["trade_count"]<30: warnings.append("Fewer than 30 out-of-sample closed trades; statistical estimates are unreliable")
    if not fund and instrument_type!="SPOT": warnings.append("Funding settlements not supplied; perpetual results exclude funding and are incomplete")
    if instrument_type=="LINEAR": warnings.append("Instrument type unspecified: generic linear long/short exposure; not a physical spot short/borrow simulation")
    if fund: warnings.append("Funding at intrabar exits is approximated using settlements through that bar close; use finer bars for exact timing")
    if leverage>1: warnings.append("Linear leveraged exposure only: no exchange maintenance margin or liquidation simulation; not validated for levered deployment")
    sensitivity=[]
    if kwargs.get("include_sensitivity",True):
        for factor in (0.5,1.5):
            p={**params,"fee_bps":fee_bps*factor,"slippage_bps":slippage_bps*factor,"spread_bps":spread_bps*factor}
            sim=_simulate(c,signals,av,start=split,stop=len(c),**p)
            sensitivity.append({"kind":"cost_multiplier","value":factor,"metrics":sim["metrics"]})
        for factor in (0.75,1.25):
            sim=_simulate(c,signals,av,start=split,stop=len(c),**{**params,"stop_atr":stop_atr*factor})
            sensitivity.append({"kind":"stop_atr_multiplier","value":factor,"metrics":sim["metrics"]})
    result.update({"strategy":strategy,"strategy_version":"0.1.0-fixed","strategy_label":"ATLAS fixed technical-filter proxy, not full historical committee" if strategy=="atlas" else "EMA trend baseline","price_model":"linear_exposure_only","instrument_type":instrument_type,"bars":len(c),"split_index":split,"in_sample":ins["metrics"],"out_of_sample":oos["metrics"],"walk_forward":windows,"confidence_intervals":{"out_of_sample_mean_bar_return":ci},"sensitivity":sensitivity,"warnings":warnings,"execution_assumptions":{"signal":"confirmed close t","fill":"next bar open t+1","same_bar_stop_target":"stop first, gap stop filled at worse opening price","fees_bps_each_side":fee_bps,"slippage_bps_each_side":slippage_bps,"full_spread_bps":spread_bps,"risk_fraction":risk_fraction,"max_leverage":leverage,"allow_short":allow_short,"initial_capital":initial,"stop_atr":stop_atr,"reward_risk":rr,"train_fraction":train_fraction,"parameter_optimization":False,"funding_events":len(fund),"probability_calibrated":False,"risk_free_return":0.0,"periods_per_year_method":"365.25 days / median observed bar duration"},"sample_kind":"historical_backtest","real_trading_win_rate":None})
    return result


def compare_strategies(candles, **kwargs):
    base=run_backtest(candles,strategy="baseline",**kwargs)
    atlas=run_backtest(candles,strategy="atlas",**kwargs)
    a=atlas["out_of_sample"]["bar_returns"]; b=base["out_of_sample"]["bar_returns"]
    differences=[x-y for x,y in zip(a,b)]
    ci=block_bootstrap_ci(differences,samples=int(kwargs.get("bootstrap_samples",500)))
    positive=bool(ci["reliable"] and ci["low"] is not None and ci["low"]>0 and atlas["out_of_sample"]["trade_count"]>=30 and base["out_of_sample"]["trade_count"]>=30)
    return {"baseline":base,"atlas":atlas,"comparison":{"same_costs_risk_capital_period":True,"paired_oos_mean_return_difference_ci":ci,"statistically_credible_improvement":positive,"interpretation":"Exploratory unadjusted comparison of pre-defined technical rules; no full ATLAS edge established. No selection of favorable runs.","multiple_testing_adjusted":False,"full_committee_historical_replay":False},"warnings":["The ATLAS comparator is a technical-filter proxy. Historical macro/news/Fed point-in-time signals are not reconstructed.","Confidence interval excludes neither strategy selection bias nor changes in market structure."]}
