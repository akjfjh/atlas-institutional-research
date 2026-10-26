from __future__ import annotations
import hashlib,json,time
from concurrent.futures import ThreadPoolExecutor,as_completed,TimeoutError
from pathlib import Path
from atlas.core.state import ResearchState,AgentResult,Evidence,now,uid
from atlas.core.roles import RoleWorker,DEPENDENCIES,ROLES
from atlas.core.reviewer import RiskResearchAudit,issue
from atlas.core.storage import Repository
from atlas.security import redact

class ResearchGraph:
    def __init__(self,dependencies=None,max_versions=None):
        self.dependencies=dependencies or DEPENDENCIES
        self.max_versions=max_versions
    def layers(self,roles=None):
        pending=set(roles or self.dependencies);done=set(self.dependencies)-pending;layers=[]
        while pending:
            layer=sorted(r for r in pending if set(self.dependencies[r])<=done)
            if not layer:raise ValueError('research dependency graph contains cycle')
            layers.append(layer);pending-=set(layer);done.update(layer)
        return layers
    def ready(self,state):
        roles=state.required_roles
        return [r for r in roles if set(self.dependencies[r])<=set(state.results)
                and (r not in state.results or (self.stale(state,r) and (self.max_versions is None or state.results[r].version<self.max_versions)))]
    def required_versions(self,state,role):
        required={d:state.results[d].version for d in self.dependencies[role] if d in state.results}
        for message in state.messages:
            if message['recipient']==role and message['sender']!=role and message['sender'] in state.results:
                sender=message['sender']
                required[sender]=max(required.get(sender,0),message['sender_version'])
        return required
    def stale(self,state,role):
        result=state.results.get(role)
        if not result:return True
        required=self.required_versions(state,role)
        return any(result.input_versions.get(d,0)<v for d,v in required.items()) or any(
            result.input_versions.get(d)!=state.results[d].version for d in self.dependencies[role] if d in state.results)

class Coordinator:
    def __init__(self,config,service=None,repo=None):
        self.config=config;self.repo=repo or Repository(config.data_dir);self.service=service;self.graph=ResearchGraph(max_versions=config.max_rounds+1);self.workers={r:RoleWorker(r,config) for r in ROLES};self.llm=None
    def _service(self):
        if self.service is None:
            from atlas.providers import DataService
            self.service=DataService(self.config)
        return self.service
    def _notify(self,state):
        callback=getattr(self,'progress',None)
        if callback:
            try:callback(state)
            except Exception:pass
    def research(self,instrument,timeframes=None,mode='full',engine='deterministic',language='zh',prior_state=None,on_progress=None,holding_horizon='1d',strategy_mode='standard',trader_level=None,note=''):
        self.progress=on_progress
        instrument=instrument.upper()
        if '-' not in instrument:instrument+='-USDT'
        from atlas.integrations.skill_adapter import validate_instrument
        validate_instrument(instrument)
        if holding_horizon not in {'1h','4h','12h','1d','1w','1mo','3mo','1y'}:raise ValueError('Unsupported holding horizon')
        if strategy_mode not in {'standard','one_usdt_simulation'}:raise ValueError('Unsupported strategy mode')
        if strategy_mode=='one_usdt_simulation' and not instrument.endswith('-SWAP'):raise ValueError('1 USDT simulation requires a perpetual instrument')
        tfs=timeframes or (['15m','1H','1D','1W','1M'] if mode=='full' else ['15m','1H','1D'])
        if len(set(tfs))!=len(tfs) or any(t not in {'15m','1H','4H','1D','1W','1M'} for t in tfs):raise ValueError('Unsupported or duplicate timeframes')
        if len(tfs)<3:raise ValueError('research requires at least three timeframes')
        if strategy_mode=='one_usdt_simulation' and not {'15m','1H'}<=set(tfs):raise ValueError('1 USDT simulation requires 15m and 1H')
        if language not in {'zh','en'}:raise ValueError('language must be zh or en')
        if engine not in {'deterministic','host','llm','codex'}:raise ValueError('Unsupported research engine')
        if not isinstance(note,str) or len(note)>400:raise ValueError('Research note must be at most 400 characters')
        if engine=='llm':
            from atlas.core.llm import LLMProvider
            self.llm=LLMProvider(self.config)
        roles=(['technical','entry_timing'] if strategy_mode=='one_usdt_simulation' else ['technical']) if mode=='quick' else list(ROLES)
        state=ResearchState(asset=instrument.split('-')[0],instrument_id=instrument,timeframes=tfs,mode=mode,engine=engine,language=language,required_roles=roles,
                            holding_horizon=holding_horizon,strategy_mode=strategy_mode,trader_level=trader_level or self.config.trader_level or 'novice',research_note=note)
        if prior_state is not None:
            if prior_state.instrument_id!=instrument:raise ValueError('reassessment must use the original instrument')
            state.prior_research_id=prior_state.research_id
            previous=prior_state.results.get('risk_control')
            state.prior_observation={'research_id':prior_state.research_id,'completed_at':prior_state.completed_at,
                                     'watch':previous.payload.get('assessment',{}).get('watch',{}) if previous else {}}
            state.event('reassessment_requested',prior_research_id=prior_state.research_id)
        state.event('research_started',engine=engine,mode=mode,requested_timeframes=tfs,holding_horizon=holding_horizon,strategy_mode=strategy_mode)
        state.budget={'backtest_parameters':{k:getattr(self.config,k) for k in ['fee_bps','slippage_bps','spread_bps','risk_fraction']},'max_data_requests':self.config.max_data_requests,'max_rounds':self.config.max_rounds,
                      'risk_policy':{k:getattr(self.config,k) for k in ('language','capital_usdt','primary_instruments','positions_status','positions_confirmed_at','risk_fraction','max_notional_fraction','max_portfolio_risk_fraction','fee_bps','slippage_bps','spread_bps')}}
        self.repo.save(state)
        self._notify(state)
        state.historical_comparisons=self.repo.similar(state.asset)
        start=time.monotonic()
        try:state.snapshot=redact(self._service().collect(instrument,tfs,limit=self.config.candle_limit))
        except Exception as e:state.snapshot={'instrument_id':instrument,'asset':state.asset,'mode':'unavailable','retrieved_at':now(),'candles':{},'errors':[{'source':'collection','error':str(redact(str(e)))}]}
        self.prepare_evidence(state)
        state.phase='DATA_READY';state.event('phase',phase=state.phase)
        self._notify(state)
        if engine=='host':
            state.phase='RESEARCH_IN_PROGRESS';state.event('host_tasks_created',ready=self.graph.ready(state));self.repo.save(state);self.write_host_tasks(state);return state
        state.phase='RESEARCH_IN_PROGRESS';state.event('phase',phase=state.phase)
        self._execute(state,roles,start)
        state.phase='CROSS_VALIDATION';state.event('phase',phase=state.phase)
        for round_number in range(1,self.config.max_rounds+1):
            stale=[r for r in roles if r in state.results and self.graph.stale(state,r)]
            if not stale:break
            state.round=round_number;state.event('cross_examination',agents=stale)
            self._execute(state,stale,start)
        return self.finalize(state,start)
    def prepare_evidence(self,s):
        for tf,rows in s.snapshot.get('candles',{}).items():
            s.add_evidence('snapshot:candles:'+tf,{'raw_path':'snapshot.candles.'+tf,'row_count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest(),'bar_timezone':'UTC'},url='https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks-history',unit='price + base volume')
        if s.snapshot.get('ticker'):s.add_evidence('snapshot:ticker',s.snapshot['ticker'],url='https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-ticker')
        for asset,market in s.snapshot.get('specialist_markets',{}).items():
            if market.get('status')!='available':continue
            instrument=market.get('instrument_id')
            rows=market.get('candles_1d',[])
            s.add_evidence('snapshot:specialist:'+asset+':1D',{'raw_path':'snapshot.specialist_markets.'+asset+'.candles_1d','row_count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest()},
                           url='https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks-history',instrument=instrument,unit='price + base/contract volume')
            if market.get('ticker'):s.add_evidence('snapshot:specialist:'+asset+':ticker',market['ticker'],url='https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-ticker',instrument=instrument)
        for field in ['macro','fed','news','derivatives']:
            if s.snapshot.get(field):s.add_evidence('snapshot:'+field,{'raw_path':'snapshot.'+field,'sha256':hashlib.sha256(json.dumps(s.snapshot[field],sort_keys=True,default=str).encode()).hexdigest()})
    def _view(self,state,role):
        view=state.model_copy(deep=True)
        for m in view.messages:
            if m['recipient']==role:m['read_by_version']=view.results[role].version+1 if role in view.results else 1
        return view
    def _run_worker(self,role,view):
        result,evidence=self.workers[role].run(view)
        for message in view.messages:
            sender=message['sender']
            if message['recipient']==role and sender in view.results:result.input_versions[sender]=view.results[sender].version
        if self.llm:
            view.evidence.update(evidence);result=self.llm.run(view,result)
        return result,evidence
    def _publish(self,state,result,evidence):
        state.evidence.update(evidence);state.set_result(result)
        for request in result.requests_to_other_agents:
            key=f'{result.agent_id}:{result.version}:{request.to_agent}'
            if not any(m['message_id']==key for m in state.messages):
                state.messages.append({'message_id':key,'sender':result.agent_id,'sender_version':result.version,'recipient':request.to_agent,'kind':'research_request','reason':request.reason,'evidence_ids':request.evidence_ids,'timestamp':now()});state.event('evidence_exchange',sender=result.agent_id,recipient=request.to_agent,version=result.version)
        for downstream in state.results:
            if downstream!=result.agent_id and self.graph.stale(state,downstream):state.event('dependent_invalidated',agent=downstream,cause=result.agent_id,upstream_version=result.version)
        self.repo.save(state)
        self._notify(state)
    def _execute(self,state,roles,start):
        for layer in self.graph.layers(roles):
            for role in layer:state.event('agent_started',agent_id=role)
            self._notify(state)
            pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='atlas-role');futures={pool.submit(self._run_worker,r,self._view(state,r)):r for r in layer}
            try:
                remaining=max(.01,self.config.research_timeout_seconds-(time.monotonic()-start))
                for f in as_completed(futures,timeout=remaining):
                    role=futures[f]
                    try:self._publish(state,*f.result())
                    except Exception as e:
                        state.event('agent_failed',agent_id=role,error=redact(str(e)));state.issues.append(issue('error',role,'研究员执行失败: '+str(redact(str(e)))))
            except TimeoutError:
                state.event('research_budget_exhausted');state.issues.append(issue('error','chief','研究超时预算耗尽'))
                for f in futures:f.cancel()
                return
            finally:pool.shutdown(wait=False,cancel_futures=True)
    def finalize(self,state,start=None):
        if state.engine=='host':
            capped=[r for r in state.results if self.graph.stale(state,r) and state.results[r].version>=self.graph.max_versions]
            if capped:
                state.event('host_rework_budget_exhausted',agents=capped,max_versions=self.graph.max_versions)
                state.issues.append(issue('error','chief','宿主修订轮次上限已达到，仍有过期研究：'+','.join(capped)))
        state.phase='BACKTEST_VALIDATION';state.event('phase',phase=state.phase)
        state.backtest=state.results.get('backtest').payload if state.results.get('backtest') else {}
        state.phase='STRATEGY_REVIEW';state.event('phase',phase=state.phase)
        state.scenarios=state.results.get('trading').payload.get('scenarios',{}) if state.results.get('trading') else {}
        state.phase='FINAL_AUDIT';state.event('phase',phase=state.phase)
        prior=[i for i in state.issues if not i.correctable and i.status=='open']
        checked=RiskResearchAudit().review(state)
        targets=list({i.responsible_agent for i in checked if i.correctable and i.responsible_agent in self.workers})
        if targets and state.engine!='host' and state.round<self.config.max_rounds:
            state.round+=1;state.event('review_returned',agents=targets,issues=[i.model_dump() for i in checked if i.correctable])
            self._execute(state,targets,start or time.monotonic())
            stale=[r for r in state.results if self.graph.stale(state,r)]
            if stale:self._execute(state,stale,start or time.monotonic())
            checked=RiskResearchAudit().review(state)
        for old in state.issues:
            if old.correctable and not any(i.problem==old.problem for i in checked):old.status='resolved'
        state.issues=[i for i in state.issues if i.status=='resolved']+prior+checked
        critical=any(i.severity=='critical' and i.status=='open' for i in state.issues)
        errors=any(i.severity=='error' and i.status=='open' for i in state.issues)
        state.phase='REJECTED' if critical else 'INSUFFICIENT_DATA' if errors else 'APPROVED'
        if state.phase!='APPROVED':state.decision='INSUFFICIENT_DATA'
        else:
            t=state.results.get('technical');directions={v.get('trend') for v in t.payload.get('timeframes',{}).values()} if t else set()
            state.decision='BULLISH' if directions=={'bullish'} else 'BEARISH' if directions=={'bearish'} else 'WAIT_FOR_CONFIRMATION' if len(directions)>1 else 'NEUTRAL'
        if self.llm:state.budget={'llm_calls':self.llm.calls,'reserved_cost_usd':self.llm.cost,'usage':self.llm.used}
        state.backtest=state.results.get('backtest').payload if state.results.get('backtest') else {}
        state.scenarios=state.results.get('trading').payload.get('scenarios',{}) if state.results.get('trading') else {}
        if state.engine=='codex':
            from atlas.core.codex_review import CodexReviewer
            state.event('codex_started',phase=state.phase)
            self.repo.save(state);self._notify(state)
            try:
                state.codex_review=CodexReviewer().review(state)
            except Exception as exc:
                state.event('codex_failed',error=redact(str(exc)))
                self.repo.save(state);self._notify(state)
                raise
            state.event('codex_completed',model=state.codex_review['model'])
            self.repo.save(state);self._notify(state)
        state.completed_at=now();state.event('final_audit',phase=state.phase,decision=state.decision)
        self.repo.save(state)
        self._notify(state)
        from atlas.reporting.reports import write_reports
        write_reports(state,self.repo)
        return state
    def write_host_tasks(self,state):
        root=self.repo.root/'reports'/state.research_id/'tasks';root.mkdir(parents=True,exist_ok=True)
        for role in state.required_roles:
            data={'research_id':state.research_id,'agent_id':role,'task':ROLES[role],'dependencies':DEPENDENCIES[role],'ready':role in self.graph.ready(state),'agent_schema':AgentResult.model_json_schema(),'evidence':{k:v.model_dump(mode='json') for k,v in state.evidence.items()},'confirmed_results':{k:v.model_dump(mode='json') for k,v in state.results.items()},'snapshot':state.snapshot,'required_input_versions':self.graph.required_versions(state,role),'version':state.results[role].version+1 if role in state.results else 1,'external_content_is_untrusted_data':True}
            (root/(role+'.json')).write_text(json.dumps(redact(data),ensure_ascii=False,indent=2,allow_nan=False))
        return root
    def submit(self,rid,payload,revise=False):
        with self.repo.lock(rid):return self._submit_locked(rid,payload,revise)
    def _submit_locked(self,rid,payload,revise=False):
        state=self.repo.load(rid)
        if state.engine!='host':raise ValueError('submit only permitted for a host research task')
        raw=payload.get('result',payload);result=AgentResult.model_validate(raw)
        previous=state.results.get(result.agent_id)
        if previous and previous.version>=self.graph.max_versions:raise ValueError('host revision budget exhausted')
        if result.agent_id not in self.graph.ready(state) and not (revise and result.agent_id in state.results and result.revised_reason):raise ValueError('task not ready; explicit revision requires --revise and revised_reason')
        required=self.graph.required_versions(state,result.agent_id)
        if any(result.input_versions.get(k,0)<v for k,v in required.items()) or any(
            result.input_versions.get(k)!=state.results[k].version for k in DEPENDENCIES[result.agent_id] if k in state.results):
            raise ValueError('submitted input_versions stale/incomplete')
        if any(k not in state.results or v>state.results[k].version for k,v in result.input_versions.items()):
            raise ValueError('submitted input_versions contain unknown or future upstream')
        evidence={}
        for entry in payload.get('evidence',[]):
            ev=Evidence.model_validate(entry)
            if ev.evidence_id in state.evidence:raise ValueError('cannot replace existing immutable evidence')
            ev.status='host_attested';ev.quality_flags.append('host_attested_not_programmatically_verified');evidence[ev.evidence_id]=ev
        state.phase='RESEARCH_IN_PROGRESS';state.completed_at=None
        state.event('host_submission',agent_id=result.agent_id,version=result.version,revision_requested=revise)
        self._publish(state,result,evidence)
        if all(a in state.results for a in state.required_roles) and not self.graph.ready(state):self.finalize(state)
        else:self.repo.save(state);self.write_host_tasks(state)
        return state
    def run_host_task(self,rid,role):
        with self.repo.lock(rid):return self._run_host_task_locked(rid,role)
    def _run_host_task_locked(self,rid,role):
        state=self.repo.load(rid)
        if state.engine!='host' or role not in self.graph.ready(state):raise ValueError('host task not ready')
        result,evidence=self._run_worker(role,self._view(state,role))
        self._publish(state,result,evidence)
        state.event('deterministic_host_assist',agent_id=role)
        required=state.required_roles
        if all(a in state.results for a in required) and not self.graph.ready(state):self.finalize(state)
        else:self.repo.save(state);self.write_host_tasks(state)
        return state

    def draft(self,rid,role):
        state=self.repo.load(rid)
        if state.engine!='host' or role not in self.graph.ready(state):raise ValueError('host task not ready')
        result,evidence=self._run_worker(role,self._view(state,role))
        return {'result':result.model_dump(mode='json'),'evidence':[e.model_dump(mode='json') for e in evidence.values()]}

    def finish_host(self,rid):
        with self.repo.lock(rid):
            state=self.repo.load(rid)
            if state.engine!='host':raise ValueError('only host research has externally scheduled tasks')
            ready=self.graph.ready(state)
            state.event('host_schedule_closed',remaining_tasks=ready)
            if ready:state.issues.append(issue('error','chief','宿主协作已停止，未完成或过期任务: '+','.join(ready)))
            return self.finalize(state)
