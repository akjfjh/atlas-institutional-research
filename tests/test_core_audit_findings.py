"""Independent review regressions using explicit synthetic data and temp storage.

These exercise gates/host workflows and do not validate live data or send orders.
"""
import json
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
import pytest
from atlas.config import Config
from atlas.core.state import ResearchState,AgentResult
from atlas.core.coordinator import Coordinator
from atlas.core.reviewer import RiskResearchAudit,DataIntegrityValidator,parse_time,issue
from atlas.core.storage import Repository
from atlas.analysis.indicators import analyze

DAY=86_400_000

def synthetic_snapshot(*,age_days=0):
    now_ms=int(time.time()*1000)
    frames={}
    for tf,step,count in [('1D',DAY,160),('1W',7*DAY,80),('1M',30*DAY,40)]:
        rows=[]
        end=now_ms-age_days*DAY
        for i in range(count):
            p=100+i*.1
            ts=end-(count-i)*step
            rows.append({'ts':ts,'open':p,'high':p+1,'low':p-1,'close':p,'volume':100,'confirm':True,'available_at':ts+step})
        frames[tf]=rows
    return {'instrument_id':'ETH-USDT','asset':'ETH','retrieved_at':datetime.now(timezone.utc).isoformat(),'mode':'live','ticker':{'last':116,'ts':now_ms},'candles':frames,'sources':[{'source':'explicit synthetic fixture for gate tests'}],'errors':[]}


def technical_result(state,**kw):
    base=dict(research_id=state.research_id,agent_id='technical',asset=state.asset,instrument_id=state.instrument_id,task='Synthetic review regression',timeframes=state.timeframes,status='complete',payload={'timeframes':{tf:analyze(rows) for tf,rows in state.snapshot['candles'].items()}})
    base.update(kw)
    return AgentResult(**base)


def test_negative_timezone_offset_is_respected():
    assert parse_time('2026-10-26T10:00:00-05:00')==parse_time('2026-10-26T15:00:00Z')


def test_missing_computed_metric_payload_cannot_pass_quick_gate():
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='quick',snapshot=synthetic_snapshot())
    st.set_result(technical_result(st,payload={'timeframes':{tf:{'trend':'bullish','metrics':{}} for tf in st.timeframes}}))
    problems=RiskResearchAudit().review(st)
    assert any(i.severity in {'error','critical'} and i.responsible_agent=='technical' for i in problems)


def test_current_ticker_cannot_make_stale_candles_current():
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='quick',snapshot=synthetic_snapshot(age_days=800))
    problems=DataIntegrityValidator().review(st)
    assert any(i.severity in {'error','critical'} for i in problems)


def test_ticker_price_must_be_finite_and_positive():
    snapshot=synthetic_snapshot();snapshot['ticker']['last']=-100
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='quick',snapshot=snapshot)
    assert any(i.severity in {'error','critical'} for i in DataIntegrityValidator().review(st))


def test_review_rework_refreshes_report_snapshot_payloads(tmp_path,monkeypatch):
    from atlas.core import coordinator as module
    cfg=Config(data_dir=tmp_path,max_rounds=1)
    c=Coordinator(cfg)
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='full',snapshot=synthetic_snapshot())
    st.results['technical']=technical_result(st)
    for role,payload in [('trading',{'scenarios':{'marker':'old'}}),('backtest',{'marker':'old'})]:
        st.results[role]=AgentResult(research_id=st.research_id,agent_id=role,asset='ETH',instrument_id='ETH-USDT',task='Synthetic',timeframes=st.timeframes,status='complete',payload=payload)
    class Review:
        n=0
        def review(self,state):
            Review.n+=1
            return [issue('critical','technical','force deterministic rework regression',True)] if Review.n==1 else []
    def execute(state,roles,start):
        state.results['trading'].payload={'scenarios':{'marker':'new'}}
        state.results['backtest'].payload={'marker':'new'}
    monkeypatch.setattr(module,'RiskResearchAudit',Review)
    monkeypatch.setattr(c,'_execute',execute)
    result=c.finalize(st)
    assert result.scenarios==result.results['trading'].payload['scenarios']
    assert result.backtest==result.results['backtest'].payload


def test_evidence_id_cannot_silently_rewrite_archived_fact(tmp_path):
    repo=Repository(tmp_path)
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT')
    eid=st.add_evidence('synthetic:test',{'value':1})
    repo.save(st)
    st.evidence[eid].data={'value':999}
    with pytest.raises((ValueError,RuntimeError)):
        repo.save(st)


def test_quick_host_cli_completes_after_its_only_required_actor(tmp_path):
    fixture=tmp_path/'explicit-synthetic-fixture.json';fixture.write_text(json.dumps(synthetic_snapshot()))
    root=Path(__file__).resolve().parents[1]
    args=[sys.executable,'-m','atlas.cli']
    start=subprocess.run(args+['research','ETH-USDT','--mode','quick','--engine','host','--fixture',str(fixture),'--data-dir',str(tmp_path/'data')],cwd=root,capture_output=True,text=True,timeout=30)
    assert start.returncode==0,start.stderr+start.stdout
    state=json.loads(start.stdout)
    result=subprocess.run(args+['task-run',state['research_id'],'--agent','technical','--data-dir',str(tmp_path/'data')],cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr+result.stdout
    final=json.loads(result.stdout)
    assert final['phase'] in {'INSUFFICIENT_DATA','REJECTED','APPROVED'}
    assert not final['ready']
    assert (tmp_path/'data'/'reports'/state['research_id']/'report.json').is_file()


def test_trend_and_nested_indicator_tampering_block_gate(tmp_path):
    from atlas.core.roles import RoleWorker
    cfg=Config(data_dir=tmp_path,max_rounds=0)
    c=Coordinator(cfg)
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='quick',snapshot=synthetic_snapshot())
    c.prepare_evidence(st)
    result,new=RoleWorker('technical',cfg).run(st)
    st.set_result(result)
    for payload in st.results['technical'].payload['timeframes'].values():
        payload['trend']='bearish' # Actual synthetic fixture trend is bullish.
        payload['metrics']['adx']['adx']=0 # Alter nested deterministic output too.
    issues=RiskResearchAudit().review(st)
    assert any(i.severity=='critical' and i.responsible_agent=='technical' for i in issues)


def test_probability_requires_more_than_self_attested_calibrated_flag(tmp_path):
    from atlas.core.roles import RoleWorker
    cfg=Config(data_dir=tmp_path,max_rounds=0)
    st=ResearchState(asset='ETH',instrument_id='ETH-USDT',mode='quick',snapshot=synthetic_snapshot())
    Coordinator(cfg).prepare_evidence(st)
    result,new=RoleWorker('technical',cfg).run(st)
    # No calibrated model or validation artifact is present in v0.1.
    result.confidence.calibrated=True
    try:
        result.confidence.probability=.99
    except ValueError:
        return # A schema-level prohibition is also acceptable.
    st.set_result(result)
    issues=RiskResearchAudit().review(st)
    assert any(i.severity=='critical' for i in issues)


def test_cli_preserves_persisted_offline_configuration(tmp_path):
    (tmp_path/'config.json').write_text(json.dumps({'offline':True}))
    root=Path(__file__).resolve().parents[1]
    proc=subprocess.run([sys.executable,'-m','atlas.cli','config','show','--data-dir',str(tmp_path)],cwd=root,capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,proc.stderr+proc.stdout
    assert json.loads(proc.stdout)['offline'] is True
