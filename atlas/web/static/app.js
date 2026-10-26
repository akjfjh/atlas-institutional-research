(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const tokenMatch = location.hash.match(/(?:^#|&)token=([^&]+)/);
  if (tokenMatch) {
    sessionStorage.setItem('atlas-local-token', decodeURIComponent(tokenMatch[1]));
    history.replaceState(null, '', location.pathname);
  }
  const token = sessionStorage.getItem('atlas-local-token') || '';
  const state = {lang:'zh', audience:'novice', type:'SPOT', catalog:[], selected:null, current:null, job:null,
    tf:'1D', hover:null, poller:null, roles:{}, rolesEn:{}, dependencies:{}, history:[], selectedRole:null};
  const roleNames={zh:{fed:'美联储研究员',macro:'宏观研究员',news:'新闻研究员',technical:'技术研究员',entry_timing:'入场时机研究员',sentiment:'情绪研究员',backtest:'回测研究员',btc_specialist:'BTC 专项研究员',eth_specialist:'ETH 专项研究员',risk_control:'独立风控员',trading:'策略决策员',chief:'首席审查员'},en:{fed:'Fed researcher',macro:'Macro researcher',news:'News researcher',technical:'Technical analyst',entry_timing:'Entry timing researcher',sentiment:'Sentiment analyst',backtest:'Backtest analyst',btc_specialist:'BTC specialist',eth_specialist:'ETH specialist',risk_control:'Risk officer',trading:'Strategy lead',chief:'Chief reviewer'}};
  const roleWork={zh:{fed:'核对官方政策消息',macro:'核对经济数据',news:'核对新闻时间',technical:'计算已收盘 K 线',entry_timing:'比对 15m 与 1H 入场条件',sentiment:'检查合约情绪',backtest:'检查历史模拟',btc_specialist:'专看 BTC',eth_specialist:'专看 ETH',risk_control:'核对风险与本金',trading:'整理条件方案',chief:'复核全部结论'},en:{fed:'Checking Fed releases',macro:'Checking macro data',news:'Checking news timing',technical:'Reading closed candles',entry_timing:'Comparing 15m and 1H',sentiment:'Checking derivatives mood',backtest:'Checking simulation',btc_specialist:'Studying BTC',eth_specialist:'Studying ETH',risk_control:'Checking risk and capital',trading:'Drafting scenarios',chief:'Auditing conclusions'}};
  const copy={zh:{audience:'你是哪类交易员？',novice:'新手 · 大白话',experienced:'资深 · 专业版',horizonType:'计划持仓',horizon:'预计持有多久',strategy:'研究策略',standard:'常规研究',oneU:'1U · 50/100 倍模拟',entry:'红线 · 条件入场参考',work:'做了什么',result:'得到什么',wait:'等待',noOrder:'当前不可下单',conditional:'仅为条件参考，需重新判断'},en:{audience:'Your trading experience',novice:'Beginner · Plain words',experienced:'Experienced · Technical',horizonType:'Holding plan',horizon:'Expected duration',strategy:'Research strategy',standard:'Standard research',oneU:'1 USDT · 50/100x simulation',entry:'Red · Conditional entry reference',work:'Work',result:'Result',wait:'Wait',noOrder:'No order now',conditional:'Conditional reference only; reassess first'}};
  const reasonZh={non_live_data:'非实时数据',ticker_not_fresh:'报价不够新',ticker_stale_at_publication:'发布时报价过期',price_unavailable:'报价缺失',levels_unavailable:'关键位缺失',instrument_not_in_profile:'未列入主要交易对',spot_usdt_only:'仅现货 USDT 可计算可执行仓位',capital_unset:'本金未设置',portfolio_exposure_unconfirmed:'账户敞口未及时确认',breakout_unconfirmed:'日线突破未确认',daily_trend_not_bullish:'日线趋势未转多',timeframe_conflict:'多周期冲突',edge_unverified:'策略优势未经验证',price_too_far_from_entry:'价格远离参考入场位',committee_not_approved:'委员会未批准',risk_officer_not_run:'快速扫描未运行完整风控',risk_officer_veto:'风控员否决',exchange_order_rules_or_size_unavailable:'交易规则或数量不可核验'};
  const reasonEn={non_live_data:'Data is not live',ticker_not_fresh:'Ticker is stale',ticker_stale_at_publication:'Ticker was stale at publication',price_unavailable:'Price unavailable',levels_unavailable:'Watch levels unavailable',instrument_not_in_profile:'Not in primary markets',spot_usdt_only:'Executable sizing supports USDT spot only',capital_unset:'Capital not set',portfolio_exposure_unconfirmed:'Portfolio exposure not recently confirmed',breakout_unconfirmed:'Daily breakout unconfirmed',daily_trend_not_bullish:'Daily trend is not bullish',timeframe_conflict:'Timeframe conflict',edge_unverified:'Strategy edge unverified',price_too_far_from_entry:'Price too far from entry reference',committee_not_approved:'Committee did not approve',risk_officer_not_run:'Quick scan did not run full risk review',risk_officer_veto:'Risk officer veto',exchange_order_rules_or_size_unavailable:'Exchange rules or size unavailable'};
  const tr = {
    zh: {overview:'总览',research:'研究台',history:'复盘档案',local:'仅本机 · 只读',heroTitle:'让每一份判断，<br><em>都有证据。</em>',heroSub:'12 位角色整理证据，由 Codex 研读行情、分歧和风险，形成最后判断。',agents:'研究角色',markets:'市场类型',memory:'本地复盘',composer:'开启一次研究',source:'交易对来自 OKX 公共目录 · 实时核验',picker:'研究市场',select:'选择交易对',mode:'研究模式',full:'完整委员会',quick:'快速技术扫描',run:'开始研究',foot:'Codex 负责研读；数据计算与风控另行核验。全程只读，并保存到本机。',dashboard:'研究现场',dashSub:'选择交易对后，这里会显示证据整理及 Codex 研读进度。',refresh:'刷新',network:'决策网络',chart:'行情结构',chartWaiting:'等待选择市场',chartEmpty:'选择市场并开始研究后显示已确认 K 线',up:'上涨',down:'下跌',levels:'支撑 / 阻力',decision:'当前判断',unresearched:'未研究',lead:'所有结论都附有行情时间、证据和阻断原因。',support:'重点支撑',resistance:'重点阻力',timeline:'协作动态',detail:'选择一位研究员',detailSummary:'点击上方角色，查看输入依赖、证据数量、结论与不确定性。',historyTitle:'每一步都有记录',historySub:'研究报告、角色版本与操作日志保留在本机，方便回看判断如何形成。',refreshHistory:'刷新档案',historyList:'研究档案',journal:'本地操作记录',footer:'Codex 研读 · 只读研究 · 不自动下单',dialog:'选择研究市场',search:'搜索全部交易对，如 BTC、ETH、SOL…',disclaimer:'目录来自 OKX 公共接口；可用性随市场和地区变化。灰色项目不可研究。',profile:'先设置你的研究偏好',profileIntro:'只保存到你的电脑，用于风险预算。不会读取交易账户，也不会自动下单。',language:'语言',capital:'规划本金（USDT）',profileMarkets:'主要研究交易对（逗号分隔）',noPositions:'我确认目前没有持仓或未成交挂单',saveProfile:'保存并进入研究台 ↗',profileFoot:'未确认持仓时，风险控制会禁止生成可执行开仓数量。',note:'写下你关心的问题，Codex 会纳入研读（可选）',waiting:'等待任务',running:'研究进行中',done:'研究完成',failed:'研究失败',noEntry:'暂不支持开仓',canEntry:'条件允许',pending:'等待完整审查',viewZh:'中文报告 ↗',viewEn:'English report ↗',reassess:'重新判断 ↻',empty:'暂无记录',sourceTime:'目录获取时间',loaded:'已载入',marketCount:'个市场',loading:'正在读取 OKX 市场目录…',busy:'任务正在运行',selectFirst:'请先选择交易对',notLive:'不可用',noFindings:'暂无角色结论',evidence:'证据',depends:'依赖',uncertainty:'不确定性',quoteTime:'报价时间',reportOld:'历史报告是时间快照，操作前请重新研究。',noAuth:'缺少本地会话令牌，请从 ATLAS 启动输出中的完整链接打开。',invalidInstrument:'当前市场目录中找不到该交易对',catalogError:'OKX 市场目录暂不可用，请稍后重试。',researchStart:'研究已启动',profileSaved:'偏好已保存',promptNote:'研究备注会作为研究问题交给 Codex；不会改变价格计算或风控门槛。',noData:'尚无可显示的已确认 K 线',price:'价格',volume:'成交量',status:{waiting:'等待',complete:'完成',partial:'部分',blocked:'受阻',running:'运行中'},events:{research_started:'研究创建',phase:'阶段切换',agent_result:'角色提交结论',evidence_exchange:'跨角色证据交换',cross_examination:'交叉复核',final_audit:'最终审查',reassessment_requested:'关键位重新判断',dependent_invalidated:'依赖结果更新',review_returned:'审查退回修订'}},
    en: {overview:'Overview',research:'Research floor',history:'Local archive',local:'Local only · Read only',heroTitle:'Every decision,<br><em>backed by evidence.</em>',heroSub:'Twelve roles prepare evidence. Codex reviews the market, disagreements, and risk before forming the final view.',agents:'Research roles',markets:'Market types',memory:'Local memory',composer:'Start a research run',source:'Instruments from the OKX public catalog · Verified live',picker:'Research market',select:'Choose an instrument',mode:'Research mode',full:'Full committee',quick:'Quick technical scan',run:'Start research',foot:'Codex conducts the review; calculations and risk gates are checked separately. Read only and archived locally.',dashboard:'Research in motion',dashSub:'Choose a market to see evidence preparation and Codex review progress.',refresh:'Refresh',network:'Decision network',chart:'Market structure',chartWaiting:'Choose a market',chartEmpty:'Confirmed candles appear after research starts',up:'Up',down:'Down',levels:'Support / resistance',decision:'Current assessment',unresearched:'Not researched',lead:'Every conclusion has a market timestamp, evidence, and blockers.',support:'Key support',resistance:'Key resistance',timeline:'Research activity',detail:'Select a researcher',detailSummary:'Click a role above to inspect dependencies, evidence, findings, and uncertainty.',historyTitle:'A record of every step',historySub:'Reports, role versions, and interaction logs stay on this computer for review.',refreshHistory:'Refresh archive',historyList:'Research archive',journal:'Local interaction log',footer:'Read-only research · Every report has a time boundary · Never auto-trades',dialog:'Choose a research market',search:'Search every instrument, e.g. BTC, ETH, SOL…',disclaimer:'Catalog from the OKX public endpoint. Availability can vary by market and region. Dimmed instruments are not live.',profile:'Set your research preferences',profileIntro:'Saved only on this computer for risk budgeting. No account read and no automatic orders.',language:'Language',capital:'Planning capital (USDT)',profileMarkets:'Primary instruments (comma separated)',noPositions:'I confirm I have no positions or open orders now',saveProfile:'Save and enter research floor ↗',profileFoot:'If exposure is unknown, risk control will not produce an executable order quantity.',note:'Your research question or note (optional)',waiting:'Waiting',running:'Research running',done:'Research complete',failed:'Research failed',noEntry:'Entry blocked',canEntry:'Conditional entry',pending:'Awaiting final audit',viewZh:'Chinese report ↗',viewEn:'English report ↗',reassess:'Reassess ↻',empty:'No records yet',sourceTime:'Catalog fetched',loaded:'Loaded',marketCount:'markets',loading:'Loading OKX market catalog…',busy:'A run is in progress',selectFirst:'Choose an instrument first',notLive:'Not live',noFindings:'No findings yet',evidence:'Evidence',depends:'Depends on',uncertainty:'Uncertainty',quoteTime:'Quote time',reportOld:'Archived reports are time snapshots. Refresh before acting.',noAuth:'Missing local session token. Open the full link printed by ATLAS.',invalidInstrument:'Instrument is not in the current catalog',catalogError:'OKX catalog is unavailable; retry later.',researchStart:'Research started',profileSaved:'Preferences saved',promptNote:'The question is sent to Codex; it does not alter price calculations or risk gates.',noData:'No confirmed candles to display',price:'Price',volume:'Volume',status:{waiting:'Waiting',complete:'Complete',partial:'Partial',blocked:'Blocked',running:'Running'},events:{research_started:'Research created',phase:'Phase changed',agent_result:'Role submitted findings',evidence_exchange:'Evidence exchange',cross_examination:'Cross-check',final_audit:'Final audit',reassessment_requested:'Key-level reassessment',dependent_invalidated:'Dependency updated',review_returned:'Review requested revision'}}
  };
  tr.zh.events.agent_started='开始处理';tr.en.events.agent_started='Role started';
  tr.zh.events.agent_failed='处理失败';tr.en.events.agent_failed='Role failed';
  const t = key => tr[state.lang][key];
  const fmt = (n, digits=2) => Number.isFinite(Number(n)) ? new Intl.NumberFormat(state.lang==='zh'?'zh-CN':'en-US',{maximumFractionDigits:digits}).format(Number(n)) : '—';
  const when = v => {if (!v) return '—'; const date = typeof v==='number' ? new Date(v) : new Date(v); return Number.isNaN(date.getTime())?'—':new Intl.DateTimeFormat(state.lang==='zh'?'zh-CN':'en-US',{dateStyle:'short',timeStyle:'medium',timeZone:'Asia/Shanghai'}).format(date);};
  const el = (tag, cls, text) => {const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=String(text);return node;};
  function toast(message){const node=$('toast');node.textContent=message;node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),4500);}
  async function api(path, options={}){
    const headers={'X-ATLAS-Token':token};
    if(options.body!==undefined)headers['Content-Type']='application/json';
    const response=await fetch(path,{...options,headers:{...headers,...(options.headers||{})}});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);
    return data;
  }
  function setText(id,value){const node=$(id);if(node)node.textContent=value;}
  function translate(){
    document.documentElement.lang=state.lang==='zh'?'zh-CN':'en';
    $('languageBtn').textContent=state.lang==='zh'?'EN':'中文';
    const ids={localLabel:'local',heroSub:'heroSub',metricAgents:'agents',metricMarkets:'markets',metricHistory:'memory',composerTitle:'composer',sourceNote:'source',pickerLabel:'picker',modeLabel:'mode',runLabel:'run',composerFoot:'foot',dashboardTitle:'dashboard',dashboardSubtitle:'dashSub',refreshBtn:'refresh',networkTitle:'network',chartTitle:'chart',legendUp:'up',legendDown:'down',legendSupport:'levels',decisionTitle:'decision',supportLabel:'support',resistanceLabel:'resistance',timelineTitle:'timeline',historyTitle:'historyTitle',historySubtitle:'historySub',historyRefresh:'refreshHistory',historyListTitle:'historyList',journalTitle:'journal',footerCopy:'footer',dialogTitle:'dialog',catalogDisclaimer:'disclaimer',profileTitle:'profile',profileIntro:'profileIntro',profileLanguageLabel:'language',profileCapitalLabel:'capital',profileMarketsLabel:'profileMarkets',profileNoPositionsLabel:'noPositions',saveProfileBtn:'saveProfile',profileFoot:'profileFoot',viewZhReport:'viewZh',viewEnReport:'viewEn',reassessBtn:'reassess'};
    for(const [id,key] of Object.entries(ids))setText(id,t(key));
    setText('legendSupport',state.lang==='zh'?'白线 · 重点观察':'White · Key watch levels');
    const c=copy[state.lang];
    for(const [id,key] of Object.entries({audienceLabel:'audience',horizonTypeLabel:'horizonType',horizonLabel:'horizon',strategyLabel:'strategy',legendEntry:'entry',profileLevelLabel:'audience'}))setText(id,c[key]);
    document.querySelectorAll('.audience-btn').forEach(btn=>{btn.textContent=c[btn.dataset.audience];btn.classList.toggle('active',btn.dataset.audience===state.audience);});
    $('strategySelect').options[0].text=c.standard;$('strategySelect').options[1].text=c.oneU;
    $('horizonType').options[0].text=state.lang==='zh'?'短期 · 1 小时到 1 天':'Short · 1 hour to 1 day';
    $('horizonType').options[1].text=state.lang==='zh'?'长期 · 1 天到 1 年':'Long · 1 day to 1 year';
    updateHorizonOptions();
    $('profileLevel').options[1].text=state.lang==='zh'?'新手交易员 · 大白话':'Beginner · Plain words';
    $('profileLevel').options[2].text=state.lang==='zh'?'资深交易员 · 专业版':'Experienced · Technical';
    setText('reportDialogTitle',state.lang==='zh'?'研究报告':'Research report');
    $('heroTitle').innerHTML=t('heroTitle');
    document.querySelectorAll('.type-btn').forEach(btn=>{btn.firstChild.textContent=state.lang==='en'?({SPOT:'Spot ',SWAP:'Perpetual ',FUTURES:'Expiry '}[btn.dataset.type]):({SPOT:'现货 ',SWAP:'永续 ',FUTURES:'交割 '}[btn.dataset.type]);});
    $('marketSearch').placeholder=t('search');$('researchNote').placeholder=t('note');
    $('modeSelect').options[0].text=t('full');$('modeSelect').options[1].text=t('quick');
    document.querySelectorAll('.nav-link').forEach(btn=>btn.textContent=t(btn.dataset.view));
    if(!state.selected)setText('selectedMarket',t('select'));
    if(!state.current){setText('detailTitle',t('detail'));setText('detailSummary',t('detailSummary'));setText('decisionBadge',t('unresearched'));setText('decisionLead',t('lead'));setText('chartInstrument',t('chartWaiting'));setText('chartEmpty',t('chartEmpty'));}
    if(state.current)renderRecord(state.current);else renderAgentGrid(null,state.job);
    if(!state.selectedRole){setText('detailTitle',t('detail'));setText('detailSummary',t('detailSummary'));}
    renderHistory();renderJournal();renderCatalog();
  }
  function setView(name){
    document.querySelectorAll('.nav-link').forEach(btn=>btn.classList.toggle('active',btn.dataset.view===name));
    const target={overview:'hero',research:'dashboard',history:'history'}[name];
    $(target).scrollIntoView({behavior:'smooth',block:'start'});
  }
  function statusClass(status){return status==='done'?'done':status==='running'?'running':status==='failed'?'failed':'idle';}
  function phaseLabel(phase){const labels={zh:{STANDBY:'待命',QUEUED:'排队中',CREATED:'已创建',DATA_READY:'数据就绪',RESEARCH_IN_PROGRESS:'研究中',CROSS_VALIDATION:'交叉复核',BACKTEST_VALIDATION:'回测核验',STRATEGY_REVIEW:'策略审查',FINAL_AUDIT:'最终审查',INSUFFICIENT_DATA:'证据不足',APPROVED:'已批准',REJECTED:'已否决'},en:{STANDBY:'STANDBY',QUEUED:'QUEUED',CREATED:'CREATED',DATA_READY:'DATA READY',RESEARCH_IN_PROGRESS:'RESEARCH',CROSS_VALIDATION:'CROSS CHECK',BACKTEST_VALIDATION:'BACKTEST',STRATEGY_REVIEW:'STRATEGY',FINAL_AUDIT:'FINAL AUDIT',INSUFFICIENT_DATA:'EVIDENCE GAP',APPROVED:'APPROVED',REJECTED:'REJECTED'}};return labels[state.lang][phase]||String(phase||'STANDBY').replaceAll('_',' ');}
  function setRunStatus(label,status){const node=$('runStatus');node.textContent=label;node.className=`status-pill ${statusClass(status)}`;}
  function updateHorizonOptions(){
    const long=$('horizonType').value==='long';const choices=long?['1d','1w','1mo','3mo','1y']:['1h','4h','12h','1d'];
    const labels=state.lang==='zh'?{'1h':'1 小时','4h':'4 小时','12h':'12 小时','1d':'1 天','1w':'1 周','1mo':'1 个月','3mo':'3 个月','1y':'1 年'}:{'1h':'1 hour','4h':'4 hours','12h':'12 hours','1d':'1 day','1w':'1 week','1mo':'1 month','3mo':'3 months','1y':'1 year'};
    const previous=$('horizonSelect').value;$('horizonSelect').replaceChildren();
    for(const value of choices){const option=document.createElement('option');option.value=value;option.textContent=labels[value];$('horizonSelect').append(option);}
    $('horizonSelect').value=choices.includes(previous)?previous:choices[0];
  }
  async function setAudience(level){
    if(!['novice','experienced'].includes(level))return;
    state.audience=level;translate();
    if(state.profile){try{await api('/api/audience',{method:'POST',body:JSON.stringify({trader_level:level})});state.profile.trader_level=level;}catch(err){toast(err.message);}}
  }
  async function loadCatalog(kind=state.type){
    state.type=kind;state.catalog=[];state.selected=null;
    setText('selectedMarket',t('select'));setText('catalogCount',t('loading'));
    document.querySelectorAll('.type-btn').forEach(btn=>btn.classList.toggle('active',btn.dataset.type===kind));
    try{
      const data=await api(`/api/instruments?type=${encodeURIComponent(kind)}`);
      if(kind!==state.type)return;
      state.catalog=data.instruments;
      setText('catalogCount',`${data.count} ${t('marketCount')}`);
      setText('catalogTime',`${t('sourceTime')}: ${when(data.fetched_at)}`);
      const favorite=(state.profile?.primary_instruments||[]).find(x=>state.catalog.some(i=>i.id===x&&i.state==='live'));
      const fallback=state.catalog.find(i=>i.id==='BTC-USDT'&&i.state==='live')||state.catalog.find(i=>i.state==='live');
      if(favorite||fallback)chooseMarket(favorite||fallback.id,false);
      renderCatalog();
    }catch(err){setText('catalogCount',t('catalogError'));toast(err.message);renderCatalog();}
  }
  function chooseMarket(id,close=true){const found=state.catalog.find(item=>item.id===id);if(!found||found.state!=='live')return;
    state.selected=found;setText('selectedMarket',id);if(close&&$('marketDialog').open)$('marketDialog').close();}
  function renderCatalog(){
    const target=$('instrumentList');target.replaceChildren();const query=$('marketSearch').value.trim().toUpperCase();
    const items=state.catalog.filter(item=>!query||item.id.includes(query)||String(item.base).toUpperCase().includes(query));
    if(!items.length){target.append(el('div','empty-copy',state.catalog.length?t('invalidInstrument'):t('loading')));return;}
    const fragment=document.createDocumentFragment();
    for(const item of items){const btn=el('button','instrument-item');btn.type='button';btn.disabled=item.state!=='live';
      const expiry=item.expiry?new Date(Number(item.expiry)).toISOString().slice(0,10):'';
      btn.append(el('strong','',item.id),el('small','',`${item.type} · ${item.state}${expiry?' · '+expiry:''}`));
      btn.addEventListener('click',()=>chooseMarket(item.id));fragment.append(btn);}
    target.append(fragment);
  }
  function roleTitle(id){return roleNames[state.lang][id]||id;}
  function roleResult(info){if(!info)return copy[state.lang].wait;return state.audience==='novice'?(state.lang==='zh'?(info.simple_zh||info.brief_zh):(info.simple_en||info.brief_en)):(state.lang==='zh'?info.brief_zh:info.brief_en);}
  function roleAction(name,info){if(!info)return roleWork[state.lang][name]||roleTitle(name);const work=state.audience==='novice'?(state.lang==='zh'?info.simple_work_zh:info.simple_work_en):(state.lang==='zh'?info.codex_work_zh:info.codex_work_en);return work||roleWork[state.lang][name]||roleTitle(name);}
  function renderAgentGrid(record=null,job=null){
    const target=$('agentGrid');target.replaceChildren();
    const orbit=$('orbitAgents');orbit.replaceChildren();
    const roleMap=record?.roles||{};const names=record?Object.keys(roleMap):Object.keys(state.roles);
    let complete=0;
    names.forEach((name,index)=>{const info=roleMap[name];const status=job?.roles?.[name]==='running'?'running':info?.status||job?.roles?.[name]||'waiting';if(status==='complete')complete++;
      const btn=el('button','agent-card');btn.type='button';btn.dataset.role=name;
      const dot=el('span',`agent-status ${status}`);btn.append(el('small','number',String(index+1).padStart(2,'0')),dot,el('strong','agent-name',roleTitle(name)));
      const deps=info?.dependencies||state.dependencies[name]||[];
      const active=job?.roles?.[name]==='running';
      const currentStatus=active?'running':status;
      const awaitingCodex=record?.engine==='codex'&&!record.codex_review?.status&&info&&status!=='waiting';
      const reviewed=Boolean(info?.codex_work_zh||info?.codex_work_en);
      const resultText=active?(state.lang==='zh'?'正在整理证据…':'Preparing evidence…'):awaitingCodex?(state.lang==='zh'?'证据已备，待 Codex 研读':'Evidence ready; awaiting Codex'):(info&&(reviewed||state.audience==='novice')?roleResult(info):(t('status')[currentStatus]||currentStatus));
      btn.append(el('div','agent-action',roleAction(name,info)),el('div','agent-result',`${copy[state.lang].result}：${resultText}`));
      if(state.audience==='experienced')btn.append(el('div','agent-dep',deps.length?`${t('depends')}: ${deps.map(roleTitle).join(' · ')}`:'ROOT'));
      btn.addEventListener('click',()=>showRole(name));target.append(btn);
      const orb=el('button',`orbit-agent ${status}`,String(index+1));orb.type='button';orb.dataset.role=name;orb.title=roleTitle(name);orb.setAttribute('aria-label',roleTitle(name));
      const angle=-Math.PI/2+2*Math.PI*index/names.length;orb.style.left=`${74+70*Math.cos(angle)}px`;orb.style.top=`${74+70*Math.sin(angle)}px`;
      orb.addEventListener('click',()=>showRole(name));orbit.append(orb);
    });
    setText('roleCount',`${complete} / ${names.length}`);
    const phase=record?.phase||job?.phase||'STANDBY';
    setText('networkPhase',record?.mode==='quick'&&phase==='APPROVED'?(state.lang==='zh'?'技术扫描完成':'Technical scan complete'):phaseLabel(phase));
  }
  function showRole(name){
    state.selectedRole=name;
    document.querySelectorAll('.agent-card,.orbit-agent').forEach(card=>card.classList.toggle('selected',card.dataset.role===name));
    const info=state.current?.roles?.[name];
    setText('detailTitle',roleTitle(name));
    setText('detailStatus',info?`${t('status')[info.status]||info.status} · v${info.version}`:t('status').waiting);
    const mandate=(state.lang==='en'?state.rolesEn:state.roles)[name]||'';
    const codexWork=info?(state.lang==='zh'?info.codex_work_zh:info.codex_work_en):null;
    setText('detailSummary',state.audience==='novice'?`${copy[state.lang].work}：${roleAction(name,info)}。${copy[state.lang].result}：${roleResult(info)}。`:`${mandate} ${t('depends')}: ${(info?.dependencies||state.dependencies[name]||[]).map(roleTitle).join(', ')||'—'} · ${t('evidence')}: ${info?.evidence_count||0}`);
    const box=$('detailFindings');box.replaceChildren();
    if(!info||!info.findings.length){box.append(el('div','empty-copy',t('noFindings')));return;}
    if(codexWork){const card=el('div','finding');card.append(el('small','',state.lang==='zh'?'Codex 研读':'Codex review'),el('div','',roleResult(info)));box.append(card);if(state.audience==='novice')return;}
    if(state.audience==='novice'){
      const message=name==='entry_timing'?(state.current?.entry_timing?.signal==='closed_bar_setup'?(state.lang==='zh'?'两种周期都出现条件形态，还要先看风控。':'Both periods show a setup; risk review remains.'):(state.lang==='zh'?'两种周期还没一起确认，先等。':'The two periods do not confirm together; wait.')):
        name==='risk_control'?(state.current?.risk?.can_open?(state.lang==='zh'?'目前可复核手动方案。':'A manual plan can be reviewed.'):(state.lang==='zh'?'当前不适合开仓。':'Entry is blocked.')):(state.lang==='zh'?'本轮已记录核验结果，详见简报。':'The result is recorded in the brief.');
      box.append(el('div','finding',message));return;
    }
    for(const finding of info.findings.slice(0,codexWork?1:2)){const card=el('div','finding');card.append(el('small','',`${finding.direction.toUpperCase()} · ${finding.evidence_ids.length} ${t('evidence')}`),el('div','',state.lang==='en'?(finding.claim_en||'See original Chinese report'):finding.claim));box.append(card);}
  }
  function renderTimeline(record=null,job=null){
    const events=record?.events||job?.events||[];const target=$('eventTimeline');target.replaceChildren();setText('eventCount',`${events.length} EVENTS`);
    if(!events.length){target.append(el('div','empty-copy',t('waiting')));return;}
    events.slice().reverse().slice(0,25).forEach(event=>{const item=el('div','timeline-item');const inner=el('div');const kind=event.kind==='codex_started'?(state.lang==='zh'?'Codex 开始综合研读':'Codex analysis started'):event.kind==='codex_completed'?(state.lang==='zh'?'Codex 完成研读':'Codex analysis completed'):event.kind==='codex_failed'?(state.lang==='zh'?'Codex 研读失败':'Codex analysis failed'):event.kind==='agent_result'&&record?.engine==='codex'?(state.lang==='zh'?'角色证据就绪':'Role evidence ready'):(t('events')[event.kind]||event.kind);
      const action=event.agent_id?` · ${roleWork[state.lang][event.agent_id]||roleTitle(event.agent_id)}`:'';
      inner.append(el('strong','',`${kind}${event.agent_id?' · '+roleTitle(event.agent_id):''}${action}`),el('small','',`${when(event.timestamp)}${event.phase?' · '+event.phase:''}${event.status?' · '+(t('status')[event.status]||event.status):''}`));item.append(inner);target.append(item);});
  }
  function renderDecision(record){
    const codexBox=$('codexPanel');codexBox.replaceChildren();codexBox.hidden=true;
    const review=record.codex_review||{};
    if(review.status==='complete'){
      codexBox.hidden=false;
      codexBox.append(el('strong','',state.lang==='zh'?'CODEX 研读判断':'CODEX RESEARCH REVIEW'));
      codexBox.append(el('p','',state.audience==='novice'?(state.lang==='zh'?(review.summary_simple_zh||review.summary_zh):(review.summary_simple_en||review.summary_en)):(state.lang==='zh'?review.summary_zh:review.summary_en)));
      const direction={UP:state.lang==='zh'?'偏上':'Upward',DOWN:state.lang==='zh'?'偏下':'Downward',SIDEWAYS:state.lang==='zh'?'横盘':'Sideways',UNCLEAR:state.lang==='zh'?'不明朗':'Unclear'}[review.market_direction]||review.market_direction;
      const entryView=state.audience==='novice'?({WAIT:state.lang==='zh'?'先等，不开仓':'Wait; no entry',LONG_WATCH:state.lang==='zh'?'留意上涨机会，先复查风险':'Watch a possible rise; recheck risk',SHORT_WATCH:state.lang==='zh'?'留意下跌机会，先复查风险':'Watch a possible fall; recheck risk'}[review.entry_view]||review.entry_view):review.entry_view;
      codexBox.append(el('small','',`${state.lang==='zh'?'观察方向':'Observed direction'}：${direction} · ${state.lang==='zh'?'入场研究':'Entry study'}：${entryView}${state.audience==='experienced'?' · '+review.model:''}`));
      if(state.audience==='experienced')codexBox.append(el('small','',`${state.lang==='zh'?'相反证据':'Contrary evidence'}：${state.lang==='zh'?review.contrary_zh:review.contrary_en}`));
    }else if(record.engine==='codex'&&record.events?.some(event=>event.kind==='codex_failed')){
      codexBox.hidden=false;codexBox.append(el('strong','',state.lang==='zh'?'Codex 研读未完成，本轮没有正式判断':'Codex review failed; this run has no final judgment'));
    }else if(record.engine==='codex'&&record.events?.some(event=>event.kind==='codex_started')){
      codexBox.hidden=false;codexBox.append(el('strong','',state.lang==='zh'?'Codex 正在综合研读证据…':'Codex is reviewing the evidence…'));
    }
    const decision=record.risk;const badge=$('decisionBadge');badge.className='risk-badge';
    if(!decision){badge.textContent=t('pending');setText('decisionLead',t('lead'));setText('supportValue','—');setText('resistanceValue','—');setText('watchMethod','');setText('decisionTime','—');$('reasonList').replaceChildren();$('entryIdea').replaceChildren();$('oneUStudy').hidden=true;return;}
    badge.textContent=decision.can_open?t('canEntry'):t('noEntry');badge.classList.add(decision.can_open?'yes':'no');
    const watch=decision.watch||{};setText('supportValue',fmt(watch.support));setText('resistanceValue',fmt(watch.resistance));
    const near=watch.nearest_level==='support'?(state.lang==='zh'?'支撑':'support'):watch.nearest_level==='resistance'?(state.lang==='zh'?'阻力':'resistance'):null;
    const levelLine=near?(state.lang==='zh'?`较近关键位为${near}；`:`The nearer level is ${near}; `):(state.lang==='zh'?'尚无可核验的关键位；':'No validated key level; ');
    const lead=state.lang==='zh'?`截至 ${when(watch.ticker_as_of)}，${record.instrument_id} 观测价 ${fmt(watch.current_price)}。${levelLine}当前${decision.can_open?'条件允许':'不建议开仓'}。`:`At ${when(watch.ticker_as_of)}, ${record.instrument_id} was ${fmt(watch.current_price)}. ${levelLine}entry is ${decision.can_open?'conditional':'blocked'}.`;
    setText('decisionLead',lead);setText('decisionTime',`${t('quoteTime')}: ${when(watch.ticker_as_of)} · ${t('reportOld')}`);
    setText('watchMethod',!watch.support||!watch.resistance?(state.lang==='zh'?'当前缺少可信的关键价位，请补齐数据后重新判断。':'Validated key levels are unavailable; refresh the study with complete data.'):state.audience==='novice'?(state.lang==='zh'?'白线是过去 20 天的重要高低位置。价格碰到白线后，等收盘确认，再重新判断。':'White lines mark important highs and lows from 20 closed days. Wait for a close, then reassess.'):(state.lang==='zh'?'观察依据：前 20 根已收盘日 K 的高低点。突破阻力需已收盘 K 线和成交量确认；测试支撑后需重新收回。':'Prior 20 closed-day high/low. Require closed-bar and volume confirmation before a breakout or support retest.'));
    const idea=$('entryIdea');idea.replaceChildren();
    const timing=record.entry_timing||{};const confirmed=timing.signal==='closed_bar_setup';
    const quickOneU=record.strategy_mode==='one_usdt_simulation';
    const entry=confirmed?timing.entry_reference:quickOneU?null:decision.risk?.entry_reference;
    const invalid=confirmed?timing.invalidation:quickOneU?null:decision.risk?.stop_reference;
    const direction=confirmed?(timing.direction==='LONG_WATCH'?(state.lang==='zh'?'观察做多':'Long watch'):(state.lang==='zh'?'观察做空':'Short watch')):(state.lang==='zh'?'等待确认':'Wait for confirmation');
    const line1=state.lang==='zh'?`研究方向：${direction}。${decision.can_open?'条件方案可供手动复核。':'当前风控未允许开仓。'}`:`Research direction: ${direction}. ${decision.can_open?'Manual conditional plan can be reviewed.':'Risk gate blocks entry.'}`;
    idea.append(el('strong','',line1));
    if(Number(entry)>0&&Number(invalid)>0&&Number.isFinite(Number(entry))&&Number.isFinite(Number(invalid))){
      idea.append(el('span','',state.lang==='zh'?`条件入场参考 ${fmt(entry)} · 失效/离场观察 ${fmt(invalid)} · ${confirmed?'已收盘形态，仍非挂单指令':'尚未确认，价格到位后请重新判断'}`:`Conditional entry ${fmt(entry)} · invalidation/exit watch ${fmt(invalid)} · ${confirmed?'closed-bar setup, not an order':'unconfirmed; reassess at the level'}`));
    }else if(quickOneU)idea.append(el('span','',state.lang==='zh'?'15m 与 1H 未共同确认，暂无可用的快进入场价和离场价。':'15m and 1H have not jointly confirmed; no valid quick entry or exit level.'));
    const sim=timing.one_usdt_simulation;const simBox=$('oneUStudy');simBox.replaceChildren();simBox.hidden=!sim;
    if(sim){simBox.append(el('strong','',state.lang==='zh'?'1U · 50/100 倍模拟（禁止下单）':'1 USDT · 50/100x simulation (orders disabled)'));
      simBox.append(el('span','',state.lang==='zh'?'1 USDT 保证金对应 50/100 USDT 名义仓位；反向波动约 2%/1%，毛亏损就接近 1 USDT，强平可能更早。未核验强平价、最小张数、资金费和账户档位。':'1 USDT margin implies 50/100 USDT notional. A 2%/1% adverse move is about 1 USDT gross loss; liquidation can happen earlier. Liquidation, minimum size, funding and account tier are unverified.'));
      simBox.append(el('small','',state.lang==='zh'?`15m RSI ${fmt(timing.indicators?.['15m_rsi14'])} · 1H ADX ${fmt(timing.indicators?.['1h_adx14'])} · 开仓方向 ${direction}`:`15m RSI ${fmt(timing.indicators?.['15m_rsi14'])} · 1H ADX ${fmt(timing.indicators?.['1h_adx14'])} · Direction ${direction}`));}
    const list=$('reasonList');list.replaceChildren();const reasons=decision.reasons||[];
    if(reasons.length){for(const reason of reasons.slice(0,8))list.append(el('span','',reason.startsWith('incomplete_')?(state.lang==='zh'?`${roleTitle(reason.slice(11))}证据不足`:`${roleTitle(reason.slice(11))} incomplete`):(state.lang==='zh'?reasonZh[reason]:reasonEn[reason])||reason.replaceAll('_',' ')));}
    else if(decision.order_plan)list.append(el('span','',`${decision.order_plan.order_type} · ${decision.order_plan.allocation} · ${decision.order_plan.total_base_quantity}`));
  }
  function renderRecord(record){
    state.current=record;
    const reviewPhase=record.mode==='quick'&&record.phase==='APPROVED'?(state.lang==='zh'?'技术扫描完成':'Technical scan complete'):phaseLabel(record.phase);
    setText('dashboardSubtitle',`${record.instrument_id} · ${record.market_type} · ${reviewPhase} · ${record.research_id}`);
    setRunStatus(record.completed_at?t('done'):t('running'),record.completed_at?'done':'running');
    setText('chartPrice',fmt(record.ticker?.last,6));setText('chartInstrument',`${record.instrument_id} · ${record.market_type}`);
    renderAgentGrid(record,state.job);renderTimeline(record,state.job);renderDecision(record);drawChart();
    const quoteAge=Date.now()-Number(record.ticker?.ts);
    const alerts=record.entry_timing?.alert===true&&record.data_mode==='live'&&quoteAge>=-60000&&quoteAge<=120000&&(record.engine!=='codex'||record.codex_review?.status==='complete');
    $('networkPhase').textContent=alerts?(state.lang==='zh'?'15m/1H 条件信号 · 复核风控':'15m/1H setup · check risk'):reviewPhase;
    document.querySelector('.network-center').classList.toggle('signal-alert',alerts);
    if(state.selectedRole)showRole(state.selectedRole);
  }
  function drawChart(){
    const canvas=$('marketChart'),wrap=canvas.parentElement,rect=wrap.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
    canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));
    const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);const w=rect.width,h=rect.height;
    ctx.clearRect(0,0,w,h);const rows=state.current?.charts?.[state.tf]||[];
    $('chartEmpty').hidden=rows.length>0;
    if(!rows.length)return;
    const left=13,right=62,top=17,bottom=29,volumeHeight=47;const plotW=w-left-right,plotH=h-top-bottom-volumeHeight;
    const low=Math.min(...rows.map(x=>Number(x.low))),high=Math.max(...rows.map(x=>Number(x.high)));
    if(!Number.isFinite(low)||!Number.isFinite(high)||high<=low)return;
    const span=(high-low)*1.16,base=low-(span-(high-low))/2;
    const Y=v=>top+(1-(v-base)/span)*plotH;
    ctx.strokeStyle='#2b3444';ctx.lineWidth=1;ctx.fillStyle='#8090a5';ctx.font='10px system-ui';
    for(let i=0;i<=4;i++){const y=top+plotH*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right+8,y);ctx.stroke();ctx.fillText(fmt(base+span*(1-i/4),2),w-right+13,y+3);}
    const maxVolume=Math.max(...rows.map(x=>Number(x.volume)||0),1),candleW=Math.max(2,Math.min(9,plotW/rows.length*.68));
    rows.forEach((row,index)=>{const x=left+(index+.5)*plotW/rows.length;const open=Number(row.open),close=Number(row.close);const up=close>=open;
      ctx.strokeStyle=up?'#65d5aa':'#eb7894';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(x,Y(Number(row.high)));ctx.lineTo(x,Y(Number(row.low)));ctx.stroke();
      const y=Math.min(Y(open),Y(close)),body=Math.max(1.4,Math.abs(Y(close)-Y(open)));
      ctx.fillRect(x-candleW/2,y,candleW,body);
      ctx.globalAlpha=.30;ctx.fillRect(x-candleW/2,h-bottom-(Number(row.volume)||0)/maxVolume*volumeHeight,candleW,(Number(row.volume)||0)/maxVolume*volumeHeight);ctx.globalAlpha=1;
    });
    {
      const watch=state.current?.chart_levels?.[state.tf]||state.current?.risk?.watch||{};
      for(const [value,color,label] of [[watch.support,'#f8fbff','S'],[watch.resistance,'#f8fbff','R']]){
        if(!(Number(value)>0)||!Number.isFinite(Number(value))||value<base||value>base+span)continue;
        const y=Y(Number(value));ctx.setLineDash([]);ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right+8,y);ctx.stroke();ctx.fillStyle=color;ctx.fillText(label,w-right+2,y-5);
      }
    }
    const timing=state.current?.entry_timing||{};
    const reference=timing.signal==='closed_bar_setup'?timing.entry_reference:state.current?.strategy_mode==='one_usdt_simulation'?null:state.current?.risk?.risk?.entry_reference;
    if(Number(reference)>0&&Number.isFinite(Number(reference))&&Number(reference)>=base&&Number(reference)<=base+span){
      const y=Y(Number(reference));ctx.setLineDash([9,4]);ctx.strokeStyle='#ff344e';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right+8,y);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#ff6478';ctx.font='bold 11px system-ui';ctx.fillText('E',w-right+1,y-6);
    }
    ctx.fillStyle='#76879b';const first=new Date(rows[0].ts),last=new Date(rows[rows.length-1].ts);
    ctx.fillText(first.toLocaleDateString(state.lang==='zh'?'zh-CN':'en-US',{month:'short',year:'2-digit'}),left,h-6);
    const label=last.toLocaleDateString(state.lang==='zh'?'zh-CN':'en-US',{month:'short',year:'2-digit'});ctx.fillText(label,w-right-40,h-6);
    if(state.hover!==null&&state.hover>=0&&state.hover<rows.length){const row=rows[state.hover],x=left+(state.hover+.5)*plotW/rows.length;
      ctx.strokeStyle='#e6f6ff69';ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,h-bottom);ctx.stroke();ctx.setLineDash([]);
      const label=`${new Date(row.ts).toLocaleDateString()}  O ${fmt(row.open)}  H ${fmt(row.high)}  L ${fmt(row.low)}  C ${fmt(row.close)}`;
      ctx.fillStyle='#101a27';ctx.fillRect(18,20,Math.min(w-36,label.length*5.8+16),25);ctx.fillStyle='#e9f5fc';ctx.fillText(label,25,37);
    }
  }
  async function loadRecord(id,scroll=true){try{const record=await api(`/api/research/${encodeURIComponent(id)}`);renderRecord(record);if(scroll)setView('research');}catch(err){toast(err.message);}}
  function renderHistory(){const box=$('historyList');box.replaceChildren();setText('historyCount',`${state.history.length} RECORDS`);
    if(!state.history.length){box.append(el('div','empty-copy',t('empty')));return;}
    for(const row of state.history){const button=el('button','history-item');button.type='button';const left=el('span');left.append(el('strong','',row.instrument_id),el('small','',`${when(row.created_at)} · ${row.research_id}`));button.append(left,el('span','history-phase',row.phase));button.addEventListener('click',()=>loadRecord(row.research_id));box.append(button);}
  }
  function renderJournal(){const box=$('journalList');box.replaceChildren();const rows=state.journal||[];if(!rows.length){box.append(el('div','empty-copy',t('empty')));return;}
    for(const row of rows){const div=el('div','journal-item');div.append(el('strong','',`${row.kind} · ${row.instrument_id||row.research_id||''}`),el('small','',`${when(row.at)}${row.note?' · '+row.note:''}`));box.append(div);}
  }
  async function refreshArchive(){try{const [historyRows,journalRows]=await Promise.all([api('/api/history'),api('/api/journal')]);state.history=historyRows;state.journal=journalRows;renderHistory();renderJournal();}catch(err){toast(err.message);}}
  async function startResearch(priorId=null){
    if(state.job&&['queued','running'].includes(state.job.status)){toast(t('busy'));return;}
    if(!priorId&&!state.selected){toast(t('selectFirst'));return;}
    if(!priorId&&$('strategySelect').value==='one_usdt_simulation'&&state.type!=='SWAP'){toast(state.lang==='zh'?'1U 高杠杆模拟仅支持选择永续合约。':'Choose a perpetual market for the 1 USDT simulation.');return;}
    const payload=priorId?{research_id:priorId,language:state.lang,trader_level:state.audience}:{instrument_id:state.selected.id,language:state.lang,mode:$('modeSelect').value,note:$('researchNote').value.trim(),holding_horizon:$('horizonSelect').value,strategy_mode:$('strategySelect').value,trader_level:state.audience};
    try{const job=await api(priorId?'/api/reassess':'/api/research',{method:'POST',body:JSON.stringify(payload)});state.job=job;state.current=null;state.selectedRole=null;setRunStatus(t('running'),'running');setText('dashboardSubtitle',`${job.instrument_id} · ${job.market_type} · ${job.job_id}`);renderAgentGrid(null,job);renderTimeline(null,job);renderDecision({risk:null});setText('detailTitle',t('detail'));setText('detailSummary',t('detailSummary'));$('detailFindings').replaceChildren();setView('research');toast(t('researchStart'));clearInterval(state.poller);state.poller=setInterval(pollJob,1400);pollJob();}
    catch(err){toast(err.message);}
  }
  async function pollJob(){if(!state.job)return;try{const job=await api(`/api/jobs/${state.job.job_id}`);state.job=job;setRunStatus(job.status==='failed'?t('failed'):job.status==='done'?t('done'):t('running'),job.status);renderAgentGrid(state.current,job);renderTimeline(state.current,job);
      if(job.research_id)await loadRecord(job.research_id,false);
      if(job.status==='done'||job.status==='failed'){clearInterval(state.poller);state.poller=null;await refreshArchive();if(job.status==='failed')toast(job.error||t('failed'));}}
    catch(err){clearInterval(state.poller);state.poller=null;toast(err.message);}}
  async function openReport(language){if(!state.current?.report_available){toast(t('pending'));return;}try{
      const response=await fetch(`/api/reports/${state.current.research_id}/${language}/html?audience=${state.audience}`,{headers:{'X-ATLAS-Token':token}});
      if(!response.ok)throw new Error('Report unavailable');const html=await response.text();
      $('reportFrame').srcdoc=html;
      setText('reportDialogTitle',`${state.current.instrument_id} · ${language==='zh'?'中文报告':'English report'}`);
      $('reportDialog').showModal();
    }catch(err){toast(err.message);}}
  function closeReport(){if($('reportDialog').open)$('reportDialog').close();$('reportFrame').removeAttribute('srcdoc');}
  async function saveProfile(event){event.preventDefault();const markets=$('profileMarkets').value.split(/[,，]/).map(x=>x.trim().toUpperCase()).filter(Boolean);
    const payload={language:$('profileLanguage').value,capital_usdt:Number($('profileCapital').value),markets,no_open_positions:$('profileNoPositions').checked,trader_level:$('profileLevel').value};
    try{const data=await api('/api/profile',{method:'POST',body:JSON.stringify(payload)});state.profile=data.profile;state.lang=data.profile.language;state.audience=data.profile.trader_level;$('profileDialog').close();translate();await loadCatalog('SPOT');toast(t('profileSaved'));}
    catch(err){toast(err.message);}}
  async function initialize(){
    if(!token){toast(t('noAuth'));return;}
    try{const data=await api('/api/bootstrap');state.profile=data.profile;state.roles=data.roles;state.rolesEn=data.roles_en;state.dependencies=data.dependencies;state.history=data.history;
      state.lang=data.profile.language||'zh';state.audience=data.profile.trader_level||'novice';translate();renderAgentGrid();renderTimeline();await Promise.all([loadCatalog('SPOT'),refreshArchive()]);
      if(!data.profile.capital_usdt||!data.profile.primary_instruments?.length||!data.profile.trader_level){$('profileDialog').showModal();$('profileCapital').value=data.profile.capital_usdt||'';$('profileMarkets').value=(data.profile.primary_instruments||[]).join(', ');$('profileLevel').value=data.profile.trader_level||'';}
      const newest=data.history.find(x=>!['CREATED','DATA_READY','RESEARCH_IN_PROGRESS'].includes(x.phase))||data.history[0];if(newest)await loadRecord(newest.research_id,false);
    }catch(err){toast(err.message);}}
  document.querySelectorAll('.nav-link').forEach(btn=>btn.addEventListener('click',()=>setView(btn.dataset.view)));
  $('homeBtn').addEventListener('click',()=>setView('overview'));
  $('languageBtn').addEventListener('click',()=>{state.lang=state.lang==='zh'?'en':'zh';translate();});
  document.querySelectorAll('.audience-btn').forEach(btn=>btn.addEventListener('click',()=>setAudience(btn.dataset.audience)));
  $('horizonType').addEventListener('change',updateHorizonOptions);
  $('hero').addEventListener('pointermove',event=>{const r=event.currentTarget.getBoundingClientRect();event.currentTarget.style.setProperty('--mx',`${event.clientX-r.left}px`);event.currentTarget.style.setProperty('--my',`${event.clientY-r.top}px`);});
  $('hero').addEventListener('pointerleave',event=>{event.currentTarget.style.removeProperty('--mx');event.currentTarget.style.removeProperty('--my');});
  document.querySelectorAll('.type-btn').forEach(btn=>btn.addEventListener('click',()=>loadCatalog(btn.dataset.type)));
  $('marketPicker').addEventListener('click',()=>{$('marketSearch').value='';renderCatalog();$('marketDialog').showModal();$('marketSearch').focus();});
  $('closeDialog').addEventListener('click',()=>$('marketDialog').close());
  $('marketSearch').addEventListener('input',renderCatalog);
  $('runBtn').addEventListener('click',()=>startResearch());
  $('refreshBtn').addEventListener('click',()=>state.current&&loadRecord(state.current.research_id,false));
  $('historyRefresh').addEventListener('click',refreshArchive);
  $('viewZhReport').addEventListener('click',()=>openReport('zh'));
  $('viewEnReport').addEventListener('click',()=>openReport('en'));
  $('closeReportDialog').addEventListener('click',closeReport);
  $('reportDialog').addEventListener('close',closeReport);
  $('reassessBtn').addEventListener('click',()=>state.current&&startResearch(state.current.research_id));
  $('profileForm').addEventListener('submit',saveProfile);
  document.querySelectorAll('#timeframeSwitch button').forEach(btn=>btn.addEventListener('click',()=>{state.tf=btn.dataset.tf;document.querySelectorAll('#timeframeSwitch button').forEach(x=>x.classList.toggle('active',x===btn));drawChart();}));
  $('marketChart').addEventListener('mousemove',event=>{const rows=state.current?.charts?.[state.tf]||[];if(!rows.length)return;const rect=event.currentTarget.getBoundingClientRect();state.hover=Math.max(0,Math.min(rows.length-1,Math.floor((event.clientX-rect.left-13)/(rect.width-75)*rows.length)));drawChart();});
  $('marketChart').addEventListener('mouseleave',()=>{state.hover=null;drawChart();});
  window.addEventListener('resize',()=>{if(state.current)drawChart();});
  initialize();
})();
