"""Independent accounting and time-alignment tests on synthetic data."""
import json
import math
import pytest
from atlas.analysis.backtesting import run_backtest,compare_strategies,block_bootstrap_ci,_simulate
from test_quant_indicators import candles,BASE,DAY


def test_costs_reduce_equity_and_next_open_enforced():
    c=candles(260)
    free=run_backtest(c,fee_bps=0,slippage_bps=0,spread_bps=0,bootstrap_samples=50)
    cost=run_backtest(c,fee_bps=20,slippage_bps=10,spread_bps=4,bootstrap_samples=50)
    assert free['metrics']['trade_count']>0
    assert cost['metrics']['net_return']<free['metrics']['net_return']
    for trade in cost['trades']:
        assert trade['entry_ts']>trade['signal_ts']
        assert trade['signal_available_at']<=trade['entry_ts']
    json.dumps(cost,allow_nan=False)


def test_manual_stop_accounting_when_both_stop_and_target_hit():
    c=candles(2,lambda i:100)
    c[1].update(high=109,low=95)
    result=_simulate(c,[1,1],[2,2],start=0,stop=2,fee_bps=0,slippage_bps=0,spread_bps=0,funding=[],risk_fraction=.01,initial_capital=10000,max_leverage=1,stop_atr=2,reward_risk=2)
    trade=result['trades'][0]
    assert trade['qty']==25
    assert trade['exit_price']==96
    assert trade['net_pnl']==-100
    assert trade['r_multiple']==-1
    assert result['metrics']['ending_equity']==9900


def test_gap_stop_is_filled_at_worse_open_and_fees_exact():
    c=candles(3,lambda i:100)
    c[2].update(open=90,high=91,low=89,close=90)
    result=_simulate(c,[1,1,1],[2,2,2],start=0,stop=3,fee_bps=10,slippage_bps=0,spread_bps=0,funding=[],risk_fraction=.01,initial_capital=10000,max_leverage=1,stop_atr=2,reward_risk=2)
    trade=result['trades'][0]
    assert trade['exit_price']==90
    assert trade['net_pnl']==pytest.approx(-250-2.5-2.25)
    assert result['metrics']['ending_equity']==pytest.approx(9745.25)


def test_funding_cost_is_not_omitted_when_supplied():
    c=candles(260)
    free=run_backtest(c,fee_bps=0,slippage_bps=0,spread_bps=0,bootstrap_samples=20)
    funded=run_backtest(c,fee_bps=0,slippage_bps=0,spread_bps=0,funding_events=[{'ts':x['ts'],'rate':0.001} for x in c[50:]],bootstrap_samples=20)
    assert funded['metrics']['ending_equity']<free['metrics']['ending_equity']
    assert sum(t['funding_cost'] for t in funded['trades'])>0


def test_candle_availability_detects_future_data_leakage():
    c=candles(100); c[60]['available_at']=c[61]['ts']+1
    with pytest.raises(ValueError,match='Lookahead'):run_backtest(c)


def test_chronological_oos_windows_do_not_overlap_training():
    result=run_backtest(candles(320,lambda i:100+i/2+2*math.sin(i/4)),bootstrap_samples=50)
    for w in result['walk_forward']:
        assert w['training_end_ts']<w['start_ts']<=w['end_ts']
        assert w['parameters_fixed_in_advance']
    assert result['split_index']==192
    assert result['sample_kind']=='historical_backtest'
    assert result['real_trading_win_rate'] is None


def test_prefix_signals_unchanged_by_future_market_path():
    prefix=candles(180,lambda i:100+0.3*i+2*math.sin(i/7))
    extra=candles(240,lambda i:100+0.3*i+2*math.sin(i/7))
    for row in extra[180:]:
        row.update(open=500,high=501,low=499,close=500)
    short=run_backtest(prefix,bootstrap_samples=10)
    long=run_backtest(extra,bootstrap_samples=10)
    cutoff=prefix[-1]['ts']
    early=lambda r:[(t['entry_ts'],t['entry_price'],t['direction']) for t in r['trades'] if t['entry_ts']<cutoff]
    assert early(short)==early(long)


def test_small_sample_bootstrap_and_comparison_do_not_claim_edge():
    ci=block_bootstrap_ci([.1]*10,samples=50)
    assert ci['low']==pytest.approx(.1)
    assert not ci['reliable']
    result=compare_strategies(candles(100),bootstrap_samples=30)
    assert not result['comparison']['statistically_credible_improvement']
    assert not result['comparison']['full_committee_historical_replay']
    json.dumps(result,allow_nan=False)


def test_invalid_configuration_rejected():
    for kwargs in ({'risk_fraction':2},{'fee_bps':-1},{'slow':5,'fast':10},{'max_leverage':100},{'random_magic':1}):
        with pytest.raises(ValueError):run_backtest(candles(100),**kwargs)


def test_spot_shorting_not_silently_simulated():
    falling=candles(160,lambda i:300-i)
    spot=run_backtest(falling,instrument_type='SPOT',bootstrap_samples=10)
    assert not spot['trades']
    assert not any('Funding settlements not supplied' in w for w in spot['warnings'])
    with pytest.raises(ValueError,match='borrowing'): run_backtest(falling,instrument_type='SPOT',allow_short=True)


def test_missing_candle_periods_block_backtest_fills():
    c=candles(100)
    del c[70]
    # Keep the previous completed bar's real availability; it still predates
    # the next observed opening, but the gap path cannot be reconstructed.
    with pytest.raises(ValueError,match='Missing candle periods'): run_backtest(c)
