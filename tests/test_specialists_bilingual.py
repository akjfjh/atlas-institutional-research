"""BTC/ETH specialist and bilingual report regressions on explicit synthetic data."""
from __future__ import annotations
import copy,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from atlas.analysis.specialists import summarize_specialist
from atlas.config import Config
from atlas.core.coordinator import Coordinator
from atlas.core.reviewer import RiskResearchAudit
from atlas.core.state import ResearchState

DAY=86_400_000

def markets_and_snapshot(asset):
    today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    times=[int((today-timedelta(days=160-i)).timestamp()*1000) for i in range(160)]
    def bars(ts_list,prices,step):
        return [{'ts':ts,'available_at':ts+step,'open':price,'high':price+1,'low':price-1,
                 'close':price,'volume':1000+i,'confirm':True} for i,(ts,price) in enumerate(zip(ts_list,prices))]
    btc=bars(times,[100+i*.4 for i in range(160)],DAY)
    eth=bars(times,[200+i*.1 for i in range(160)],DAY)
    market={}
    now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
    for coin,rows in [('BTC',btc),('ETH',eth)]:
        market[coin]={'status':'available','instrument_id':coin+'-USDT','market_type':'SPOT',
                      'ticker':{'last':rows[-1]['close'],'ts':now_ms},'candles_1d':rows[-90:]}
    monday=today-timedelta(days=today.weekday())
    weekly_times=[int((monday-timedelta(weeks=80-i)).timestamp()*1000) for i in range(80)]
    monthly_times=[]
    for i in range(49):
        total=today.year*12+today.month-1-49+i
        monthly_times.append(int(datetime(total//12,total%12+1,1,tzinfo=timezone.utc).timestamp()*1000))
    monthly_ends=monthly_times[1:]+[int(datetime(today.year,today.month,1,tzinfo=timezone.utc).timestamp()*1000)]
    monthly=[{'ts':ts,'available_at':end,'open':110+i*.2,'high':112+i*.2,'low':109+i*.2,
              'close':110+i*.2,'volume':1000+i,'confirm':True} for i,(ts,end) in enumerate(zip(monthly_times,monthly_ends))]
    primary=btc if asset=='BTC' else eth
    return market,{'asset':asset,'instrument_id':asset+'-USDT','retrieved_at':datetime.now(timezone.utc).isoformat(),
                   'mode':'offline_fixture','sources':[{'source':'synthetic_test_only','quality_flags':['synthetic']}],
                   'errors':[],'ticker':{'last':primary[-1]['close'],'ts':now_ms},
                   'candles':{'1D':primary,'1W':bars(weekly_times,[100+i*.2 for i in range(80)],7*DAY),'1M':monthly},
                   'specialist_markets':market,'macro':{},'macro_missing':['synthetic test omission'],
                   'fed':[],'news':[],'derivatives':{}}

def test_specialist_math_requires_aligned_matching_markets():
    markets,_=markets_and_snapshot('BTC')
    result=summarize_specialist('BTC',markets)
    assert result['status']=='available' and result['aligned_bars']==90
    assert result['own_return_30d']>result['peer_return_30d']
    assert result['relative_price_ratio_change_30d']>0
    assert result['forecast_probability'] is None
    missing=copy.deepcopy(markets);missing['ETH']['candles_1d']=missing['ETH']['candles_1d'][:-70]
    assert summarize_specialist('BTC',missing)['status']=='unavailable'
    mismatched=copy.deepcopy(markets);mismatched['ETH']['instrument_id']='ETH-USDC'
    assert summarize_specialist('BTC',mismatched)['status']=='unavailable'
    gap=copy.deepcopy(markets);del gap['BTC']['candles_1d'][-12]
    assert summarize_specialist('BTC',gap)['reason']=='Aligned 30-day window has missing UTC days'
    tampered=copy.deepcopy(markets);tampered['BTC']['candles_1d'][-1]['close']=float('nan')
    with pytest.raises(ValueError,match='invalid specialist close'):summarize_specialist('BTC',tampered)

def test_existing_v01_archives_keep_their_original_eight_role_scope():
    old=ResearchState.model_validate({'schema_version':'1.0','asset':'ETH','instrument_id':'ETH-USDT'})
    current=ResearchState(asset='ETH',instrument_id='ETH-USDT')
    assert len(old.required_roles)==8 and 'btc_specialist' not in old.required_roles
    assert len(current.required_roles)==12 and {'btc_specialist','risk_control','entry_timing'}<=set(current.required_roles)

def test_host_mode_creates_separate_btc_eth_specialist_tasks(tmp_path):
    _,snapshot=markets_and_snapshot('ETH')
    class Service:
        def collect(self,*args,**kwargs):return copy.deepcopy(snapshot)
    coordinator=Coordinator(Config(data_dir=tmp_path),Service())
    state=coordinator.research('ETH-USDT',engine='host',language='en')
    folder=tmp_path/'reports'/state.research_id/'tasks'
    btc=json.loads((folder/'btc_specialist.json').read_text())
    eth=json.loads((folder/'eth_specialist.json').read_text())
    assert len(list(folder.glob('*.json')))==12
    assert btc['agent_id']=='btc_specialist' and eth['agent_id']=='eth_specialist'
    assert 'btc_specialist' in eth['dependencies']
    assert btc['snapshot']['specialist_markets']['BTC']['instrument_id']=='BTC-USDT'
    assert state.language=='en' and state.required_roles[-2:]==['trading','chief']

@pytest.mark.parametrize('asset',['BTC','ETH'])
def test_full_research_has_two_specialists_and_both_language_reports(tmp_path,asset):
    _,snapshot=markets_and_snapshot(asset)
    class Service:
        def collect(self,*args,**kwargs):return copy.deepcopy(snapshot)
    coordinator=Coordinator(Config(data_dir=tmp_path),Service())
    state=coordinator.research(asset+'-USDT',engine='deterministic',language='en')
    assert state.language=='en' and len(state.required_roles)==12
    assert {'btc_specialist','eth_specialist'}<=set(state.results)
    assert all(state.results[name].payload['quant']['status']=='available' for name in ('btc_specialist','eth_specialist'))
    root=tmp_path/'reports'/state.research_id
    assert all((root/name).is_file() for name in ['report.zh.md','report.en.md','report.zh.html','report.en.html','market.zh.svg','market.en.svg'])
    english=(root/'report.en.md').read_text();chinese=(root/'report.zh.md').read_text()
    assert 'Who did what' in english and '每位研究员做了什么' in chinese
    assert 'BTC specialist' in english and 'BTC 专项研究员' in chinese and 'ETH 专项研究员' in chinese
    assert '<html lang="en">' in (root/'report.en.html').read_text()
    assert '<html lang="zh-CN">' in (root/'report.zh.html').read_text()
    assert (root/'report.md').read_text()==english
    state.results['btc_specialist'].payload['quant']['own_return_30d']=99
    issues=RiskResearchAudit().review(state)
    assert any(i.severity=='critical' and i.responsible_agent=='btc_specialist' for i in issues)
