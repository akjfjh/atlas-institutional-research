"""Small loopback-only dashboard server; no trading or arbitrary file endpoints."""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse
import hmac
import base64
import json
import re
import secrets
import os
import tempfile
import time
import webbrowser

from atlas.analysis.risk import final_decision
from atlas.config import load_config
from atlas.core.coordinator import Coordinator
from atlas.core.roles import DEPENDENCIES, ROLES, ROLES_EN
from atlas.core.storage import Repository
from atlas.integrations.skill_adapter import validate_instrument
from atlas.providers import DataService
from atlas.providers.okx_public_api import instrument_type
from atlas.security import redact

STATIC=Path(__file__).resolve().parent/'static'
RID=re.compile(r'^atlas_[0-9a-f]{16}$')
JOB=re.compile(r'^[0-9a-f]{24}$')


def utc_now()->str:
    return datetime.now(timezone.utc).isoformat()

def role_brief(role,result,language='zh'):
    en=language=='en'
    if result is None:return 'Waiting' if en else '等待开始'
    data=result.payload or {}
    if role=='fed':return (f'{len(data.get("events",[]))} official releases checked' if en else f'核对 {len(data.get("events",[]))} 条官方消息')
    if role=='macro':return (f'{len(data.get("latest",{}))} data series checked' if en else f'核对 {len(data.get("latest",{}))} 项经济数据')
    if role=='news':return (f'{len(data.get("events",[]))} unique events checked' if en else f'核对 {len(data.get("events",[]))} 条新闻')
    if role=='technical':
        trends=data.get('timeframes',{});hour=trends.get('1H',{}).get('trend')
        return (f'1H trend: {hour or "unavailable"}' if en else f'1 小时方向：'+{'bullish':'偏上','bearish':'偏下','neutral':'不明显'}.get(hour,'数据不足'))
    if role=='entry_timing':return ('15m and 1H setup observed; check risk' if data.get('signal')=='closed_bar_setup' else '15m and 1H do not confirm; wait') if en else ('15 分钟和 1 小时出现条件形态，仍要看风控' if data.get('signal')=='closed_bar_setup' else '15 分钟和 1 小时尚未共同确认，等待')
    if role=='sentiment':return ('Derivatives evidence is incomplete' if en else '合约情绪证据仍不完整')
    if role=='backtest':return ('Technical proxy simulation only' if en else '只完成技术规则的历史模拟') if data else ('Backtest unavailable' if en else '历史模拟数据不足')
    if role in {'btc_specialist','eth_specialist'}:
        quant=data.get('quant',{});value=quant.get('own_return_30d')
        return (f'30-day observed return {value:+.1%}' if en else f'过去 30 天实际涨跌 {value:+.1%}') if isinstance(value,(float,int)) else ('Specialist data unavailable' if en else '专项数据不足')
    if role=='risk_control':return (f'{len(data.get("assessment",{}).get("blockers",[]))} entry blockers' if en else f'发现 {len(data.get("assessment",{}).get("blockers",[]))} 项开仓阻碍')
    if role=='trading':return ('Conditional scenarios only; no order' if en else '仅整理条件方案，未下单')
    if role=='chief':return ('Waiting for missing evidence' if en else '仍有证据不足') if result.status!='complete' else ('Review completed' if en else '已完成复核')
    return result.status


def compact_state(state)->dict:
    roles={}
    reviewed={item.get('agent_id'):item for item in state.codex_review.get('role_reviews',[])} if state.codex_review.get('status')=='complete' else {}
    for role in state.required_roles:
        result=state.results.get(role)
        codex=reviewed.get(role,{})
        roles[role]={'id':role,'title':ROLES[role],'title_en':ROLES_EN[role],
                     'dependencies':DEPENDENCIES[role],
                     'status':result.status if result else 'waiting',
                     'version':result.version if result else 0,
                     'findings':[{'claim':f.claim,'claim_en':f.claim_en,'direction':f.direction,
                                  'evidence_ids':f.evidence_ids} for f in result.findings[:5]] if result else [],
                     'uncertainties':result.uncertainties[:5] if result else [],
                     'uncertainties_en':result.uncertainties_en[:5] if result else [],
                     'summary':(result.findings[0].claim if result and result.findings else None),
                     'summary_en':(result.findings[0].claim_en if result and result.findings else None),
                     'brief_zh':codex.get('result_zh') or role_brief(role,result,'zh'),
                     'brief_en':codex.get('result_en') or role_brief(role,result,'en'),
                     'simple_zh':codex.get('result_simple_zh'),
                     'simple_en':codex.get('result_simple_en'),
                     'simple_work_zh':codex.get('work_simple_zh'),
                     'simple_work_en':codex.get('work_simple_en'),
                     'codex_work_zh':codex.get('work_zh'),'codex_work_en':codex.get('work_en'),
                     'codex_evidence_ids':codex.get('evidence_ids',[]),
                     'evidence_count':len(result.evidence) if result else 0,
                     'input_versions':result.input_versions if result else {}}
    chart={tf:[{k:row.get(k) for k in ('ts','open','high','low','close','volume','available_at')}
               for row in state.snapshot.get('candles',{}).get(tf,[])[-180:]] for tf in state.timeframes}
    technical=state.results.get('technical')
    chart_levels={tf:{k:period.get(k) for k in ('support','resistance')}
                  for tf,period in (technical.payload.get('timeframes',{}) if technical else {}).items()}
    return redact({'research_id':state.research_id,'prior_research_id':state.prior_research_id,
                   'instrument_id':state.instrument_id,'market_type':instrument_type(state.instrument_id),
                   'asset':state.asset,'created_at':state.created_at,'completed_at':state.completed_at,
                   'phase':state.phase,'decision':state.decision,'engine':state.engine,'language':state.language,
                   'trader_level':state.trader_level,'holding_horizon':state.holding_horizon,
                   'strategy_mode':state.strategy_mode,'codex_review':state.codex_review,
                   'data_mode':state.snapshot.get('mode'),'ticker':state.snapshot.get('ticker',{}),
                   'charts':chart,'chart_levels':chart_levels,'roles':roles,'events':state.events[-100:],
                   'messages':state.messages[-60:],
                   'sources':state.snapshot.get('sources',[])[:100],
                   'issues':[{'severity':i.severity,'responsible_agent':i.responsible_agent,
                              'problem':i.problem,'status':i.status} for i in state.issues],
                   'backtest':state.backtest.get('comparison',{}),
                   'entry_timing':state.results.get('entry_timing').payload if state.results.get('entry_timing') else None,
                   'scenarios':state.scenarios,
                   'risk':final_decision(state) if state.completed_at else None,
                   'report_available':bool(state.completed_at)})


class Dashboard:
    def __init__(self,config):
        self.config=config
        self.repo=Repository(config.data_dir)
        self.token=secrets.token_urlsafe(32)
        self.lock=Lock()
        self.jobs={}
        self.catalog={}
        self.journal_path=config.data_dir/'ui-journal.jsonl'
    def journal(self,kind,**data):
        entry={'at':utc_now(),'kind':kind,**data}
        with self.lock:
            with self.journal_path.open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(redact(entry),ensure_ascii=False)+'\n')
            try:self.journal_path.chmod(0o600)
            except OSError:pass
    def journal_entries(self):
        if not self.journal_path.is_file():return []
        with self.lock:
            lines=self.journal_path.read_text(encoding='utf-8').splitlines()[-100:]
        out=[]
        for line in lines:
            try:out.append(json.loads(line))
            except json.JSONDecodeError:continue
        return out[::-1]
    def instruments(self,kind):
        if kind not in {'SPOT','SWAP','FUTURES'}:raise ValueError('Unsupported instrument type')
        with self.lock:
            entry=self.catalog.get(kind)
            if entry and time.time()-entry['fetched_epoch']<600:return entry['payload']
        service=DataService(self.config)
        try:rows,meta=service.api.call('/api/v5/public/instruments',{'instType':kind})
        finally:service.close()
        items=[]
        for row in rows:
            inst=row.get('instId')
            if not isinstance(inst,str):continue
            try:validate_instrument(inst)
            except ValueError:continue
            items.append({'id':inst,'base':row.get('baseCcy') or row.get('uly') or inst.split('-')[0],
                          'quote':row.get('quoteCcy') or (inst.split('-')[1] if '-' in inst else ''),
                          'state':row.get('state','unknown'),'type':kind,
                          'expiry':row.get('expTime') or None,'family':row.get('instFamily') or None})
        items.sort(key=lambda x:(x['state']!='live',x['id']))
        payload={'type':kind,'count':len(items),'instruments':items,'source':'OKX public instruments',
                 'source_url':'https://www.okx.com/docs-v5/en/#public-data-rest-api-get-instruments',
                 'fetched_at':utc_now(),'cached_transport':bool(meta.get('cached'))}
        with self.lock:self.catalog[kind]={'fetched_epoch':time.time(),'payload':payload}
        return payload
    def verify_selection(self,instrument):
        validate_instrument(instrument)
        kind=instrument_type(instrument)
        if kind not in {'SPOT','SWAP','FUTURES'}:raise ValueError('Unsupported market type')
        catalog=self.instruments(kind)
        found=next((x for x in catalog['instruments'] if x['id']==instrument),None)
        if not found:raise ValueError('Instrument is absent from current OKX public catalog')
        if found['state']!='live':raise ValueError('Instrument is not live on OKX')
        return found
    def start(self,instrument,language,mode='full',note='',prior_id=None,holding_horizon='1d',strategy_mode='standard',trader_level=None):
        self.verify_selection(instrument)
        if language not in {'zh','en'} or mode not in {'full','quick'}:raise ValueError('Invalid research options')
        if not isinstance(note,str) or len(note)>400:raise ValueError('Note must be at most 400 characters')
        if holding_horizon not in {'1h','4h','12h','1d','1w','1mo','3mo','1y'}:raise ValueError('Invalid holding horizon')
        if strategy_mode not in {'standard','one_usdt_simulation'}:raise ValueError('Invalid strategy mode')
        if trader_level not in {None,'novice','experienced'}:raise ValueError('Invalid trader level')
        previous=self.repo.load(prior_id) if prior_id else None
        if previous and previous.instrument_id!=instrument:raise ValueError('Reassessment instrument mismatch')
        job_id=secrets.token_hex(12)
        job={'job_id':job_id,'instrument_id':instrument,'market_type':instrument_type(instrument),
             'created_at':utc_now(),'status':'queued','phase':'QUEUED','research_id':None,
             'roles':{},'events':[],'error':None,'prior_research_id':prior_id}
        with self.lock:self.jobs[job_id]=job
        self.journal('research_requested',job_id=job_id,instrument_id=instrument,market_type=job['market_type'],
                     language=language,mode=mode,note=note,prior_research_id=prior_id,
                     holding_horizon=holding_horizon,strategy_mode=strategy_mode,trader_level=trader_level)
        def progress(state):
            with self.lock:
                current=self.jobs[job_id]
                current['research_id']=state.research_id
                current['status']='running'
                current['phase']=state.phase
                active=set()
                for event in state.events:
                    if event.get('kind')=='agent_started':active.add(event.get('agent_id'))
                    elif event.get('kind') in {'agent_result','agent_failed'}:active.discard(event.get('agent_id'))
                current['roles']={r:('running' if r in active else state.results[r].status if r in state.results else 'waiting') for r in state.required_roles}
                current['events']=[{'kind':e.get('kind'),'timestamp':e.get('timestamp'),'agent_id':e.get('agent_id'),
                                    'phase':e.get('phase'),'status':e.get('status')} for e in state.events[-35:]]
        def run():
            with self.lock:self.jobs[job_id]['status']='running'
            try:
                cfg=load_config(self.config.data_dir)
                coordinator=Coordinator(cfg)
                state=coordinator.research(instrument,mode=mode,engine='codex',language=language,prior_state=previous,on_progress=progress,
                                           holding_horizon=holding_horizon,strategy_mode=strategy_mode,trader_level=trader_level,note=note)
                with self.lock:
                    self.jobs[job_id].update(status='done',phase=state.phase,research_id=state.research_id)
                self.journal('research_completed',job_id=job_id,research_id=state.research_id,
                             instrument_id=instrument,phase=state.phase,decision=state.decision)
            except Exception as exc:
                with self.lock:self.jobs[job_id].update(status='failed',error=str(exc)[:300])
                self.journal('research_failed',job_id=job_id,instrument_id=instrument,error=str(exc)[:300])
        Thread(target=run,name='atlas-ui-'+job_id,daemon=True).start()
        return job
    def job(self,job_id):
        if not JOB.fullmatch(job_id):raise KeyError('Invalid job ID')
        with self.lock:
            if job_id not in self.jobs:raise KeyError('Job not found')
            return json.loads(json.dumps(self.jobs[job_id]))


def handler_for(app:Dashboard):
    class Handler(BaseHTTPRequestHandler):
        server_version='ATLAS-Local/0.6'
        def log_message(self,format,*args):
            # Avoid logging URL fragments or private request payloads.
            if self.path.startswith('/api/'):return
            super().log_message(format,*args)
        def _send(self,status,body,content_type='application/json; charset=utf-8'):
            payload=(json.dumps(redact(body),ensure_ascii=False,allow_nan=False).encode() if isinstance(body,(dict,list)) else body)
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-src blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(payload)
        def _authorized(self):
            return hmac.compare_digest(self.headers.get('X-ATLAS-Token',''),app.token)
        def _local_host(self):
            # A loopback bind alone does not prevent browser DNS rebinding.
            return self.headers.get('Host','')==f'127.0.0.1:{self.server.server_port}'
        def _error(self,status,message):self._send(status,{'error':str(message)[:300]})
        def _route(self):return urlparse(self.path)
        def do_GET(self):
            if not self._local_host():return self._error(403,'Local host required')
            path=self._route().path
            if path in {'/','/index.html','/app.css','/app.js','/icon.svg'}:
                filename='index.html' if path in {'/','/index.html'} else path[1:]
                file=STATIC/filename
                if not file.is_file():return self._error(404,'Asset missing')
                ctype={'index.html':'text/html; charset=utf-8','app.css':'text/css; charset=utf-8','app.js':'text/javascript; charset=utf-8','icon.svg':'image/svg+xml'}[filename]
                return self._send(200,file.read_bytes(),ctype)
            if path=='/api/health':return self._send(200,{'status':'ok','local_only':True,'time':utc_now()})
            if not path.startswith('/api/') or not self._authorized():return self._error(403,'Local session token required')
            try:
                query=parse_qs(self._route().query)
                if path=='/api/bootstrap':
                    cfg=load_config(app.config.data_dir)
                    return self._send(200,{'profile':{'language':cfg.language,'capital_usdt':cfg.capital_usdt,
                                                       'primary_instruments':cfg.primary_instruments,
                                                       'positions_status':cfg.positions_status,
                                                       'positions_confirmed_at':cfg.positions_confirmed_at,
                                                       'trader_level':cfg.trader_level},
                                           'history':app.repo.list(limit=30),'roles':ROLES,'roles_en':ROLES_EN,'dependencies':DEPENDENCIES,
                                           'server_time':utc_now(),'read_only':True})
                if path=='/api/instruments':return self._send(200,app.instruments(query.get('type',['SPOT'])[0]))
                if path=='/api/history':return self._send(200,app.repo.list(limit=100))
                if path=='/api/journal':return self._send(200,app.journal_entries())
                if path.startswith('/api/jobs/'):
                    return self._send(200,app.job(path.removeprefix('/api/jobs/')))
                match=re.fullmatch(r'/api/research/(atlas_[0-9a-f]{16})',path)
                if match:return self._send(200,compact_state(app.repo.load(match.group(1))))
                match=re.fullmatch(r'/api/reports/(atlas_[0-9a-f]{16})/(zh|en)/(html|md|svg)',path)
                if match:
                    rid,language,fmt=match.groups();record=app.repo.load(rid)
                    audience=query.get('audience',[record.trader_level])[0]
                    if audience not in {'novice','experienced'}:raise ValueError('Invalid report audience')
                    suffix={'html':'.html','md':'.md','svg':'.svg'}[fmt]
                    name=('market.' if fmt=='svg' else 'report.')+language+suffix
                    file=app.repo.root/'reports'/rid/name
                    if not file.is_file():return self._error(404,'Report not ready')
                    ctype={'html':'text/html; charset=utf-8','md':'text/markdown; charset=utf-8','svg':'image/svg+xml'}[fmt]
                    if fmt in {'html','md'}:
                        from atlas.reporting.reports import render_markdown,render_html
                        md=render_markdown(record,language,audience)
                        content=(render_html(record,md,language) if fmt=='html' else md).encode()
                    else:content=file.read_bytes()
                    if fmt=='html':
                        # Embed the local chart so a tokenless image subrequest is never needed.
                        chart=app.repo.root/'reports'/rid/('market.'+language+'.svg')
                        if chart.is_file():
                            image='data:image/svg+xml;base64,'+base64.b64encode(chart.read_bytes()).decode()
                            content=content.replace(('market.'+language+'.svg').encode(),image.encode())
                    return self._send(200,content,ctype)
                return self._error(404,'Unknown endpoint')
            except KeyError as exc:return self._error(404,exc)
            except (ValueError,TypeError) as exc:return self._error(400,exc)
            except Exception:return self._error(502,'Data source unavailable; retry later')
        def do_POST(self):
            if not self._local_host():return self._error(403,'Local host required')
            path=self._route().path
            if not path.startswith('/api/') or not self._authorized():return self._error(403,'Local session token required')
            origin=self.headers.get('Origin')
            expected=f'http://127.0.0.1:{self.server.server_port}'
            if origin and origin!=expected:return self._error(403,'Origin mismatch')
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16_384:raise ValueError('Invalid request length')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('JSON object required')
                if path=='/api/profile':
                    from atlas.cli import initialize_profile
                    markets=body.get('markets',[])
                    if not isinstance(markets,list) or any(not isinstance(x,str) for x in markets):raise ValueError('Invalid market list')
                    args=Namespace(language=body.get('language'),capital_usdt=body.get('capital_usdt'),
                                   markets=','.join(markets),no_open_positions=body.get('no_open_positions') is True,
                                   trader_level=body.get('trader_level'))
                    result=initialize_profile(args,load_config(app.config.data_dir))
                    app.journal('profile_updated',language=result['profile']['language'],primary_instruments=result['profile']['primary_instruments'])
                    return self._send(200,result)
                if path=='/api/audience':
                    level=body.get('trader_level')
                    if level not in {'novice','experienced'}:raise ValueError('Invalid trader level')
                    cfg=load_config(app.config.data_dir)
                    cfg.trader_level=level
                    path_cfg=app.config.data_dir/'config.json'
                    current=json.loads(path_cfg.read_text()) if path_cfg.exists() else {}
                    current['trader_level']=level
                    fd,temp=tempfile.mkstemp(prefix='.atlas-profile-',dir=app.config.data_dir)
                    try:
                        with os.fdopen(fd,'w') as handle:json.dump(current,handle,ensure_ascii=False,indent=2);handle.write('\n')
                        os.chmod(temp,0o600);os.replace(temp,path_cfg)
                    finally:
                        if os.path.exists(temp):os.unlink(temp)
                    app.journal('audience_updated',trader_level=level)
                    return self._send(200,{'trader_level':level})
                if path=='/api/research':
                    inst=body.get('instrument_id')
                    if not isinstance(inst,str):raise ValueError('Instrument required')
                    return self._send(202,app.start(inst,body.get('language','zh'),body.get('mode','full'),body.get('note',''),
                                                     holding_horizon=body.get('holding_horizon','1d'),strategy_mode=body.get('strategy_mode','standard'),
                                                     trader_level=body.get('trader_level')))
                if path=='/api/reassess':
                    rid=body.get('research_id')
                    if not isinstance(rid,str) or not RID.fullmatch(rid):raise ValueError('Valid prior research ID required')
                    state=app.repo.load(rid)
                    return self._send(202,app.start(state.instrument_id,body.get('language',state.language),state.mode,'',rid,
                                                     holding_horizon=state.holding_horizon,strategy_mode=state.strategy_mode,
                                                     trader_level=body.get('trader_level',state.trader_level)))
                return self._error(404,'Unknown endpoint')
            except (ValueError,TypeError,json.JSONDecodeError) as exc:return self._error(400,exc)
            except KeyError as exc:return self._error(404,exc)
            except Exception:return self._error(502,'Operation unavailable; review local logs')
    return Handler


def serve(config,port=0,open_browser=True):
    app=Dashboard(config)
    server=ThreadingHTTPServer(('127.0.0.1',port),handler_for(app))
    url=f'http://127.0.0.1:{server.server_port}/#token={app.token}'
    print(json.dumps({'url':url,'bind':'127.0.0.1','port':server.server_port,'data_dir':str(config.data_dir)},ensure_ascii=False),flush=True)
    if open_browser:webbrowser.open(url)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()
