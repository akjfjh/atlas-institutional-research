import json
import pytest
from atlas.analysis.event_study import study_events,similar_events,validate_event,timestamp_ms
from test_quant_indicators import candles,BASE,DAY


def event(index=10,**extra):
    ts=BASE+index*DAY+DAY//2
    return dict(event_id=f'e{index}',event_type='CPI',event_time=ts,publication_time=ts,first_available_time=ts,source='synthetic fixture',**extra)


def test_event_return_uses_next_tradable_open_after_publication():
    c=candles(80)
    result=study_events(c,[event()],horizons=(1,3))
    r=result['events'][0]
    assert r['entry_time']==BASE+11*DAY
    assert r['entry_price']==111
    assert r['windows']['1']['return']==pytest.approx(112/111-1)
    assert r['windows']['3']['return']==pytest.approx(114/111-1)
    assert r['event']['surprise'] is None
    assert not result['causal_estimate']
    json.dumps(result,allow_nan=False)


def test_future_vintage_and_bad_publication_are_rejected():
    e=event(); e['first_available_time']-=1
    with pytest.raises(ValueError,match='Lookahead'):validate_event(e)
    e=event(vintage_time=BASE+20*DAY)
    with pytest.raises(ValueError,match='leakage'):validate_event(e)
    result=study_events(candles(80),[e])
    assert not result['events'] and len(result['rejected_events'])==1


def test_unfinished_horizon_is_not_silently_shortened():
    result=study_events(candles(20),[event(15)],horizons=(1,30))
    assert result['events'][0]['windows']['30']['status']=='insufficient_future_history'
    assert result['summary']['30']['sample_count']==0


def test_event_before_price_history_rejected():
    result=study_events(candles(80),[event(-2)])
    assert not result['events']
    assert 'predates' in result['rejected_events'][0]['error']


def test_similar_events_never_select_by_favorable_outcome_or_future_cases():
    query=event(50,market_regime='trend')
    a=event(10,market_regime='trend',outcome=-.2)
    b=event(20,market_regime='trend',outcome=.3)
    result=similar_events(query,[a,b,event(60)],limit=10)
    assert len(result['cases'])==2
    assert not result['selection_uses_outcome']
    assert {x['event']['outcome'] for x in result['cases']}=={-.2,.3}


def test_release_time_timezone_required():
    with pytest.raises(ValueError,match='without release time'): timestamp_ms('2024-01-10')
    with pytest.raises(ValueError,match='timezone'): timestamp_ms('2024-01-10T13:30:00')
    assert timestamp_ms('2024-01-10T13:30:00Z')==1704893400000
