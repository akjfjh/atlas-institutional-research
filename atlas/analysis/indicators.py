"""Causal technical indicators on closed, oldest-first OHLCV bars.

Formulas use arithmetic seed for EMA, Wilder smoothing for ATR/RSI/ADX,
population standard deviation for bands, and 365.25-day annualization for crypto.
Warm-up values are None; insufficient history is never padded with invented bars.
Primary formula references (consulted 2026-10-26):
https://github.com/TA-Lib/ta-lib/tree/main/src/ta_func
Implementations are original Python. EMA arithmetic seed, OBV zero offset, KDJ
50/50 recursive seed and SuperTrend initial up direction are explicit conventions;
bit-for-bit equivalence to exchange/TA-Lib indicator seeds is not claimed.
"""
from __future__ import annotations

import math
import statistics
from typing import Sequence


def validate_candles(candles: Sequence[dict], *, min_count: int = 1) -> list[dict]:
    if len(candles) < min_count:
        raise ValueError(f"At least {min_count} closed candles required")
    times = [int(c["ts"]) for c in candles]
    if any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError("Candle timestamps must be unique and strictly increasing")
    out = []
    previous = -1
    for i, c in enumerate(candles):
        if not isinstance(c, dict):
            raise ValueError("Candle must be an object")
        ts = int(c["ts"])
        if ts <= previous:
            raise ValueError("Candle timestamps must be unique and strictly increasing")
        if c.get("confirm") is not True:
            raise ValueError("Unclosed candles cannot be used for confirmed analysis")
        row = {"ts": ts, "confirm": True}
        for key in ("open", "high", "low", "close", "volume"):
            v = float(c[key])
            if not math.isfinite(v) or v < 0 or (key != "volume" and v <= 0):
                raise ValueError(f"Invalid {key} at candle {i}")
            row[key] = v
        if row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(row["open"], row["close"]):
            raise ValueError(f"Inconsistent OHLC at candle {i}")
        if "available_at" in c:
            row["available_at"] = int(c["available_at"])
            if row["available_at"] < ts:
                raise ValueError("Candle availability predates its opening")
            if i + 1 < len(candles) and row["available_at"] > int(candles[i+1]["ts"]):
                raise ValueError("Lookahead: candle not available before next-bar execution")
        out.append(row)
        previous = ts
    return out


def sma(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= period:
            total -= values[i-period]
        if i >= period-1:
            result[i] = total / period
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period-1] = current
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        current += alpha * (values[i] - current)
        result[i] = current
    return result


def wilder(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period < 1:
        raise ValueError("period must be positive")
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period-1] = current
    for i in range(period, len(values)):
        current = (current * (period-1) + values[i]) / period
        result[i] = current
    return result


def true_range(candles: Sequence[dict]) -> list[float]:
    return [c["high"] - c["low"] if i == 0 else max(c["high"]-c["low"], abs(c["high"]-candles[i-1]["close"]), abs(c["low"]-candles[i-1]["close"])) for i, c in enumerate(candles)]


def atr(candles: Sequence[dict], period: int = 14) -> list[float | None]:
    # First bar has no previous close and is excluded from the Wilder seed.
    tr = true_range(candles)
    return [None] + wilder(tr[1:], period) if tr else []


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    if not values:
        return []
    changes = [values[i]-values[i-1] for i in range(1, len(values))]
    up = wilder([max(v, 0) for v in changes], period)
    down = wilder([max(-v, 0) for v in changes], period)
    result: list[float | None] = [None]
    for u, d in zip(up, down):
        if u is None or d is None:
            result.append(None)
        elif u == 0 and d == 0:
            result.append(50.0)
        elif d == 0:
            result.append(100.0)
        else:
            result.append(100 - 100 / (1 + u/d))
    return result


def macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    f, s = ema(values, fast), ema(values, slow)
    line = [None if a is None or b is None else a-b for a, b in zip(f, s)]
    valid = [v for v in line if v is not None]
    sig = [None] * (len(line)-len(valid)) + ema(valid, signal)
    return {"macd": line, "signal": sig, "histogram": [None if a is None or b is None else a-b for a,b in zip(line,sig)]}


def adx(candles: Sequence[dict], period: int = 14) -> dict:
    n = len(candles)
    if n == 0:
        return {"adx": [], "plus_di": [], "minus_di": []}
    up, down, trs = [], [], []
    for i in range(1, n):
        u = candles[i]["high"]-candles[i-1]["high"]
        d = candles[i-1]["low"]-candles[i]["low"]
        up.append(u if u > d and u > 0 else 0.0)
        down.append(d if d > u and d > 0 else 0.0)
        trs.append(true_range(candles[i-1:i+1])[-1])
    au, ad, at = wilder(up,period), wilder(down,period), wilder(trs,period)
    pdi, mdi, dx = [None], [None], [None]
    for u,d,t in zip(au,ad,at):
        if t is None:
            pdi.append(None); mdi.append(None); dx.append(None)
        else:
            p = 100*u/t if t else 0.0
            m = 100*d/t if t else 0.0
            pdi.append(p); mdi.append(m)
            dx.append(100*abs(p-m)/(p+m) if p+m else 0.0)
    valid = [v for v in dx if v is not None]
    return {"adx": [None]*(n-len(valid))+wilder(valid,period), "plus_di": pdi, "minus_di": mdi}


def stochastic(candles: Sequence[dict], period: int = 14, smooth: int = 3) -> dict:
    k = [None] * len(candles)
    for i in range(period-1,len(candles)):
        window = candles[i-period+1:i+1]
        lo, hi = min(c["low"] for c in window), max(c["high"] for c in window)
        k[i] = 100*(candles[i]["close"]-lo)/(hi-lo) if hi != lo else 50.0
    valid = [v for v in k if v is not None]
    d = [None]*(len(k)-len(valid))+sma(valid,smooth)
    return {"k": k, "d": d, "j": [None if a is None or b is None else 3*a-2*b for a,b in zip(k,d)]}


def kdj(candles: Sequence[dict], period: int = 9, smooth_k: int = 3, smooth_d: int = 3) -> dict:
    """RSV, then recursive Chinese KDJ smoothing; K/D seeds are 50."""
    if smooth_k < 1 or smooth_d < 1: raise ValueError("KDJ smoothing must be positive")
    raw = stochastic(candles, period)["k"]
    ks, ds, js = [None]*len(candles), [None]*len(candles), [None]*len(candles)
    previous_k = previous_d = 50.0
    for i, value in enumerate(raw):
        if value is None: continue
        previous_k = ((smooth_k-1)*previous_k+value)/smooth_k
        previous_d = ((smooth_d-1)*previous_d+previous_k)/smooth_d
        ks[i],ds[i],js[i] = previous_k,previous_d,3*previous_k-2*previous_d
    return {"k":ks,"d":ds,"j":js}


def stochastic_rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    rs = rsi(values, period)
    out = [None] * len(values)
    for i in range(2*period-1,len(values)):
        w = rs[i-period+1:i+1]
        if all(v is not None for v in w):
            lo,hi = min(w),max(w)
            out[i] = 100*(rs[i]-lo)/(hi-lo) if hi != lo else 50.0
    return out


def supertrend(candles: Sequence[dict], period: int = 10, multiplier: float = 3.0) -> dict:
    av = atr(candles,period)
    bands, directions = [None]*len(candles), [None]*len(candles)
    fu=fl=None
    direction=1
    for i,c in enumerate(candles):
        if av[i] is None: continue
        mid=(c["high"]+c["low"])/2
        bu,bl=mid+multiplier*av[i],mid-multiplier*av[i]
        if fu is None:
            fu,fl=bu,bl
        else:
            old_fu,old_fl=fu,fl
            fu=bu if bu<old_fu or candles[i-1]["close"]>old_fu else old_fu
            fl=bl if bl>old_fl or candles[i-1]["close"]<old_fl else old_fl
            if direction < 0 and c["close"] > old_fu: direction=1
            elif direction > 0 and c["close"] < old_fl: direction=-1
        directions[i]=direction
        bands[i]=fl if direction>0 else fu
    return {"value":bands,"direction":directions}


def ichimoku(candles: Sequence[dict]) -> dict:
    def midpoint(period):
        out=[None]*len(candles)
        for i in range(period-1,len(candles)):
            w=candles[i-period+1:i+1]
            out[i]=(max(c["high"] for c in w)+min(c["low"] for c in w))/2
        return out
    tenkan,kijun,span_b_raw=midpoint(9),midpoint(26),midpoint(52)
    span_a_raw=[None if a is None or b is None else (a+b)/2 for a,b in zip(tenkan,kijun)]
    # The cloud visible at t was calculated at t-26, never at t+26.
    n=len(candles)
    shift=lambda a: ([None]*26+a)[:n]
    return {"tenkan":tenkan,"kijun":kijun,"span_a":shift(span_a_raw),"span_b":shift(span_b_raw)}


def bollinger(values: Sequence[float], period: int = 20, deviations: float = 2.0) -> dict:
    middle=sma(values,period)
    upper,lower=[None]*len(values),[None]*len(values)
    for i in range(period-1,len(values)):
        std=statistics.pstdev(values[i-period+1:i+1])
        upper[i]=middle[i]+deviations*std
        lower[i]=middle[i]-deviations*std
    return {"middle":middle,"upper":upper,"lower":lower}


def obv(candles: Sequence[dict]) -> list[float]:
    out=[]; total=0.0
    for i,c in enumerate(candles):
        if i: total += c["volume"]*(1 if c["close"]>candles[i-1]["close"] else -1 if c["close"]<candles[i-1]["close"] else 0)
        out.append(total)
    return out


def mfi(candles: Sequence[dict],period: int=14) -> list[float | None]:
    typical=[(c["high"]+c["low"]+c["close"])/3 for c in candles]
    pos,neg=[0.0],[0.0]
    for i in range(1,len(candles)):
        flow=typical[i]*candles[i]["volume"]
        pos.append(flow if typical[i]>typical[i-1] else 0.0)
        neg.append(flow if typical[i]<typical[i-1] else 0.0)
    out=[None]*len(candles)
    for i in range(period,len(candles)):
        p,n=sum(pos[i-period+1:i+1]),sum(neg[i-period+1:i+1])
        out[i]=100-100/(1+p/n) if n else 100.0 if p else 50.0
    return out


def rolling_vwap(candles: Sequence[dict],period: int=20) -> list[float | None]:
    out=[None]*len(candles)
    for i in range(period-1,len(candles)):
        w=candles[i-period+1:i+1]; volume=sum(c["volume"] for c in w)
        out[i]=sum((c["high"]+c["low"]+c["close"])/3*c["volume"] for c in w)/volume if volume else None
    return out


def historical_volatility(values: Sequence[float], period: int=20, periods_per_year: float=365.25) -> list[float | None]:
    out=[None]*len(values)
    rets=[math.log(values[i]/values[i-1]) for i in range(1,len(values))]
    for i in range(period,len(values)):
        out[i]=statistics.stdev(rets[i-period:i])*math.sqrt(periods_per_year)
    return out


def feature_series(candles: Sequence[dict]) -> dict:
    c=validate_candles(candles)
    close=[v["close"] for v in c]
    step=statistics.median([c[i]["ts"]-c[i-1]["ts"] for i in range(1,len(c))]) if len(c)>1 else 86_400_000
    annual=365.25*86_400_000/step
    return {"sma20":sma(close,20),"ema20":ema(close,20),"ema50":ema(close,50),"ema200":ema(close,200),"rsi14":rsi(close),"macd":macd(close),"adx":adx(c),"atr14":atr(c),"stoch_rsi14":stochastic_rsi(close),"kdj":kdj(c,9,3,3),"supertrend":supertrend(c),"ichimoku":ichimoku(c),"bollinger":bollinger(close),"obv":obv(c),"mfi14":mfi(c),"vwap20":rolling_vwap(c),"historical_volatility20":historical_volatility(close,20,annual),"roc12":[None if i<12 else 100*(p/close[i-12]-1) for i,p in enumerate(close)]}


def analyze(candles: Sequence[dict]) -> dict:
    if not candles:
        return {"metrics":{},"trend":"neutral","regime":"unknown","support":None,"resistance":None,"flags":["insufficient_history"],"candle_count":0,"as_of":None}
    c=validate_candles(candles)
    f=feature_series(c); last=c[-1]; flags=[]
    def tail(v): return v[-1] if v else None
    metrics={}
    for name,v in f.items():
        if isinstance(v,dict):
            metrics[name]={k:tail(a) for k,a in v.items()}
        else: metrics[name]=tail(v)
    metrics["close"]=last["close"]
    metrics["volume_change20"]=last["volume"]/(sum(x["volume"] for x in c[-21:-1])/20)-1 if len(c)>=21 and sum(x["volume"] for x in c[-21:-1]) else None
    e20,e50=metrics["ema20"],metrics["ema50"]
    trend="bullish" if e20 is not None and e50 is not None and last["close"]>e20>e50 else "bearish" if e20 is not None and e50 is not None and last["close"]<e20<e50 else "neutral"
    av=metrics["atr14"]
    strength=metrics["adx"]["adx"]
    regime="high_volatility" if av is not None and av/last["close"]>0.08 else "trending" if strength is not None and strength>=25 else "range" if strength is not None else "unknown"
    intervals=[c[i]["ts"]-c[i-1]["ts"] for i in range(1,len(c))]
    if len(intervals)>2 and any(v>1.5*statistics.median(intervals) for v in intervals): flags.append("candle_gaps_present")
    if len(c)<50: flags.append("insufficient_history_for_ema50")
    if len(c)<200: flags.append("insufficient_history_for_ema200")
    if len(c)<78: flags.append("insufficient_history_for_displaced_ichimoku_cloud")
    # Prior bars only: current high/low must not define its own breakout threshold.
    structure=c[-21:-1] if len(c)>1 else c
    support=min(x["low"] for x in structure)
    resistance=max(x["high"] for x in structure)
    metrics["breakout"]= "above_resistance" if last["close"]>resistance else "below_support" if last["close"]<support else "inside_range"
    return {"metrics":metrics,"trend":trend,"regime":regime,"support":support,"resistance":resistance,"flags":flags,"candle_count":len(c),"as_of":last.get("available_at",last["ts"]),"price_basis":"input_instrument_closed_candles","signal_is_probability":False}
