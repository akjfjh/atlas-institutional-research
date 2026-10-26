"""High-leverage research must not turn a stale or partial signal into an order."""
from __future__ import annotations

from datetime import datetime,timezone
import pytest

from atlas.analysis.entry_timing import study
from atlas.config import Config
from atlas.core.coordinator import Coordinator
from atlas.core.state import ResearchState,now
from atlas.analysis.risk import final_decision
from atlas.reporting.reports import render_markdown


def periods():
    timestamp=int(datetime.now(timezone.utc).timestamp()*1000)-60_000
    return {'15m':{'trend':'bullish','support':100,'resistance':102,'as_of':timestamp,
                   'metrics':{'rsi14':58,'volume_change20':.3,'atr14':.4}},
            '1H':{'trend':'bullish','as_of':timestamp,'metrics':{'adx':{'adx':28}}}}


def snapshot(age=0,mode='live'):
    now=datetime.now(timezone.utc)
    return {'mode':mode,'retrieved_at':now.isoformat(),
            'ticker':{'last':102,'ts':int(now.timestamp()*1000)-age*1000}}


def test_1u_study_has_two_confirmed_periods_and_never_authorizes_execution():
    candidate=study(periods(),snapshot(),simulation=True)
    assert candidate['direction']=='LONG_WATCH' and candidate['alert']
    assert candidate['entry_reference']>102 and candidate['invalidation']<100
    assert candidate['executable'] is False and candidate['order_execution']=='disabled'
    sim=candidate['one_usdt_simulation']
    assert sim['margin_usdt']==1 and sim['notional_usdt']==[50,100]
    assert sim['liquidation_price'] is None and sim['execution_allowed'] is False
    assert sim['round_trip_fee_slippage_usdt'][1]>0


def test_stale_ticker_or_missing_hourly_evidence_suppresses_alert():
    stale=study(periods(),snapshot(age=121),simulation=True)
    assert stale['direction']=='WAIT' and not stale['alert']
    data=periods();data.pop('1H')
    missing=study(data,snapshot(),simulation=True)
    assert missing['direction']=='WAIT' and not missing['alert']
    far=snapshot();far['ticker']['last']=110
    assert not study(periods(),far)['alert']


def test_high_leverage_research_rejects_spot_and_missing_15m(tmp_path):
    coordinator=Coordinator(Config(data_dir=tmp_path))
    with pytest.raises(ValueError,match='perpetual'):
        coordinator.research('BTC-USDT',strategy_mode='one_usdt_simulation')
    with pytest.raises(ValueError,match='15m and 1H'):
        coordinator.research('BTC-USDT-SWAP',timeframes=['1H','1D','1W'],strategy_mode='one_usdt_simulation')


def test_quick_simulation_shows_real_quote_without_inventing_entry_levels():
    state=ResearchState(asset='BTC',instrument_id='BTC-USDT-SWAP',mode='quick',
                        strategy_mode='one_usdt_simulation',completed_at=now(),
                        snapshot=snapshot())
    decision=final_decision(state)
    assert decision['watch']['current_price']==102
    assert decision['watch']['nearest_level'] is None
    report=render_markdown(state,'zh')
    assert '看到的价格是 102' in report
    assert '没有可用的快进快出入场价和离场价' in report
    assert '未确认的做多观察方案' not in report
