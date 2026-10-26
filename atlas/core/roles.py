from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone
from atlas.core.state import AgentResult, Finding, Request

ROLES={
'fed':'研究美联储政策事实、发布时间与政策预期的缺口，不推断降息必涨。',
'macro':'研究官方宏观观测、流动性和收益率曲线，区分相关性、修订数据和实时可得信息。',
'news':'核验近期事件来源、发布日期与发生时间，去重并记录新旧信息及反证。',
'technical':'计算 15 分钟、一小时、日线、周线、月线已收盘指标并识别周期冲突。',
'entry_timing':'结合已收盘 15 分钟和一小时 K 线，核验入场条件、关键价位和失效条件；不下单。',
'sentiment':'结合资金费率、OI、价格与成交量研究拥挤风险，不用单项持仓数据判方向。',
'backtest':'独立量化回测、样本外检验、摩擦与不确定性评估。',
'btc_specialist':'专项研究 BTC 的已确认价格结构、波动和相对 ETH 强弱，区分描述与预测。',
'eth_specialist':'专项研究 ETH 的已确认价格结构、波动和相对 BTC 强弱，不伪造链上与生态指标。',
'risk_control':'独立评估数据新鲜度、关键位、账户敞口、单笔风险、交易规则和执行摩擦，向策略与首席审查提交否决或条件报告。',
'trading':'依据全部已确认研究形成多头、空头、观望条件，禁止执行订单。',
'chief':'主持交叉质询并保存重大分歧，禁止把研究分数称为获利概率。'}
ROLES_EN={
'fed':'Review official Federal Reserve policy events, timing, and missing market expectations.',
'macro':'Review official macro observations and their revision and release-time limits.',
'news':'Deduplicate recent source events and preserve publication versus occurrence time.',
'technical':'Calculate indicators on closed 15-minute, hourly, daily, weekly, and monthly bars and retain conflicts.',
'entry_timing':'Check entry timing using confirmed 15-minute and hourly bars, levels, and invalidation; never place orders.',
'sentiment':'Compare funding, open interest, and sentiment without assigning a direction from one reading.',
'backtest':'Compare predeclared rules on chronological out-of-sample data with explicit costs.',
'btc_specialist':'Analyze BTC price structure, volatility, and relative strength versus ETH from verified daily data.',
'eth_specialist':'Analyze ETH price structure, volatility, and relative strength versus BTC without inventing on-chain metrics.',
'risk_control':'Independently assess freshness, levels, exposure, trade risk, exchange rules, and friction; provide a veto or conditional assessment.',
'trading':'State conditional long, short, and wait scenarios without placing orders.',
'chief':'Retain contrary evidence and apply independent data and research gates.'}
ROLE_LIMITS_EN={
'fed':['An official statement is not a verified market-expectation surprise.'],
'macro':['Latest revised observations are not historical first-release vintages.','Unverified PMI, DXY, and global liquidity fields remain missing.'],
'news':['Publication and event occurrence may differ; unverified occurrence times remain unknown.','The available feeds are not comprehensive market-news coverage.'],
'technical':['Closed-bar indicators describe observed structure; warm-up and timeframe conflicts remain visible.'],
'entry_timing':['A closed-bar setup is a conditional observation, not a forecast or order authorization.'],
'sentiment':['One funding or open-interest observation cannot establish positioning direction or crowding.'],
'backtest':['The technical proxy is not a historical replay of the complete research committee.','Historical simulation is not a filled live trade.'],
'btc_specialist':['Relative BTC/ETH strength and realized volatility are descriptive, not win probabilities or market-cap dominance.'],
'eth_specialist':['Relative ETH/BTC strength is descriptive; on-chain usage, staking, and ecosystem metrics are unavailable unless separately verified.'],
'risk_control':['A stop is not a guaranteed fill; unknown portfolio exposure or exchange rules block an executable order plan.'],
'trading':['Scenarios are conditional research; account capital and live execution are unavailable.'],
'chief':['Research weights are not calibrated profit probabilities or institutional endorsement.']}
DEPENDENCIES={'fed':[], 'technical':[], 'entry_timing':['technical'], 'macro':['fed'], 'news':['fed'], 'backtest':['technical'],
              'btc_specialist':['technical','macro','news'],
              'eth_specialist':['technical','macro','news','btc_specialist'],
              'sentiment':['technical','news','macro'],
              'risk_control':['macro','fed','news','technical','entry_timing','sentiment','backtest','btc_specialist','eth_specialist'],
              'trading':['macro','fed','news','technical','entry_timing','sentiment','backtest','btc_specialist','eth_specialist','risk_control'],
              'chief':['macro','fed','news','technical','entry_timing','sentiment','backtest','btc_specialist','eth_specialist','risk_control','trading']}

class RoleWorker:
    def __init__(self,role,config): self.role=role;self.config=config
    def run(self,state):
        known=set(state.evidence)
        r=AgentResult(research_id=state.research_id,agent_id=self.role,asset=state.asset,instrument_id=state.instrument_id,task=ROLES[self.role],timeframes=state.timeframes,input_versions={k:state.results[k].version for k in DEPENDENCIES[self.role] if k in state.results})
        if self.role in state.results:r.version=state.results[self.role].version+1;r.revised_reason='依赖更新或审查返工；保留旧版本。'
        getattr(self,'_'+self.role)(state,r)
        r.summary_en=ROLES_EN[self.role]
        if not r.uncertainties_en:r.uncertainties_en=ROLE_LIMITS_EN[self.role]
        r.data_sources=sorted({state.evidence[e].source for e in r.evidence})
        r.data_timestamps=sorted({state.evidence[e].timestamp for e in r.evidence})
        if r.status=='complete':r.confidence.level='moderate'
        return r,{k:v for k,v in state.evidence.items() if k not in known}
    def ev(self,s,r,source,data,**kw):
        eid=s.add_evidence(source,data,agent=self.role,**kw);r.evidence.append(eid);return eid
    def fact(self,r,text,eid,direction='neutral',kind='fact',english=None):
        r.findings.append(Finding(claim=text,claim_en=english,evidence_ids=[eid],kind=kind,direction=direction))
    def _fed(self,s,r):
        events=s.snapshot.get('fed',[])
        for e in events[:8]:
            eid=self.ev(s,r,e.get('source','Federal Reserve'),e,url=e.get('source_url'),timestamp=e.get('published_at'))
            title=e.get('title','美联储公开发布')
            english=title if all(ord(ch)<128 for ch in title) else 'Official Federal Reserve release; see linked original source.'
            self.fact(r,title,eid,english=english)
        r.status='complete' if events else 'blocked'
        r.uncertainties=['官方公告不等同市场预期；本模式未自动读取 CME 利率定价、SEP 数表或比较完整声明措辞。','未获取可靠市场预期时不计算政策意外程度。']
        r.payload={'events':events[:8],'policy_path_probability':None,'interpretation':'事实归档，方向需要研究员交叉验证'}
        if events:
            for role in ['macro','news','technical','backtest','trading']:r.requests_to_other_agents.append(Request(to_agent=role,reason='检查最新官方政策事件对本模块假设的影响。',evidence_ids=r.evidence[:1]))
    def _macro(self,s,r):
        series=s.snapshot.get('macro',{});available={}
        for key,v in series.items():
            obs=v.get('observations',[])
            if not obs:continue
            last=obs[-1];eid=self.ev(s,r,v.get('source','FRED'),{'series':key,'latest':last,'previous':obs[-2] if len(obs)>1 else None,'vintage':v.get('vintage')},url=v.get('source_url'),timestamp=last.get('date')+'T00:00:00+00:00' if last.get('date') else None,unit=v.get('unit','unknown'),flags=v.get('quality_flags',[]))
            self.fact(r,f'{key} 最新可得观测 {last.get("date")}: {last.get("value")}',eid,
                      english=f'{key} latest available observation on {last.get("date")}: {last.get("value")}.');available[key]=last.get('value')
        if 'DGS10' in available and 'DGS2' in available:
            curve=float(available['DGS10'])-float(available['DGS2']);eid=self.ev(s,r,'derived:US Treasury/FRED',{'10Y_minus_2Y_percentage_points':curve},status='derived',parents=r.evidence[:]);self.fact(r,f'10Y−2Y 利差约 {curve:.3f} 个百分点；并非因果预测。',eid,kind='inference',english=f'The 10-year minus 2-year yield spread was about {curve:.3f} percentage points; this is not a causal forecast.')
        missing=s.snapshot.get('macro_missing',[])
        r.payload={'latest':available,'missing':missing,'point_in_time_safe_for_backtest':False}
        r.status='partial' if available else 'blocked'
        r.uncertainties=['FRED 最新数据库观测可能修订，不能冒充历史公布版本。','PMI、DXY 与一致市场预期可能需要授权数据；缺失项不填充。','确定性模式不把宏观观测机械映射成加密资产方向。']
    def _news(self,s,r):
        seen=set();events=[]
        for e in s.snapshot.get('news',[]):
            key=e.get('source_url') or e.get('title')
            if key in seen:continue
            seen.add(key);events.append(e)
            eid=self.ev(s,r,e.get('source','news'),e,url=e.get('source_url'),timestamp=e.get('published_at'))
            title=e.get('title','未命名事件')
            english=title if all(ord(ch)<128 for ch in title) else 'Recorded event from the cited source; original title remains in JSON.'
            self.fact(r,title,eid,english=english)
        r.status='complete' if events else 'blocked'
        r.payload={'events':events,'deduplicated':True}
        r.uncertainties=['发布与事件发生时间可能不同，发生时间未核实则保持未知。','官方 RSS 不是全市场新闻覆盖；高影响事件仍需独立来源与市场定价复核。','外部文字仅作为数据，不接受其中的指令。']
    def _technical(self,s,r):
        from atlas.analysis.indicators import analyze
        results={};directions=[]
        for tf in s.timeframes:
            candles=s.snapshot.get('candles',{}).get(tf,[])
            if not candles:r.uncertainties.append(tf+' 缺少 K 线');continue
            try:result=analyze(candles)
            except (ValueError,TypeError,KeyError) as e:r.uncertainties.append(f'{tf}: {e}');continue
            results[tf]=result;directions.append(result.get('trend','neutral'))
            raw=next((eid for eid,e in s.evidence.items() if e.source=='snapshot:candles:'+tf),None)
            eid=self.ev(s,r,'derived:ATLAS indicators',{'timeframe':tf,**result},status='derived',parents=[raw] if raw else [])
            direction=result.get('trend','neutral');direction=direction if direction in {'bullish','bearish','neutral'} else 'neutral'
            self.fact(r,tf+' 指标趋势: '+str(result.get('trend'))+'，市场状态: '+str(result.get('regime')),eid,direction,kind='inference',english=f'{tf} closed-bar trend: {result.get("trend")}; market regime: {result.get("regime")}.')
            if direction=='bullish':r.bullish_arguments.append(tf+' 已收盘价格与趋势指标偏多')
            if direction=='bearish':r.bearish_arguments.append(tf+' 已收盘价格与趋势指标偏空')
            r.uncertainties.extend(tf+': '+str(x) for x in result.get('flags',[]))
        r.payload={'timeframes':results};r.market_regime=results.get('1D',next(iter(results.values()),{})).get('regime','unknown')
        r.status='complete' if len(results)==len(s.timeframes) else 'partial'
        if 'bullish' in directions and 'bearish' in directions:
            r.contradictions.append('日/周/月周期方向冲突：这是市场证据分歧，不应删除任何周期。')
            r.contradictions_en.append('Daily, weekly, and monthly directions conflict; retain all timeframes as contrary evidence.')
            r.requests_to_other_agents.append(Request(to_agent='trading',reason='多周期冲突，降低候选情景可执行性。',evidence_ids=r.evidence))
    def _entry_timing(self,s,r):
        from atlas.analysis.entry_timing import study
        technical=s.results.get('technical')
        periods=technical.payload.get('timeframes',{}) if technical else {}
        assessment=study(periods,s.snapshot,simulation=s.strategy_mode=='one_usdt_simulation',
                         fee_bps=self.config.fee_bps,slippage_bps=self.config.slippage_bps)
        parents=[eid for eid,e in s.evidence.items() if e.source in {'snapshot:candles:15m','snapshot:candles:1H','snapshot:ticker'}]
        eid=self.ev(s,r,'derived:ATLAS entry timing',assessment,status='derived',parents=parents)
        r.payload=assessment
        if assessment['signal']=='closed_bar_setup':
            label='观察做多' if assessment['direction']=='LONG_WATCH' else '观察做空'
            self.fact(r,f'15 分钟与一小时已收盘指标同向：{label}；参考入场 {assessment["entry_reference"]:.6g}，失效 {assessment["invalidation"]:.6g}。仍须风险审查。',eid,
                      kind='inference',english=f'Closed 15m and 1H indicators align for {assessment["direction"]}; conditional entry {assessment["entry_reference"]:.6g}, invalidation {assessment["invalidation"]:.6g}. Risk review still applies.')
        else:self.fact(r,'15 分钟与一小时未共同确认入场条件，等待。',eid,kind='inference',english='The closed 15m and 1H bars do not jointly confirm entry; wait.')
        r.status='complete' if periods.get('15m') and periods.get('1H') else 'partial'
        r.uncertainties=['本结果只描述已收盘 K 线，不预测下一根；实时盘口、滑点与合约强平价未核实。']
    def _sentiment(self,s,r):
        d=s.snapshot.get('derivatives',{});eid=self.ev(s,r,'OKX derivatives',d,url='https://www.okx.com/docs-v5/en/')
        for k in ['funding_rate','open_interest','mark_price','basis']:
            if d.get(k) is not None:self.fact(r,f'{k}: {d[k]}（不可单独判定价格方向）',eid,english=f'{k}: {d[k]}; this observation alone does not determine future price direction.')
        
        for capability,entry in s.snapshot.get('sentiment_data',{}).items():
            sid=self.ev(s,r,entry.get('source','OKX analytics'),entry,url='https://www.okx.com/docs-v5/en/')
            self.fact(r,capability+' 已获取，保留原始结构；不转换为获利概率。',sid,english=f'{capability} raw analytics were obtained and retained; they are not converted into a profit probability.')
        r.status='partial' if d or s.snapshot.get('sentiment_data') else 'blocked'
        r.payload={'derivatives':d,'direction':'neutral','crowding':'unconfirmed','social_sentiment_available':False}
        r.uncertainties=['当前 OI 单点不说明多头或空头新增；历史变化和价格联动需要同时评估。','无可靠社媒、期权偏斜或私有聪明钱数据时不生成综合拥挤概率。']
        r.requests_to_other_agents.append(Request(to_agent='trading',reason='不得把正资金费率或 OI 上升解释成确定交易方向。',evidence_ids=[eid]))
    def _backtest(self,s,r):
        from atlas.analysis.backtesting import compare_strategies
        if s.instrument_id.rsplit('-',1)[-1].isdigit():
            r.status='blocked';r.uncertainties=['交割合约的到期、换月及保证金路径尚未在回测中建模；不能以现货规则替代。'];return
        candles=s.snapshot.get('candles',{}).get('1D',[])
        if len(candles)<120:
            r.status='blocked';r.uncertainties=['不足 120 根日线，禁止产生可靠历史胜率结论。'];return
        try:
            comparison=compare_strategies(candles,fee_bps=self.config.fee_bps,slippage_bps=self.config.slippage_bps,spread_bps=self.config.spread_bps,risk_fraction=self.config.risk_fraction,instrument_type='SWAP' if s.instrument_id.endswith('-SWAP') else 'SPOT')
            r.payload=comparison
            eid=self.ev(s,r,'derived:ATLAS chronological backtest',comparison,status='derived',parents=[e for e,v in s.evidence.items() if v.source=='snapshot:candles:1D'])
            self.fact(r,'在相同费用、资本约束与时间划分下完成 Baseline 和 ATLAS 技术代理回测。',eid,kind='inference',english='Baseline and ATLAS technical-proxy simulations used the same costs, capital constraints, and chronological split.')
            r.status='partial';r.uncertainties=['ATLAS 技术代理不等于完整宏观/消息研究委员会策略，不能据此声称完整 ATLAS 获得优势。','本次快照历史长度有限；五年事件研究需单独下载历史与验证事件发布时间。','没有真实成交记录，只有历史模拟结果。']
        except (ValueError,TypeError,KeyError,ArithmeticError) as e:r.status='blocked';r.uncertainties=['回测无法运行: '+str(e)]
    def _btc_specialist(self,s,r):self._specialist(s,r,'BTC')
    def _eth_specialist(self,s,r):self._specialist(s,r,'ETH')
    def _specialist(self,s,r,asset):
        from atlas.analysis.specialists import summarize_specialist
        markets=s.snapshot.get('specialist_markets',{})
        try:quant=summarize_specialist(asset,markets)
        except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
            quant={'status':'unavailable','asset':asset,'peer':'ETH' if asset=='BTC' else 'BTC','reason':str(exc)}
        r.payload={'quant':quant,'specialist_asset':asset,'scope':'confirmed 30-day BTC/ETH relative market structure; no prediction or on-chain inference'}
        if quant['status']!='available':
            r.status='blocked';r.uncertainties=[asset+' 专项数据不足：'+quant.get('reason','未知原因')]
            r.uncertainties_en=[asset+' specialist data unavailable: '+quant.get('reason','unknown reason')+'.']
            return
        own=markets[asset];peer=quant['peer']
        parents=[eid for eid,e in s.evidence.items() if e.source in {'snapshot:specialist:'+asset+':1D','snapshot:specialist:'+peer+':1D'}]
        timestamp=datetime.fromtimestamp(quant['latest_available_at']/1000,timezone.utc).isoformat()
        eid=self.ev(s,r,'derived:ATLAS '+asset+' specialist',quant,status='derived',parents=parents,
                    instrument=own['instrument_id'],timestamp=timestamp,unit='returns and annualized volatility')
        own_ret=quant['own_return_30d'];spread=quant['relative_return_spread_30d']
        self.fact(r,f'{asset} 最近 30 个已确认 UTC 日区间收益 {own_ret:+.2%}；历史描述，不是未来预测。',eid,
                  kind='inference',english=f'{asset} returned {own_ret:+.2%} over 30 aligned confirmed UTC daily intervals; this describes history, not a forecast.')
        self.fact(r,f'{asset} 相对 {peer} 的 30 日收益差 {spread:+.2%}；两种资产合约类型均为 {quant["market_type"]}。',eid,
                  kind='inference',english=f'{asset} minus {peer} 30-day return spread was {spread:+.2%}; both instruments use {quant["market_type"]} market data.')
        r.market_regime='relative_outperformance' if spread>0 else 'relative_underperformance' if spread<0 else 'relative_neutral'
        r.status='complete'
        r.uncertainties=['相对强弱、历史波动与回撤不构成获利概率；只使用同类型现货或永续的已确认日线。']
        if asset=='BTC':r.uncertainties.append('缺少已核验的市值占比、链上流量和矿工持仓，不推断 BTC dominance。')
        else:r.uncertainties.append('缺少已核验的质押、链上使用和生态数据，不从价格推断 ETH 基本面。')
    def _trading(self,s,r):
        tech=s.results.get('technical');tfs=tech.payload.get('timeframes',{}) if tech else {};day=tfs.get('1D',{})
        ticker=s.snapshot.get('ticker',{});last=ticker.get('last');metrics=day.get('metrics',{})
        def number(value):
            try:return float(value) if value is not None and math.isfinite(float(value)) else None
            except (ValueError,TypeError):return None
        last=number(last);support=number(day.get('support'));resistance=number(day.get('resistance'));atr=number(metrics.get('atr',metrics.get('atr14',metrics.get('atr_14'))))
        plans={'long':{'status':'unavailable'},'short':{'status':'unavailable'},'wait':{'conditions':['未完成样本外的完整委员会策略验证','关键证据缺失、周期冲突或重要事件窗口时等待'],'decision':'WAIT_FOR_CONFIRMATION'}}
        if last and support and resistance and support<resistance:
            buffer=atr*.1 if atr and atr>0 else (resistance-support)*.02
            entry=resistance+buffer;stop=support-buffer;risk=entry-stop
            plans['long']={'status':'conditional_research_only','trigger':'日线收盘突破结构阻力且成交量确认','entry_reference':entry,'invalidation':stop,'illustrative_target':entry+2*risk,'gross_reward_risk':2,'target_basis':'按2R风险距离构造的算术情景，不是预测','historical_edge_verified':False}
            short_entry=support-buffer;short_stop=resistance+buffer;short_risk=short_stop-short_entry
            plans['short']={'status':'conditional_research_only','trigger':'日线收盘跌破结构支撑；确认反抽失败且借贷/合约可用','entry_reference':short_entry,'invalidation':short_stop,'illustrative_target':max(0,short_entry-2*short_risk),'gross_reward_risk':min(2,short_entry/short_risk) if short_risk else None,'target_basis':'支撑失守的独立结构情景，目标受价格非负约束','historical_edge_verified':False}
        risk=s.results.get('risk_control')
        r.payload={'scenarios':plans,'risk_assessment':risk.payload.get('assessment',{}) if risk else {},'order_execution':'not_implemented','eligible_for_order':False,'position_size':None,'fees_bps':self.config.fee_bps,'slippage_bps':self.config.slippage_bps,'funding':'历史资金费率未传入时不得声称已计入'}
        r.evidence=list(dict.fromkeys(e for a in DEPENDENCIES['trading'] if a in s.results for e in s.results[a].evidence))
        r.findings=[Finding(claim='候选方案仅为条件研究；完整历史优势未验证，当前观望。',claim_en='Candidates are conditional research only; full historical edge is unverified, so wait for confirmation.',evidence_ids=r.evidence[:6],kind='hypothesis')]
        r.status='partial';r.uncertainties=['风险金额与仓位需要用户资本和风险预算；未获取私有账户资产。','现货与永续价格不得混用；止损并不保证按触发价成交。']
    def _risk_control(self,s,r):
        from atlas.analysis.risk import assess_risk
        assessment=assess_risk(s,s.budget.get('risk_policy',{}))
        parents=list(dict.fromkeys(e for role in DEPENDENCIES['risk_control'] if role in s.results for e in s.results[role].evidence))
        eid=self.ev(s,r,'derived:ATLAS risk assessment',assessment,status='derived',parents=parents[:30])
        r.payload={'assessment':assessment,'veto':not assessment['preliminary_entry_eligible'],'recipients':['trading','chief']}
        r.findings=[Finding(claim='风险控制评估完成；当前存在 '+str(len(assessment['blockers']))+' 项入场阻断条件。',
                            claim_en='Risk assessment complete; '+str(len(assessment['blockers']))+' entry blockers remain.',
                            evidence_ids=[eid],kind='inference')]
        r.status='complete'
        r.uncertainties=['未经账户查询的持仓声明会过期；止损单的最终成交价可能偏离触发价。','风险预算只限制预估损失，不保证实际最大损失。']
        r.requests_to_other_agents=[Request(to_agent='trading',reason='依据风险评估决定候选方案能否进入执行讨论。',evidence_ids=[eid]),
                                    Request(to_agent='chief',reason='独立复核风险否决项，保留等待结论。',evidence_ids=[eid])]
    def _chief(self,s,r):
        r.evidence=list(dict.fromkeys(e for k,v in s.results.items() for e in v.evidence))
        r.contradictions=list(dict.fromkeys(x for v in s.results.values() for x in v.contradictions))
        r.contradictions_en=list(dict.fromkeys(x for v in s.results.values() for x in v.contradictions_en))
        partial=[a for a in DEPENDENCIES['chief'] if a not in s.results or s.results[a].status!='complete']
        r.payload={'incomplete_roles':partial,'weights':self.config.weights,'weighted_score':None,'win_probability':None,'decision':'WAIT_FOR_CONFIRMATION' if not partial else 'INSUFFICIENT_DATA','reason':'证据完整度与策略验证限制；不强制产生交易信号','unique_evidence_count':len(r.evidence)}
        r.findings=[Finding(claim='研究结论受到缺失数据与未经完整验证的策略限制。',claim_en='Research conclusions are constrained by missing data and unvalidated full-strategy performance.',evidence_ids=r.evidence[:8],kind='inference')]
        r.status='partial' if partial else 'complete';r.uncertainties=['研究权重是初始配置，未经样本外优化或概率校准。','机构式研究流程不代表任何机构认可或投资业绩。']
