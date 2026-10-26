"""Explicitly synthetic closed-bar tests; not live market validation."""
import json
import math
import pytest
from atlas.analysis.indicators import (sma,ema,rsi,atr,adx,ichimoku,obv,mfi,bollinger,analyze,feature_series,validate_candles,kdj,rolling_vwap,historical_volatility,supertrend)

BASE=1_577_836_800_000
DAY=86_400_000

def candles(n=260, fn=lambda i:100+i):
    rows=[]
    for i in range(n):
        p=fn(i)
        rows.append(dict(ts=BASE+i*DAY,open=p,high=p+1,low=p-1,close=p,volume=10+i,confirm=True,available_at=BASE+(i+1)*DAY))
    return rows


def test_sma_ema_arithmetic_seed_and_recursive_update():
    assert sma([1,2,3,4],3)==[None,None,2,3]
    assert ema([1,2,3,4],3)==[None,None,2,3]
    assert ema([2,4,6,10],3)[-1]==7


def test_rsi_wilder_reference_and_flat_series():
    prices=[44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28]
    assert rsi(prices)[14]==pytest.approx(70.4641350211)
    assert rsi([5]*20)[-1]==50
    assert rsi(list(range(1,21)))[-1]==100


def test_atr_hand_computed_gap_true_range():
    c=candles(4)
    c[0].update(open=10,high=11,low=9,close=10)
    c[1].update(open=13,high=14,low=12,close=13)
    c[2].update(open=13,high=14,low=12,close=13)
    c[3].update(open=14,high=15,low=13,close=14)
    assert atr(c,2)==[None,None,3,2.5]


def test_adx_monotonic_trend_and_warmup():
    out=adx(candles(60),14)
    assert all(x is None for x in out['adx'][:27])
    assert out['adx'][-1]==pytest.approx(100)
    assert out['minus_di'][-1]==0


def test_ichimoku_visible_cloud_is_shifted_from_past():
    c=candles(100)
    out=ichimoku(c)
    assert out['span_b'][76] is None
    assert out['span_b'][77]==(c[51]['high']+c[0]['low'])/2
    future=c+[dict(c[-1],ts=c[-1]['ts']+DAY,available_at=c[-1]['available_at']+DAY,high=10001,low=9999,open=10000,close=10000)]
    assert ichimoku(future)['span_b'][:100]==out['span_b']


def test_obv_mfi_and_population_bands():
    c=candles(30)
    assert obv(c)[2]==c[1]['volume']+c[2]['volume']
    assert mfi(c)[-1]==100
    b=bollinger([1,2,3],3)
    assert b['middle'][-1]==2
    assert b['upper'][-1]==pytest.approx(2+2*math.sqrt(2/3))


def test_analysis_short_history_does_not_fake_long_term_values():
    result=analyze(candles(20))
    assert result['metrics']['ema200'] is None
    assert 'insufficient_history_for_ema200' in result['flags']
    json.dumps(result,allow_nan=False)


def test_all_features_are_causal_prefix_invariant():
    c=candles(300,lambda i:100+0.1*i+3*math.sin(i/9))
    before=feature_series(c[:230]); after=feature_series(c)
    for name,arr in before.items():
        if isinstance(arr,dict):
            for sub,values in arr.items(): assert after[name][sub][:230]==values
        else: assert after[name][:230]==arr


def test_invalid_data_rejected():
    c=candles(3)
    with pytest.raises(ValueError,match='unique'): validate_candles(c+[c[-1]])
    c[1]['confirm']=False
    with pytest.raises(ValueError,match='Unclosed'): validate_candles(c)
    c[1]['confirm']=True; c[1]['available_at']=c[2]['ts']+1
    with pytest.raises(ValueError,match='Lookahead'): validate_candles(c)


def test_kdj_recursive_smoothing_and_rolling_vwap():
    c=candles(10,lambda i:10+i)
    result=kdj(c,9)
    rsv=100*(18-9)/(19-9)
    k=(100+rsv)/3
    d=(100+k)/3
    assert result['k'][8]==pytest.approx(k)
    assert result['d'][8]==pytest.approx(d)
    assert result['j'][8]==pytest.approx(3*k-2*d)
    c=candles(2,lambda i:10+2*i)
    assert rolling_vwap(c,2)[-1]==pytest.approx((10*10+12*11)/21)


def test_supertrend_and_log_volatility_numeric_behavior():
    c=candles(50)
    result=supertrend(c)
    assert result['direction'][-1]==1
    assert result['value'][-1]<c[-1]['close']
    values=[10*math.exp(i*.01) for i in range(30)]
    assert historical_volatility(values)[-1]==pytest.approx(0,abs=1e-14)
