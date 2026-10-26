from __future__ import annotations
import hashlib,html,json,math,re
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from atlas.core.roles import ROLES_EN,ROLE_LIMITS_EN
from atlas.security import redact

def clean(text):return str(text).replace('|','\\|').replace('\n',' ').replace('`','\\`')
def cjk(text):return bool(re.search(r'[\u3400-\u9fff]',str(text)))
def english_issue(problem):
    text=str(problem)
    for original,translated in [
        ('研究部分完成或缺少关键证据','Research is partial or lacks essential evidence.'),
        ('要求的宏观指标覆盖不完整','Required macroeconomic coverage is incomplete.'),
        ('多周期方向冲突','Timeframe directions conflict; retain wait-for-confirmation.'),
        ('宿主提交证据','Host-attested source content was not independently refetched by the engine.'),
        ('当前报价已过时','The current ticker is stale and cannot support a current entry.'),
        ('离线/缓存/fixture','Offline, cached, or fixture data cannot support a current entry.'),
        ('缺少研究结果','A required research role has not submitted a result.'),
        ('使用过期上游版本','A result consumed an outdated upstream version.'),
        ('专项行情缺失或不可用','Required BTC/ETH specialist market data is missing.'),
        ('专项收益/波动/相对强弱','Specialist measures differ from recomputed BTC/ETH source candles.'),
        ('中英双语结论不完整','Bilingual findings are incomplete; the English report retains a source-language pointer instead of guessing a translation.')]:
        if original in text:return translated
    return text if not cjk(text) else 'Original-language review issue retained in report.zh.md and report.json.'

RISK_REASONS={
 'non_live_data':('不是实时数据','Data are not live'),
 'ticker_not_fresh':('报价时间不足以支持当前判断','Ticker timestamp is stale or invalid'),
 'price_unavailable':('当前报价缺失','Current ticker is unavailable'),
 'levels_unavailable':('支撑或阻力无法核实','Support or resistance is unavailable'),
 'instrument_not_in_profile':('交易对不在已配置的主做币种中','Instrument is outside the configured primary list'),
 'spot_usdt_only':('当前风险方案仅适用于 USDT 现货','This risk profile supports USDT spot only'),
 'capital_unset':('本金尚未配置','Trading capital is not configured'),
 'portfolio_exposure_unconfirmed':('已有持仓和挂单情况未在最近 24 小时内确认','Positions and open orders were not confirmed within 24 hours'),
 'breakout_unconfirmed':('尚无已收盘日线突破阻力且成交量高于前 20 日均值的确认','No closed daily breakout with volume above the preceding 20-day average'),
 'daily_trend_not_bullish':('日线趋势尚未确认向上','Daily trend is not confirmed bullish'),
 'price_too_far_from_entry':('报价已高于参考入场价超过 1%，不追价','Ticker is more than 1% above the reference entry; do not chase'),
 'timeframe_conflict':('多周期信号冲突','Timeframe signals conflict'),
 'edge_unverified':('完整委员会策略的样本外优势未获验证','Full committee out-of-sample edge is unverified'),
 'committee_not_approved':('最终研究审查未批准','Final research review is not approved'),
 'risk_officer_veto':('风险控制员否决当前开仓','Risk officer vetoes entry'),
 'risk_officer_not_run':('快速扫描未运行完整风控，不能开仓','Quick scan did not run a full risk review; entry is blocked'),
 'ticker_stale_at_publication':('发布时报价已过时','Ticker was stale at report publication'),
 'exchange_order_rules_or_size_unavailable':('交易规则或最小下单量不满足','Exchange order rules or minimum size are unavailable or unmet'),
}

def risk_reason(code,en):
    if code.startswith('incomplete_'):
        return ('研究员结果未完成：' if not en else 'Incomplete research role: ')+code.removeprefix('incomplete_')
    return RISK_REASONS.get(code,(code,code))[1 if en else 0]

def format_utc(value):
    if isinstance(value,(int,float)):
        stamp=float(value)/1000 if value>1e11 else float(value)
        return datetime.fromtimestamp(stamp,timezone.utc).isoformat(timespec='seconds')
    return value

def observation_time(value,language):
    if value is None:return '—'
    try:
        stamp=float(value)/1000 if float(value)>1e11 else float(value)
        moment=datetime.fromtimestamp(stamp,timezone.utc)
    except (TypeError,ValueError,OverflowError):
        try:moment=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        except ValueError:return str(value)
    if moment.tzinfo is None:moment=moment.replace(tzinfo=timezone.utc)
    if language=='zh':return moment.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S（北京时间）')
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def market_label(value,en):
    if en:return value
    return {'inside_range':'支撑与阻力之间','above_resistance':'高于阻力','below_support':'低于支撑',
            'support':'支撑','resistance':'阻力','bullish':'偏多','bearish':'偏空','neutral':'中性','unknown':'未知','unavailable':'不可用'}.get(value,value)
def svg_chart(state,language='zh'):
    c=state.snapshot.get('candles',{}).get('1D',[])[-240:]
    title=f'{state.instrument_id} · {state.snapshot.get("mode","unknown")} · '+('confirmed daily closes' if language=='en' else '已确认日线收盘价')
    if not c:return '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="320"><text x="30" y="50">'+('No validated daily candles available' if language=='en' else '缺少已核验日线')+'</text></svg>'
    values=[float(x['close']) for x in c];low,high=min(values),max(values);span=max(high-low,high*.001)
    points=' '.join(f'{60+i*840/max(1,len(c)-1):.1f},{250-(v-low)*170/span:.1f}' for i,v in enumerate(values))
    caution='Historical observations, not a forecast. Latest closed candle is not the live ticker.' if language=='en' else '历史观测，不是预测；最新已收盘日线不等于实时报价。'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="340" viewBox="0 0 960 340"><rect width="960" height="340" fill="#101b2d" rx="16"/><g font-family="Arial,sans-serif" fill="#dde5f3"><text x="40" y="42" font-size="20">{html.escape(title)}</text><text x="40" y="76" font-size="13">{html.escape(caution)}</text><polyline points="{points}" fill="none" stroke="#54d7b7" stroke-width="3"/><text x="60" y="286">min {low:.4g}</text><text x="740" y="286">max {high:.4g}</text><text x="60" y="315">{len(c)} bars · UTC · raw evidence retained in report.json</text></g></svg>'''

def render_markdown(state,language='zh',audience=None):
    """Short, audience-aware report. Complete evidence remains in report.json."""
    if language not in {'zh','en'}:raise ValueError('language must be zh or en')
    audience=audience or state.trader_level
    if audience not in {'novice','experienced'}:raise ValueError('invalid report audience')
    en=language=='en'
    review=state.codex_review if state.codex_review.get('status')=='complete' else {}
    if state.engine=='codex' and not review:raise ValueError('Codex research review is incomplete')
    codex_roles={item.get('agent_id'):item for item in review.get('role_reviews',[])}
    from atlas.analysis.risk import final_decision
    d=final_decision(state)
    watch=d.get('watch') or {}
    timing=state.results.get('entry_timing')
    timing=timing.payload if timing else {}
    sim=timing.get('one_usdt_simulation')
    report_time=observation_time(watch.get('ticker_as_of'),language)
    title='ATLAS market brief' if en else 'ATLAS 行情简报'
    lines=[f'# {title}',f'\n**{state.instrument_id} · {state.holding_horizon} · {state.research_id}**',
           '\n'+(('Experienced' if audience=='experienced' else 'Beginner') if en else ('资深交易员版' if audience=='experienced' else '新手版')),
           '\n## '+('In brief' if en else '一句话结论')]
    if en:
        lines.append('\n'+(f'Observed {watch.get("current_price") or "—"} at {report_time}. '+('The research gate permits a conditional manual plan.' if d['can_open'] else 'Do not open a new position now.')))
    else:
        lines.append('\n'+(f'{report_time} 看到的价格是 {watch.get("current_price") or "—"}。'+('条件满足，可复核后手动分批挂单。' if d['can_open'] else '目前不要开新仓。')))
    if review:
        direction={'UP':('上行','upward'),'DOWN':('下行','downward'),'SIDEWAYS':('横盘','sideways'),'UNCLEAR':('不明朗','unclear')}[review['market_direction']][1 if en else 0]
        summary_key=('summary_simple_en' if en else 'summary_simple_zh') if audience=='novice' else ('summary_en' if en else 'summary_zh')
        lines.append('\n**'+('Codex research judgment' if en else 'Codex 研读判断')+'：'+direction+'。** '+(review.get(summary_key) or review['summary_en' if en else 'summary_zh']))
        if audience=='experienced':
            lines.append('\n'+(('Opposing evidence: ' if en else '相反证据：')+review['contrary_en' if en else 'contrary_zh']))
            lines.append('\n'+review['reasoning_en' if en else 'reasoning_zh'])
    lines += ['\n'+('The quote is a time snapshot. Refresh research before any action.' if en else '价格只是当时的快照；再次决策前必须重新获取行情。'),
              '\n## '+('Watch and entry conditions' if en else '接下来观察什么')]
    support,resistance=watch.get('support'),watch.get('resistance')
    if en:
        lines.append(f'\n- Watch support **{support or "—"}** and resistance **{resistance or "—"}** (prior 20 closed daily bars).')
        lines.append('\n- A price touch alone is insufficient. Check a closed candle, volume, 15m and 1H agreement, then rerun risk review.')
    else:
        lines.append(f'\n- 重点看 **{support or "—"}** 和 **{resistance or "—"}**，它们来自前 20 根已收盘日 K 的高低点。')
        lines.append('\n- 到价还不等于能买卖；等 K 线收盘、成交量与 15 分钟和 1 小时方向一起确认，再重新判断。')
    if timing.get('signal')=='closed_bar_setup':
        direction=('long' if timing.get('direction')=='LONG_WATCH' else 'short') if en else ('观察做多' if timing.get('direction')=='LONG_WATCH' else '观察做空')
        lines.append('\n- '+(f'Conditional {direction} setup: entry reference {timing.get("entry_reference"):.6g}; invalidation {timing.get("invalidation"):.6g}; illustrative 2R exit {timing.get("illustrative_exit"):.6g}. This is not an order.' if en else f'入场研究：{direction}；参考位置 {timing.get("entry_reference"):.6g}，走错时重新评估的位置 {timing.get("invalidation"):.6g}，2R 算术离场参考 {timing.get("illustrative_exit"):.6g}。这不是挂单指令。'))
    else:
        entry=d.get('risk',{}).get('entry_reference')
        stop=d.get('risk',{}).get('stop_reference')
        if entry and stop and state.strategy_mode!='one_usdt_simulation':
            lines.append('\n- '+(f'Unconfirmed long scenario: entry reference {entry:.6g}, invalidation {stop:.6g}; no order size while blocked.' if en else f'未确认的做多观察方案：价格到 {entry:.6g} 附近时复查，跌到 {stop:.6g} 说明这个方案可能错了。目前不生成挂单数量。'))
        if state.strategy_mode=='one_usdt_simulation':
            lines.append('\n- '+('No 15m/1H setup: there is no valid quick-entry or exit level now.' if en else '15 分钟和 1 小时没有共同形成机会：现在没有可用的快进快出入场价和离场价。'))
        if state.strategy_mode!='one_usdt_simulation':
            lines.append('\n- '+('15m and 1H entry conditions are not jointly confirmed; current direction: wait.' if en else '15 分钟与 1 小时没有共同确认入场；当前方向：等待。'))
    if d.get('reasons'):
        lines.append('\n- '+(('Main blockers: ' if en else '主要拦截原因：')+'; '.join(risk_reason(x,en) for x in d['reasons'][:3])))
    if state.prior_research_id:
        lines.append('\n'+(f'Reassessment of prior research `{state.prior_research_id}`; new market evidence controls this result.' if en else f'重新判断前次研究 `{state.prior_research_id}`；以这次新取的行情为准。'))
    if sim:
        lines += ['\n## '+('1 USDT high-leverage study' if en else '1U 高杠杆模拟'),
                  '\n'+('Hypothetical 1 USDT margin at 50x/100x means 50/100 USDT notional. A 2%/1% adverse move loses roughly 1 USDT before costs; liquidation can occur earlier. No liquidation price, exchange minimum size, funding, mark price, or account tier was verified. Execution disabled.' if en else '假设只放 1 USDT 保证金，50 倍/100 倍对应约 50/100 USDT 名义仓位。反向波动约 2%/1%，毛亏损就接近 1 USDT，强平可能更早。实际强平价、最小下单量、资金费、标记价格和账户档位未核验；此模式禁止下单。')]
    lines += ['\n## '+('Who did what' if en else '每位研究员做了什么'),
              '\n| '+('Role | Work | Result' if en else '职务 | 做了什么 | 得到什么')+' |',
              '|---|---|---|']
    simple_zh={'fed':'核对美联储官方消息','macro':'核对经济数据','news':'核对新闻发布时间','technical':'看各周期已收盘 K 线','entry_timing':'对照 15 分钟和 1 小时入场条件','sentiment':'看合约情绪数据','backtest':'检查历史模拟','btc_specialist':'专看 BTC','eth_specialist':'专看 ETH','risk_control':'检查本金、持仓和交易风险','trading':'整理条件方案','chief':'复核全部结论'}
    simple_en={'fed':'Checked official Fed releases','macro':'Checked macro data','news':'Checked event timing','technical':'Read closed candles by timeframe','entry_timing':'Compared 15m and 1H entry conditions','sentiment':'Checked derivatives sentiment','backtest':'Checked historical simulation','btc_specialist':'Reviewed BTC','eth_specialist':'Reviewed ETH','risk_control':'Checked capital, exposure, and risk','trading':'Drafted conditional scenarios','chief':'Audited conclusions'}
    names_zh={'fed':'美联储研究员','macro':'宏观研究员','news':'新闻研究员','technical':'技术研究员','entry_timing':'入场时机研究员','sentiment':'情绪研究员','backtest':'回测研究员','btc_specialist':'BTC 专项研究员','eth_specialist':'ETH 专项研究员','risk_control':'独立风控员','trading':'策略决策员','chief':'首席审查员'}
    names_en={'fed':'Fed researcher','macro':'Macro researcher','news':'News researcher','technical':'Technical analyst','entry_timing':'Entry timing researcher','sentiment':'Sentiment analyst','backtest':'Backtest analyst','btc_specialist':'BTC specialist','eth_specialist':'ETH specialist','risk_control':'Risk officer','trading':'Strategy lead','chief':'Chief reviewer'}
    statuses_zh={'complete':'已完成','partial':'证据不全','blocked':'无法核实','waiting':'未开始'}
    statuses_en={'complete':'Completed','partial':'Evidence incomplete','blocked':'Unavailable','waiting':'Not started'}
    for role in state.required_roles:
        result=state.results.get(role)
        status=result.status if result else 'waiting'
        codex_role=codex_roles.get(role,{})
        work_key=('work_simple_en' if en else 'work_simple_zh') if audience=='novice' else ('work_en' if en else 'work_zh')
        result_key=('result_simple_en' if en else 'result_simple_zh') if audience=='novice' else ('result_en' if en else 'result_zh')
        job=codex_role.get(work_key) or codex_role.get('work_en' if en else 'work_zh') or (simple_en if en else simple_zh).get(role,role)
        name=names_en.get(role,role) if en else names_zh.get(role,role)
        if codex_role:
            outcome=codex_role.get(result_key) or codex_role['result_en' if en else 'result_zh']
        elif audience=='experienced' and result and result.findings:
            finding=result.findings[0]
            outcome=(finding.claim_en or statuses_en[status]) if en else finding.claim
        elif role=='fed' and result:outcome=(f'{len(result.payload.get("events",[]))} official releases checked' if en else f'核对了 {len(result.payload.get("events",[]))} 条官方消息')
        elif role=='macro' and result:outcome=(f'{len(result.payload.get("latest",{}))} macro series checked' if en else f'核对了 {len(result.payload.get("latest",{}))} 项经济数据')
        elif role=='news' and result:outcome=(f'{len(result.payload.get("events",[]))} events checked' if en else f'核对了 {len(result.payload.get("events",[]))} 条新闻')
        elif role=='technical' and result:
            hour=result.payload.get('timeframes',{}).get('1H',{}).get('trend')
            outcome=(f'1H trend: {hour or "unavailable"}' if en else '1 小时方向：'+{'bullish':'偏上','bearish':'偏下','neutral':'不明显'}.get(hour,'数据不足'))
        elif role=='entry_timing':
            outcome=('Closed-bar setup; risk review still applies' if timing.get('signal')=='closed_bar_setup' else 'Wait: 15m/1H not aligned or data missing') if en else ('条件形态出现，仍需风控复核' if timing.get('signal')=='closed_bar_setup' else '等待：周期未共同确认或数据不足')
        elif role=='risk_control':
            outcome=('Entry permitted' if d['can_open'] else 'Entry blocked') if en else ('允许复核挂单' if d['can_open'] else '阻止开仓')
        elif role in {'btc_specialist','eth_specialist'} and result:
            value=result.payload.get('quant',{}).get('own_return_30d')
            outcome=(f'Observed 30-day return {value:+.1%}' if en else f'过去 30 天实际涨跌 {value:+.1%}') if isinstance(value,(int,float)) else (statuses_en if en else statuses_zh)[status]
        elif role=='trading':outcome=('Conditional scenarios; no order' if en else '只整理条件方案，未下单')
        elif role=='backtest' and result and result.payload:outcome=('Technical proxy simulation only' if en else '仅完成技术规则的历史模拟')
        else:outcome=(statuses_en if en else statuses_zh)[status]
        lines.append('| '+' | '.join(clean(x) for x in (name,job,outcome))+' |')
    if audience=='experienced':
        ind=timing.get('indicators') or {}
        lines += ['\n## '+('Entry indicators' if en else '入场指标'),
                  '\n| 15m RSI14 | 15m volume vs 20 bars | 1H ADX14 | 15m trend | 1H trend |',
                  '|---:|---:|---:|---|---|',
                  '| '+' | '.join(clean(ind.get(k,'—')) for k in ('15m_rsi14','15m_volume_vs_20_bar_mean','1h_adx14','15m_trend','1h_trend'))+' |']
    lines.append('\n'+('Full raw evidence, versions and source timestamps: report.json in the local archive. No order was placed.' if en else '原始证据、版本和来源时间保存在本地 report.json；本次没有下单。'))
    lines.append('\n## '+('Final assessment at publication' if en else '报告发布时的最终判断'))
    direction_label={'UP':('偏上','upward'),'DOWN':('偏下','downward'),'SIDEWAYS':('横盘','sideways'),'UNCLEAR':('不明朗','unclear')}
    model_direction=(('; Codex view ' if en else '；Codex 判断')+direction_label[review['market_direction']][1 if en else 0]) if review else ''
    lines.append('\n'+(f'At {report_time}, observed price {watch.get("current_price") or "—"}{model_direction}; '+('conditional manual entry may be reviewed' if d['can_open'] else 'do not open now')+f'. Watch {support or "—"} / {resistance or "—"}; request a fresh reassessment at either level.' if en else f'{report_time} 观测价 {watch.get("current_price") or "—"}{model_direction}；'+('可复核条件挂单' if d['can_open'] else '当前不可以开仓')+f'。重点观察 {support or "—"} / {resistance or "—"}，到价后重新判断。'))
    return '\n'.join(lines)+'\n'

def render_html(state,markdown,language='zh'):
    from markdown_it import MarkdownIt
    rendered=MarkdownIt('commonmark',{'html':False}).enable('table').render(markdown)
    lang='en' if language=='en' else 'zh-CN'
    return '<!doctype html><html lang="'+lang+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ATLAS '+html.escape(state.research_id)+'</title><style>body{font:16px/1.75 system-ui;background:#f5f7fb;color:#17263d;max-width:1120px;margin:36px auto;padding:24px}main{background:#fff;padding:36px;border-radius:18px}h1,h2,h3{line-height:1.3;color:#12243d}h2{margin-top:2.2em;border-bottom:2px solid #d4e1ef;padding-bottom:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f8;padding:18px;border-radius:10px;font-size:13px}img{width:100%;border-radius:16px}table{border-collapse:collapse;display:block;overflow-x:auto;font-size:14px}td,th{border:1px solid #cfdae7;padding:8px;text-align:left}th{background:#e7eff8}blockquote{border-left:5px solid #c58924;padding:12px;background:#fff5df;margin:0}a{color:#146f99}code{overflow-wrap:anywhere}</style><main>'+rendered+'</main></html>'

def write_reports(state,repo,language=None):
    requested=language or state.language
    if requested not in {'zh','en'}:raise ValueError('language must be zh or en')
    root=repo.root/'reports'/state.research_id;root.mkdir(parents=True,exist_ok=True)
    markdown={lang:render_markdown(state,lang) for lang in ('zh','en')}
    pages={lang:render_html(state,markdown[lang],lang) for lang in ('zh','en')}
    content={'report.json':json.dumps(redact(state.model_dump(mode='json')),ensure_ascii=False,indent=2,allow_nan=False),
             'report.md':markdown[requested],'report.html':pages[requested],
             'report.zh.md':markdown['zh'],'report.en.md':markdown['en'],
             'report.zh.html':pages['zh'],'report.en.html':pages['en'],
             'market.svg':svg_chart(state,requested),'market.zh.svg':svg_chart(state,'zh'),'market.en.svg':svg_chart(state,'en')}
    for filename,value in content.items():
        (root/filename).write_text(value)
        if filename.endswith(('.json','.md','.html')):
            key={'report.json':'json','report.md':'markdown','report.html':'html'}.get(filename,filename)
            repo.hash_report(state.research_id,key,value)
    if state.completed_at:
        digest=hashlib.sha256(''.join(content.values()).encode()).hexdigest()[:12]
        archive=root/'versions'/f'v{state.version}-{requested}-{digest}';archive.mkdir(parents=True,exist_ok=True)
        for filename,value in content.items():
            path=archive/filename
            if path.exists() and path.read_text()!=value:raise ValueError('report archive is immutable')
            if not path.exists():path.write_text(value)
    return {'json':str(root/'report.json'),'markdown':str(root/'report.md'),'html':str(root/'report.html'),
            'zh_markdown':str(root/'report.zh.md'),'en_markdown':str(root/'report.en.md'),
            'zh_html':str(root/'report.zh.html'),'en_html':str(root/'report.en.html')}
