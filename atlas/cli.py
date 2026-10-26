from __future__ import annotations
import argparse,json,os,platform,sys,tempfile
from pathlib import Path
from atlas.config import load_config
from atlas.core.storage import Repository
from atlas.security import redact

def emit(obj):print(json.dumps(redact(obj),ensure_ascii=False,indent=2,allow_nan=False,default=str))
def add_data(p):p.add_argument('--data-dir',default=argparse.SUPPRESS,help='Local data directory; never the skill install folder')
def add_data_inputs(p):
    add_data(p);p.add_argument('--fixture',type=Path);p.add_argument('--offline',action='store_true',default=None);p.add_argument('--years',type=int,default=5)
def parser():
    p=argparse.ArgumentParser(prog='atlas',description='Local evidence-based read-only OKX research');p.add_argument('--version',action='version',version='ATLAS 0.6.0');add_data(p)
    sp=p.add_subparsers(dest='command',required=True)
    ui=sp.add_parser('ui',help='Launch the loopback-only visual research floor');add_data(ui)
    ui.add_argument('--port',type=int,default=0);ui.add_argument('--no-open',action='store_true')
    init=sp.add_parser('init',help='Create or update the local nonsecret research profile');add_data(init)
    init.add_argument('--language',choices=['zh','en']);init.add_argument('--capital-usdt',type=float);init.add_argument('--markets',help='Comma-separated OKX instrument IDs');init.add_argument('--no-open-positions',action='store_true')
    d=sp.add_parser('doctor');add_data(d);d.add_argument('--network',action='store_true')
    r=sp.add_parser('research');r.add_argument('instrument');add_data_inputs(r);r.add_argument('--mode',choices=['quick','full'],default='full');r.add_argument('--timeframes',default='15m,1H,1D,1W,1M');r.add_argument('--engine',choices=['codex','deterministic','host','llm'],default='codex');r.add_argument('--lang',choices=['zh','en'])
    reassess=sp.add_parser('reassess',help='Rerun live research against a prior key-level report');reassess.add_argument('research_id');add_data(reassess);reassess.add_argument('--lang',choices=['zh','en']);reassess.add_argument('--engine',choices=['codex','deterministic','host','llm'],default='codex')
    b=sp.add_parser('backtest');b.add_argument('--asset',required=True);add_data_inputs(b);b.add_argument('--funding-file',type=Path)
    e=sp.add_parser('event-study');e.add_argument('--asset',required=True);e.add_argument('--event',required=True);e.add_argument('--events',type=Path);add_data_inputs(e)
    h=sp.add_parser('history');add_data(h);h.add_argument('--asset');h.add_argument('--days',type=int);hs=h.add_subparsers(dest='history_action')
    for action in ['show','versions','delete']:
        hp=hs.add_parser(action);hp.add_argument('research_id');add_data(hp)
    hp=hs.add_parser('compare');hp.add_argument('a');hp.add_argument('b');add_data(hp)
    hp=hs.add_parser('backup');add_data(hp)
    hp=hs.add_parser('outcomes');hp.add_argument('--asset');hp.add_argument('--days',type=int,default=90);add_data(hp)
    for action in ['audit','task-list','finalize']:
        a=sp.add_parser(action);a.add_argument('research_id');add_data(a)
    a=sp.add_parser('submit');a.add_argument('research_id');a.add_argument('--file',type=Path,required=True);a.add_argument('--revise',action='store_true');add_data(a)
    a=sp.add_parser('task-draft');a.add_argument('research_id');a.add_argument('--agent',required=True);a.add_argument('--output',type=Path,required=True);add_data(a)
    a=sp.add_parser('task-run');a.add_argument('research_id');a.add_argument('--agent',required=True);add_data(a)
    a=sp.add_parser('export');a.add_argument('research_id');a.add_argument('--format',choices=['markdown','json','html'],default='markdown');a.add_argument('--lang',choices=['zh','en']);add_data(a)
    a=sp.add_parser('config');a.add_argument('action',choices=['show']);add_data(a)
    a=sp.add_parser('capabilities');a.add_argument('--refresh',action='store_true');add_data(a)
    a=sp.add_parser('mcp');add_data(a)
    a=sp.add_parser('outcome');a.add_argument('research_id');a.add_argument('--horizon-days',type=int,default=7);add_data(a)
    return p

def doctor(config,network=False):
    from atlas.integrations.skill_adapter import OfficialSkillAdapter,executable_env
    import shutil
    status=OfficialSkillAdapter(config).status();info={'atlas':'0.6.0','python':platform.python_version(),'os':platform.system(),'architecture':platform.machine(),'node':shutil.which('node',path=executable_env()['PATH']),'npm':shutil.which('npm',path=executable_env()['PATH']),'git':shutil.which('git'),'codex_cli':shutil.which('codex'),'data_dir':str(config.data_dir),'profile_complete':bool(config.capital_usdt and config.primary_instruments),'auth':status,'default_permissions':'READ_ONLY','live_orders':'not_implemented','llm_configured':bool(config.llm_model and os.environ.get('ATLAS_LLM_API_KEY')),'mcp_sdk':False,'network_test':'not_requested'}
    try:import mcp;info['mcp_sdk']=True
    except ImportError:pass
    if network:
        from atlas.providers import DataService
        svc=DataService(config)
        try:
            data,meta=svc.api.ticker('ETH-USDT');info['network_test']={'success':bool(data),'metadata':meta}
        except Exception as e:info['network_test']={'success':False,'error':str(e)}
        finally:svc.close()
    return info

def historical(config,asset):
    from atlas.providers import DataService
    svc=DataService(config)
    try:return svc.history(asset,'1D',years=getattr(config,'_years',5))
    finally:svc.close()

def initialize_profile(args,config):
    from atlas.config import Config
    from atlas.core.state import now
    from atlas.integrations.skill_adapter import validate_instrument
    if sys.stdin.isatty():
        language=args.language or input('Language / 语言 [zh/en] (zh): ').strip() or 'zh'
        capital=args.capital_usdt if args.capital_usdt is not None else float(input('Trading capital in USDT / 本金（USDT）: ').strip())
        markets=args.markets or input('Primary markets / 主做交易对 (comma-separated): ').strip()
    else:
        if args.language is None or args.capital_usdt is None or not args.markets:
            raise ValueError('Noninteractive init requires --language, --capital-usdt and --markets')
        language,capital,markets=args.language,args.capital_usdt,args.markets
    instruments=[validate_instrument(x.strip().upper()) for x in markets.replace('，',',').split(',') if x.strip()]
    if not instruments:raise ValueError('At least one primary instrument is required')
    original=config.model_dump(mode='json',exclude={'data_dir'})
    original.update({'language':language,'capital_usdt':capital,'primary_instruments':instruments,
                     'trader_level':getattr(args,'trader_level',None) or config.trader_level,
                     'positions_status':'none_reported' if args.no_open_positions else 'unknown',
                     'positions_confirmed_at':now() if args.no_open_positions else None})
    validated=Config(**original,data_dir=config.data_dir)
    root=config.data_dir;root.mkdir(parents=True,exist_ok=True)
    path=root/'config.json'
    # Keep the existing nonsecret settings while updating the onboarding fields.
    current=json.loads(path.read_text()) if path.exists() else {}
    current.update({k:getattr(validated,k) for k in ('language','capital_usdt','primary_instruments','positions_status','positions_confirmed_at','trader_level')})
    fd,temp=tempfile.mkstemp(prefix='.atlas-config-',dir=root)
    try:
        with os.fdopen(fd,'w') as handle:
            json.dump(current,handle,ensure_ascii=False,indent=2);handle.write('\n')
        os.chmod(temp,0o600);os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'configured':True,'profile':{k:getattr(validated,k) for k in ('language','capital_usdt','primary_instruments','positions_status','positions_confirmed_at','trader_level')},'config_path':str(path),'default_permissions':'READ_ONLY'}

def main(argv=None):
    args=parser().parse_args(argv);a=vars(args)
    try:
        config=load_config(a.get('data_dir'),offline=True if a.get('fixture') else a.get('offline'),fixture=a.get('fixture'))
        command=args.command
        if command=='ui':
            if not 0<=args.port<=65535:raise ValueError('port must be 0..65535')
            from atlas.web.server import serve
            serve(config,args.port,not args.no_open);return 0
        if command=='init':emit(initialize_profile(args,config));return 0
        if command=='config':emit(config.model_dump(mode='json'));return 0
        if command=='doctor':emit(doctor(config,args.network));return 0
        if command=='mcp':
            from atlas.integrations.mcp_server import serve
            serve(config);return 0
        if command=='capabilities':
            from atlas.integrations.skill_adapter import OfficialSkillAdapter
            emit(OfficialSkillAdapter(config).discover(args.refresh));return 0
        repo=Repository(config.data_dir)
        if command=='research':
            from atlas.core.coordinator import Coordinator
            selected_language=args.lang or config.language
            st=Coordinator(config,repo=repo).research(args.instrument,args.timeframes.split(','),args.mode,args.engine,selected_language)
            from atlas.reporting.reports import write_reports
            reports=write_reports(st,repo,selected_language) if st.completed_at else {'tasks':str(repo.root/'reports'/st.research_id/'tasks')}
            emit({'research_id':st.research_id,'phase':st.phase,'decision':st.decision,'engine':st.engine,'data_mode':st.snapshot.get('mode'),'reports':reports,'issues':[i.model_dump() for i in st.issues],'agents':{k:v.version for k,v in st.results.items()}});return 0
        if command=='reassess':
            previous=repo.load(args.research_id)
            from atlas.core.coordinator import Coordinator
            st=Coordinator(config,repo=repo).research(previous.instrument_id,previous.timeframes,previous.mode,args.engine,args.lang or config.language,prior_state=previous)
            from atlas.reporting.reports import write_reports
            reports=write_reports(st,repo,st.language) if st.completed_at else {'tasks':str(repo.root/'reports'/st.research_id/'tasks')}
            emit({'research_id':st.research_id,'prior_research_id':previous.research_id,'phase':st.phase,'decision':st.decision,'reports':reports,'rechecked_from_new_snapshot':True});return 0
        if command in {'backtest','event-study'}:
            from atlas.providers import DataService
            service=DataService(config)
            try:
                history=service.history(args.asset,'1D',years=args.years)
                if command=='backtest':
                    from atlas.analysis.backtesting import compare_strategies
                    if not ('-USDT' in args.asset or '-USDC' in args.asset):raise ValueError('backtest supports linear USDT/USDC spot or swap; inverse/options unsupported')
                    result=compare_strategies(history['data'],fee_bps=config.fee_bps,slippage_bps=config.slippage_bps,spread_bps=config.spread_bps,risk_fraction=config.risk_fraction,funding_events=json.loads(args.funding_file.read_text()) if args.funding_file else None,instrument_type='SWAP' if args.asset.endswith('-SWAP') else 'SPOT')
                else:
                    from atlas.analysis.event_study import study_events
                    found={'events':json.loads(args.events.read_text())} if args.events else service.events(args.event,start_year=__import__('datetime').datetime.now().year-args.years)
                    events=found.get('events',[]);repo.add_events(events);result=study_events(history['data'],events);result['event_source_status']={k:v for k,v in found.items() if k!='events'}
            finally:service.close()
            from atlas.core.state import ResearchState,now
            st=ResearchState(asset=args.asset.split('-')[0],instrument_id=args.asset,phase='INSUFFICIENT_DATA',decision='INSUFFICIENT_DATA',mode='quick',completed_at=now(),snapshot={'mode':history.get('mode','live'),'instrument_id':args.asset,'retrieved_at':now(),'candles':{'1D':history['data']},'history_provenance':history});st.backtest=result;st.event(command,source_coverage_complete=history['complete']);repo.save(st)
            output={'research_id':st.research_id,'sample_kind':'offline_fixture' if config.fixture else 'historical_observations','history':{k:v for k,v in history.items() if k!='data'},'result':result}
            root=repo.root/'reports'/st.research_id;root.mkdir(parents=True,exist_ok=True);(root/'analysis.json').write_text(json.dumps(redact(output),ensure_ascii=False,indent=2,allow_nan=False));emit(output);return 0
        if command=='history':
            action=args.history_action
            if not action:emit(repo.list(args.asset,args.days))
            elif action=='show':emit(repo.load(args.research_id).model_dump(mode='json'))
            elif action=='compare':emit(repo.compare(args.a,args.b))
            elif action=='versions':emit(repo.versions(args.research_id))
            elif action=='backup':emit({'backup':str(repo.backup())})
            elif action=='delete':emit(repo.delete(args.research_id))
            elif action=='outcomes':
                with repo.connect() as db:out=db.execute('SELECT research_id,horizon_days,observed_at,data FROM outcomes').fetchall()
                eligible={x['research_id'] for x in repo.list(args.asset,args.days,limit=10000)}
                emit({'observations':[json.loads(x[3]) for x in out if x[0] in eligible],'real_trading_win_rate':None,'note':'Research outcome observations, not actual filled trades'})
            return 0
        st=repo.load(args.research_id)
        if command=='audit':
            from atlas.core.reviewer import RiskResearchAudit
            issues=RiskResearchAudit().review(st)
            content_path=repo.root/'reports'/st.research_id/'report.json'
            integrity=repo.check_report_hash(st.research_id,'json',content_path.read_text()) if content_path.exists() else False
            st.event('re_audit',report_file_integrity=integrity,issues=[i.model_dump() for i in issues]);repo.save(st)
            emit({'research_id':st.research_id,'approved':not any(i.severity in {'error','critical'} for i in issues) and integrity,'saved_phase':st.phase,'report_file_integrity':integrity,'issues':[i.model_dump() for i in issues]});return 0
        if command=='export':
            from atlas.reporting.reports import write_reports
            emit({'research_id':st.research_id,'path':write_reports(st,repo,args.lang)[args.format]});return 0
        if command in {'task-list','task-run','task-draft','submit','finalize'}:
            from atlas.core.coordinator import Coordinator
            c=Coordinator(config,repo=repo)
            if command=='finalize':
                st=c.finish_host(st.research_id);emit({'research_id':st.research_id,'phase':st.phase,'decision':st.decision})
            elif command=='task-draft':
                args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(c.draft(st.research_id,args.agent),ensure_ascii=False,indent=2,allow_nan=False));emit({'draft':str(args.output)})
            elif command=='task-list':emit({'research_id':st.research_id,'ready':c.graph.ready(st),'tasks':str(c.write_host_tasks(st)),'results':{k:v.version for k,v in st.results.items()}})
            else:
                st=c.run_host_task(st.research_id,args.agent) if command=='task-run' else c.submit(st.research_id,json.loads(args.file.read_text()),args.revise)
                emit({'research_id':st.research_id,'phase':st.phase,'ready':c.graph.ready(st),'results':{k:v.version for k,v in st.results.items()}})
            return 0
        if command=='outcome':
            from atlas.core.outcomes import observe_outcome
            emit(observe_outcome(st,config,repo,args.horizon_days));return 0
    except KeyboardInterrupt:print('Research cancelled; completed stages remain in local archive.',file=sys.stderr);return 130
    except Exception as exc:
        emit({'error':str(redact(str(exc))),'error_type':type(exc).__name__,'write_executed':False});return 2

if __name__=='__main__':raise SystemExit(main())
