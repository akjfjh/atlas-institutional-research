"""Risk veto, onboarding, and same-instrument reassessment regressions."""
from __future__ import annotations
from argparse import Namespace
import copy,json,os
from datetime import datetime,timezone
from atlas.analysis.risk import assess_risk,final_decision
from atlas.cli import initialize_profile
from atlas.config import Config,load_config
from atlas.core.coordinator import Coordinator
from atlas.core.reviewer import RiskResearchAudit
from atlas.core.state import AgentResult,ResearchState,now
from test_specialists_bilingual import markets_and_snapshot


def profile(root):
    args=Namespace(language='zh',capital_usdt=300,markets='BTC-USDT,ETH-USDT',no_open_positions=True)
    saved=initialize_profile(args,Config(data_dir=root))
    assert saved['profile']['capital_usdt']==300 and saved['profile']['language']=='zh'
    assert saved['profile']['primary_instruments']==['BTC-USDT','ETH-USDT']
    return load_config(root)


def test_first_run_profile_is_local_validated_and_private(tmp_path):
    cfg=profile(tmp_path)
    assert cfg.positions_status=='none_reported' and cfg.risk_fraction==.005
    assert (tmp_path/'config.json').stat().st_mode & 0o077==0


def test_risk_officer_veto_and_final_watch_are_recomputed(tmp_path):
    cfg=profile(tmp_path)
    _,snapshot=markets_and_snapshot('BTC')
    snapshot['instrument']={'instId':'BTC-USDT','lotSz':'0.00000001','minSz':'0.00001','tickSz':'0.01'}
    class Service:
        def collect(self,*args,**kwargs):return copy.deepcopy(snapshot)
    state=Coordinator(cfg,Service()).research('BTC-USDT')
    assert len(state.required_roles)==12
    risk=state.results['risk_control']
    assert risk.status=='complete' and risk.payload['veto']
    assert risk.payload['assessment']['risk']['risk_budget_usdt']==1.5
    decision=final_decision(state)
    assert not decision['can_open'] and decision['order_plan'] is None
    assert decision['watch']['support'] is not None and decision['watch']['resistance'] is not None
    report=(tmp_path/'reports'/state.research_id/'report.zh.md').read_text()
    assert '目前不生成挂单数量' in report and '目前不要开新仓' in report
    risk.payload['assessment']['risk']['risk_budget_usdt']=999
    assert any(i.responsible_agent=='risk_control' and i.severity=='critical' for i in RiskResearchAudit().review(state))


def test_reassessment_creates_new_id_and_carries_only_prior_reference(tmp_path):
    cfg=profile(tmp_path)
    _,snapshot=markets_and_snapshot('ETH')
    class Service:
        def collect(self,*args,**kwargs):return copy.deepcopy(snapshot)
    coordinator=Coordinator(cfg,Service())
    first=coordinator.research('ETH-USDT')
    again=coordinator.research('ETH-USDT',prior_state=first)
    assert first.research_id!=again.research_id
    assert again.prior_research_id==first.research_id
    assert again.prior_observation['watch']['support']==first.results['risk_control'].payload['assessment']['watch']['support']
    assert '重新判断前次研究' in (tmp_path/'reports'/again.research_id/'report.zh.md').read_text()


def test_limit_sizing_only_after_all_gates_and_exchange_rules(tmp_path):
    ts=int(datetime.now(timezone.utc).timestamp()*1000)
    state=ResearchState(asset='BTC',instrument_id='BTC-USDT',phase='APPROVED',completed_at=now())
    state.snapshot={'instrument':{'instId':'BTC-USDT','lotSz':'0.001','minSz':'0.001','tickSz':'0.01'}}
    state.budget={'risk_policy':{'spread_bps':2}}
    assessment={'preliminary_entry_eligible':True,'blockers':[],
                'watch':{'ticker_as_of':ts},
                'risk':{'entry_reference':100,'stop_reference':95,'capital_usdt':300,
                        'risk_budget_usdt':1.5,'portfolio_risk_cap_usdt':3,'notional_cap_usdt':75,'fees_bps_each_side':10,'slippage_bps_each_side':5}}
    state.results['risk_control']=AgentResult(research_id=state.research_id,agent_id='risk_control',asset='BTC',instrument_id='BTC-USDT',task='risk',timeframes=['1D'],payload={'assessment':assessment})
    decision=final_decision(state)
    assert decision['can_open'] and decision['order_plan']['order_type']=='limit'
    assert decision['order_plan']['allocation']=='staged'
    assert sum(map(float,decision['order_plan']['stage_base_quantities']))==float(decision['order_plan']['total_base_quantity'])
    assert float(decision['order_plan']['estimated_max_loss_usdt'])<=1.5
    state.snapshot['instrument'].pop('minSz')
    assert final_decision(state)['reasons']==['exchange_order_rules_or_size_unavailable']
