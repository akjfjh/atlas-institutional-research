from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
import uuid

LEGACY_ROLES=['fed','macro','news','technical','sentiment','backtest','trading','chief']
CURRENT_ROLES=['fed','macro','news','technical','entry_timing','sentiment','backtest','btc_specialist','eth_specialist','risk_control','trading','chief']

def now(): return datetime.now(timezone.utc).isoformat()
def uid(prefix='ev'): return prefix+'_'+uuid.uuid4().hex[:16]
class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',validate_assignment=True)
class Evidence(StrictModel):
    evidence_id:str
    source:str
    source_url:str|None=None
    instrument:str|None=None
    timestamp:str
    retrieved_at:str
    unit:str='mixed'
    status:Literal['observed','derived','unavailable','host_attested']='observed'
    quality_flags:list[str]=Field(default_factory=list)
    data:dict[str,Any]=Field(default_factory=dict)
    parent_ids:list[str]=Field(default_factory=list)
class Finding(StrictModel):
    claim:str
    claim_en:str|None=None
    evidence_ids:list[str]
    kind:Literal['fact','inference','hypothesis']='inference'
    direction:Literal['bullish','bearish','neutral']='neutral'
class Request(StrictModel):
    to_agent:str
    reason:str
    evidence_ids:list[str]=Field(default_factory=list)
class Confidence(StrictModel):
    level:Literal['low','moderate','high']='low'
    calibrated:bool=False
    probability:float|None=None
    basis:str='Evidence completeness; not a win rate.'
    @field_validator('probability')
    @classmethod
    def no_uncalibrated(cls,v,info):
        if v is not None and (not info.data.get('calibrated') or not 0<=v<=1): raise ValueError('probability requires calibrated model and [0,1]')
        return v
class AgentResult(StrictModel):
    research_id:str
    agent_id:Literal['chief','macro','fed','news','technical','entry_timing','sentiment','backtest','risk_control','trading','btc_specialist','eth_specialist']
    asset:str
    instrument_id:str
    task:str
    timeframes:list[str]
    data_sources:list[str]=Field(default_factory=list)
    data_timestamps:list[str]=Field(default_factory=list)
    evidence:list[str]=Field(default_factory=list)
    findings:list[Finding]=Field(default_factory=list)
    market_regime:str='unknown'
    bullish_arguments:list[str]=Field(default_factory=list)
    bearish_arguments:list[str]=Field(default_factory=list)
    uncertainties:list[str]=Field(default_factory=list)
    uncertainties_en:list[str]=Field(default_factory=list)
    contradictions:list[str]=Field(default_factory=list)
    contradictions_en:list[str]=Field(default_factory=list)
    summary_en:str|None=None
    confidence:Confidence=Field(default_factory=Confidence)
    requests_to_other_agents:list[Request]=Field(default_factory=list)
    status:Literal['complete','partial','blocked']='partial'
    version:int=Field(default=1,ge=1)
    input_versions:dict[str,int]=Field(default_factory=dict)
    revised_reason:str|None=None
    payload:dict[str,Any]=Field(default_factory=dict)
class ReviewIssue(StrictModel):
    issue_id:str=Field(default_factory=lambda:uid('issue'))
    severity:Literal['warning','error','critical']
    responsible_agent:str
    problem:str
    required_correction:str
    evidence:list[str]=Field(default_factory=list)
    status:Literal['open','resolved']='open'
    correctable:bool=False
class ResearchState(StrictModel):
    schema_version:str='1.3'
    research_id:str=Field(default_factory=lambda:uid('atlas'))
    created_at:str=Field(default_factory=now)
    completed_at:str|None=None
    asset:str
    instrument_id:str
    mode:Literal['quick','full']='full'
    engine:Literal['deterministic','host','llm','codex']='deterministic'
    language:Literal['zh','en']='zh'
    trader_level:Literal['novice','experienced']='novice'
    holding_horizon:str='1d'
    strategy_mode:Literal['standard','one_usdt_simulation']='standard'
    required_roles:list[str]=Field(default_factory=lambda:CURRENT_ROLES.copy())
    timeframes:list[str]=Field(default_factory=lambda:['1D','1W','1M'])
    phase:Literal['DATA_READY','RESEARCH_IN_PROGRESS','CROSS_VALIDATION','BACKTEST_VALIDATION','STRATEGY_REVIEW','FINAL_AUDIT','APPROVED','REJECTED','INSUFFICIENT_DATA']='DATA_READY'
    decision:Literal['BULLISH','BEARISH','NEUTRAL','WAIT_FOR_CONFIRMATION','INSUFFICIENT_DATA']='INSUFFICIENT_DATA'
    snapshot:dict[str,Any]=Field(default_factory=dict)
    evidence:dict[str,Evidence]=Field(default_factory=dict)
    results:dict[str,AgentResult]=Field(default_factory=dict)
    messages:list[dict[str,Any]]=Field(default_factory=list)
    events:list[dict[str,Any]]=Field(default_factory=list)
    issues:list[ReviewIssue]=Field(default_factory=list)
    backtest:dict[str,Any]=Field(default_factory=dict)
    scenarios:dict[str,Any]=Field(default_factory=dict)
    research_note:str=''
    codex_review:dict[str,Any]=Field(default_factory=dict)
    round:int=0
    version:int=1
    budget:dict[str,Any]=Field(default_factory=dict)
    historical_comparisons:list[dict[str,Any]]=Field(default_factory=list)
    prior_research_id:str|None=None
    prior_observation:dict[str,Any]=Field(default_factory=dict)
    @model_validator(mode='before')
    @classmethod
    def preserve_legacy_role_scope(cls,value):
        if isinstance(value,dict) and value.get('schema_version')=='1.0' and 'required_roles' not in value:
            value=dict(value);value['required_roles']=LEGACY_ROLES.copy()
        return value
    @field_validator('required_roles')
    @classmethod
    def known_unique_roles(cls,value):
        if not value or len(value)!=len(set(value)) or any(role not in CURRENT_ROLES for role in value):
            raise ValueError('required_roles must be a nonempty unique known-role list')
        return value
    def event(self,kind,**payload):
        self.events.append({'event_id':uid(),'timestamp':now(),'kind':kind,'round':self.round,**payload})
    def add_evidence(self,source,data,*,agent='data',url=None,timestamp=None,unit='mixed',status='observed',parents=None,flags=None,instrument=None):
        eid=uid('evidence')
        ev=Evidence(evidence_id=eid,source=source,source_url=url,instrument=instrument or self.instrument_id,timestamp=timestamp or self.snapshot.get('retrieved_at',self.created_at),retrieved_at=self.snapshot.get('retrieved_at',self.created_at),unit=unit,status=status,data=data,parent_ids=parents or [],quality_flags=flags or [])
        self.evidence[eid]=ev
        return eid
    def set_result(self,result:AgentResult):
        if result.research_id != self.research_id or result.instrument_id != self.instrument_id or result.asset != self.asset: raise ValueError('result research/instrument mismatch')
        referenced=set(result.evidence)|{e for f in result.findings for e in f.evidence_ids}
        if referenced-set(self.evidence): raise ValueError('unknown evidence references: '+str(sorted(referenced-set(self.evidence))))
        old=self.results.get(result.agent_id)
        if old and result.version<=old.version: raise ValueError('revision must increase version')
        self.results[result.agent_id]=result
        self.event('agent_result',agent_id=result.agent_id,version=result.version,status=result.status,input_versions=result.input_versions)
