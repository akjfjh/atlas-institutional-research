from __future__ import annotations
from datetime import datetime,timezone
import math
from atlas.core.state import ReviewIssue
from atlas.core.roles import DEPENDENCIES

def parse_time(v):
    if isinstance(v,(int,float)):return float(v)/1000 if abs(v)>1e11 else float(v)
    dt=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()

def issue(severity,role,problem,correctable=False,evidence=None):
    return ReviewIssue(severity=severity,responsible_agent=role,problem=problem,required_correction='重新获取、核实或计算相关证据；保留原始记录与修订理由。',correctable=correctable,evidence=evidence or [])
class DataIntegrityValidator:
    def review(self,state):
        out=[];snap=state.snapshot;now=datetime.now(timezone.utc).timestamp()
        if snap.get('instrument_id')!=state.instrument_id:out.append(issue('critical','data','数据资产标识不一致'))
        for tf in state.timeframes:
            rows=snap.get('candles',{}).get(tf,[])
            if not rows:out.append(issue('error','data',tf+' 关键 K 线缺失'));continue
            minimum={'1D':60,'1W':52,'1M':24,'4H':60}.get(tf,30)
            if len(rows)<minimum:out.append(issue('error','data',f'{tf} 仅有 {len(rows)} 根，少于研究最小值 {minimum}'))
            times=[]
            for c in rows:
                try:
                    vals=[float(c[k]) for k in ['open','high','low','close','volume']];t=int(c['ts']);times.append(t)
                    if not all(math.isfinite(x) for x in vals) or min(vals[:4])<=0 or vals[4]<0:raise ValueError('nonfinite/nonpositive price')
                    if c['high']<max(c['open'],c['close'],c['low']) or c['low']>min(c['open'],c['close'],c['high']):raise ValueError('OHLC bounds')
                    if not c.get('confirm',False):raise ValueError('未收盘 K 线混入确认分析')
                    if t/1000>now+300:raise ValueError('未来 K 线')
                except (KeyError,ValueError,TypeError) as e:out.append(issue('critical','data',tf+' K线不合法: '+str(e)));break
            try:
                latest=rows[-1];available=latest.get('available_at')
                if available is None:
                    from atlas.providers.okx_public_api import close_time
                    available=close_time(latest['ts'],tf)
                close_ts=parse_time(available)
                if close_ts>now+300:out.append(issue('critical','data',tf+' 已确认K线可用时间仍在未来'))
                max_age={'1D':2*86400,'1W':9*86400,'1M':35*86400,'4H':8*3600}.get(tf,2*86400)
                if snap.get('mode')=='live' and now-close_ts>max_age:out.append(issue('error','data',tf+' 最新已收盘K线已过时'))
            except (KeyError,ValueError,TypeError):out.append(issue('error','data',tf+' 缺少有效收盘可用时间'))
            if times!=sorted(set(times)):out.append(issue('critical','data',tf+' K线重复或时间顺序错误'))
        ticker=snap.get('ticker',{})
        if not isinstance(ticker.get('last'),(int,float)) or not math.isfinite(float(ticker['last'])) or float(ticker['last'])<=0:out.append(issue('error','data','当前价格缺失'))
        elif snap.get('mode')=='live':
            try:
                age=now-parse_time(ticker['ts'])
                if age>300:out.append(issue('error','data',f'当前报价已过时 {age:.0f} 秒，不可用于当前入场研究'))
                if age<-300:out.append(issue('critical','data','报价时间在未来'))
            except (KeyError,ValueError,TypeError):out.append(issue('error','data','报价没有有效时间戳'))
        elif snap.get('mode')!='live':out.append(issue('error','data','离线/缓存/fixture 不能用于当前入场判断'))
        if {'btc_specialist','eth_specialist'} & set(state.required_roles):
            markets=snap.get('specialist_markets',{})
            for asset in ('BTC','ETH'):
                market=markets.get(asset,{})
                if market.get('status')!='available':
                    out.append(issue('error',asset.lower()+'_specialist',asset+' 专项行情缺失或不可用'))
                    continue
                if not str(market.get('instrument_id','')).startswith(asset+'-'):
                    out.append(issue('critical',asset.lower()+'_specialist',asset+' 专项资产标识不一致'))
                rows=market.get('candles_1d',[])
                times=[]
                for bar in rows:
                    try:
                        ts=int(bar['ts']);available=int(bar['available_at']);close=float(bar['close']);times.append(ts)
                        if not bar.get('confirm') or ts/1000>now+300 or available/1000>now+300 or available<ts+86400000 or not math.isfinite(close) or close<=0:raise ValueError('invalid confirmed daily bar')
                    except (KeyError,TypeError,ValueError):
                        out.append(issue('critical',asset.lower()+'_specialist',asset+' 专项日线无效'))
                        break
                if times!=sorted(set(times)):out.append(issue('critical',asset.lower()+'_specialist',asset+' 专项日线重复或乱序'))
                if snap.get('mode')=='live':
                    try:
                        last=float(market['ticker']['last'])
                        if not math.isfinite(last) or last<=0:raise ValueError('invalid ticker')
                        if now-parse_time(market['ticker']['ts'])>300:out.append(issue('error',asset.lower()+'_specialist',asset+' 专项报价已过时'))
                    except (KeyError,TypeError,ValueError):out.append(issue('error',asset.lower()+'_specialist',asset+' 专项报价缺少有效时间戳'))
                    if rows and now-parse_time(rows[-1]['available_at'])>2*86400:
                        out.append(issue('error',asset.lower()+'_specialist',asset+' 专项最新日线已过时'))
        for group in ['news','fed']:
            for e in snap.get(group,[]):
                if not e.get('source') or not str(e.get('source_url','')).startswith('https://'):out.append(issue('error',group,'事件缺少可追溯来源URL'))
                try:
                    if parse_time(e['published_at'])>parse_time(e.get('observed_at',snap['retrieved_at']))+300:out.append(issue('critical',group,'新闻/政策发布时间晚于观察时间'))
                except (KeyError,ValueError,TypeError):out.append(issue('error',group,'事件缺少有效来源时间戳'))
        return out

class RiskResearchAudit:
    def review(self,state):
        out=DataIntegrityValidator().review(state)
        needed=state.required_roles
        for role in needed:
            r=state.results.get(role)
            if not r:out.append(issue('error',role,'缺少研究结果'));continue
            if r.status=='complete' and (not r.evidence or not r.findings):out.append(issue('critical',role,'研究结果没有可核实的结论与证据',True))
            if r.status!='complete':out.append(issue('error',role,'研究部分完成或缺少关键证据'))
            required={dep:state.results[dep].version for dep in DEPENDENCIES[role] if dep in state.results}
            for message in state.messages:
                if message['recipient']==role and message['sender']!=role and message['sender'] in state.results:
                    sender=message['sender']
                    required[sender]=max(required.get(sender,0),message['sender_version'])
            for dep,v in required.items():
                actual=r.input_versions.get(dep,0)
                if actual<v or (dep in DEPENDENCIES[role] and actual!=v):
                    out.append(issue('error',role,'使用过期上游版本: '+dep,True))
            for dep,v in r.input_versions.items():
                if dep not in state.results or v>state.results[dep].version:
                    out.append(issue('error',role,'使用不存在的上游版本: '+dep,True))
            for f in r.findings:
                if not f.evidence_ids:out.append(issue('critical',role,'无证据结论: '+f.claim,True))
                if any(e not in state.evidence for e in f.evidence_ids):out.append(issue('critical',role,'引用不存在的证据',True))
            if state.schema_version in {'1.1','1.2','1.3'} and (not r.summary_en or any(
                any('\u3400'<=ch<='\u9fff' for ch in f.claim) and not f.claim_en for f in r.findings)):
                out.append(issue('warning',role,'中英双语结论不完整；英文报告保留原文索引而不猜译'))
            if r.confidence.probability is not None:out.append(issue('critical',role,'未经校准的概率或胜率'))
        for eid,e in state.evidence.items():
            if e.source.startswith('snapshot:candles:'):
                import hashlib,json
                tf=e.source.split(':',2)[2]
                actual=hashlib.sha256(json.dumps(state.snapshot.get('candles',{}).get(tf,[]),sort_keys=True,allow_nan=False).encode()).hexdigest()
                if e.data.get('sha256')!=actual:out.append(issue('critical','data','原始K线证据哈希不匹配',evidence=[eid]))
            if e.source.startswith('snapshot:specialist:') and e.source.endswith(':1D'):
                import hashlib,json
                asset=e.source.split(':')[2]
                rows=state.snapshot.get('specialist_markets',{}).get(asset,{}).get('candles_1d',[])
                actual=hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest()
                if e.data.get('sha256')!=actual:out.append(issue('critical',asset.lower()+'_specialist','专项原始K线证据哈希不匹配',evidence=[eid]))
            if any(p not in state.evidence for p in e.parent_ids):out.append(issue('critical','data','证据父节点丢失',evidence=[eid]))
            if e.status=='host_attested':out.append(issue('warning','data','宿主提交证据由宿主核实，未由引擎自动验证来源内容',evidence=[eid]))
        technical=state.results.get('technical')
        if technical:
            missing=set(state.timeframes)-set(technical.payload.get('timeframes',{}))
            if missing:out.append(issue('critical','technical','技术结果缺少周期: '+','.join(sorted(missing)),True))
            from atlas.analysis.indicators import analyze
            def same(a,b):
                if isinstance(a,bool) or isinstance(b,bool):return a is b
                if isinstance(a,(int,float)) and isinstance(b,(int,float)):
                    return math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-7,abs_tol=1e-8)
                if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(same(v,b[k]) for k,v in a.items())
                if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
                return a==b
            for tf,data in technical.payload.get('timeframes',{}).items():
                try:
                    expected=analyze(state.snapshot['candles'][tf])
                    if not same(expected,data):out.append(issue('critical','technical','技术指标/趋势/结构与原始 K 线复算不一致: '+tf,True))
                except (ValueError,TypeError,KeyError):out.append(issue('critical','technical','技术结果无法从原始K线复算: '+tf,True))
            if technical.contradictions:out.append(issue('warning','trading','多周期方向冲突必须保留，并在情景中采用等待确认。'))
        backtest=state.results.get('backtest')
        if backtest and backtest.payload:
            from atlas.analysis.backtesting import compare_strategies
            try:
                params=state.budget.get('backtest_parameters',{'fee_bps':10,'slippage_bps':5,'spread_bps':2,'risk_fraction':.005})
                expected=compare_strategies(state.snapshot['candles']['1D'],**params,instrument_type='SWAP' if state.instrument_id.endswith('-SWAP') else 'SPOT')
                if expected!=backtest.payload:out.append(issue('critical','backtest','回测结果与原始数据及预注册参数复算不一致',True))
            except (KeyError,ValueError,TypeError) as e:out.append(issue('critical','backtest','回测无法复算: '+str(e),True))
        from atlas.analysis.specialists import summarize_specialist
        for asset in ('BTC','ETH'):
            role=asset.lower()+'_specialist';result=state.results.get(role)
            if not result:continue
            try:
                expected=summarize_specialist(asset,state.snapshot.get('specialist_markets',{}))
                if result.payload.get('quant')!=expected:
                    out.append(issue('critical',role,'专项收益/波动/相对强弱与原始日线复算不一致',True))
            except (KeyError,ValueError,TypeError,ArithmeticError):
                out.append(issue('critical',role,'专项数据无法复算',True))
        risk=state.results.get('risk_control')
        if risk:
            from atlas.analysis.risk import assess_risk
            expected=assess_risk(state,state.budget.get('risk_policy',{}))
            recorded=risk.payload.get('assessment',{})
            if 'assessment_version' not in recorded and state.schema_version in {'1.2','1.3'}:
                expected.pop('assessment_version',None)
                for key in ('distance_above_support_pct','distance_below_resistance_pct','nearest_level'):
                    expected['watch'].pop(key,None)
            if recorded!=expected or risk.payload.get('veto')==expected['preliminary_entry_eligible']:
                out.append(issue('critical','risk_control','风险评估与冻结行情及风险预算复算不一致',True))
        if state.mode=='full':
            macro=state.snapshot.get('macro',{})
            if not any(v.get('observations') for v in macro.values()):out.append(issue('error','macro','宏观官方观测缺失'))
            if state.snapshot.get('macro_missing'):out.append(issue('error','macro','要求的宏观指标覆盖不完整'))
            if not state.snapshot.get('fed'):out.append(issue('error','fed','美联储政策证据缺失'))
            if not state.snapshot.get('news'):out.append(issue('error','news','新闻/事件证据缺失'))
        # Deduplicate repeated gate messages, preserve all genuinely different conflicts.
        unique={ (x.severity,x.responsible_agent,x.problem):x for x in out }
        return list(unique.values())
