"""Data service with explicit CLI -> optional MCP -> public API provenance."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import copy
import json
import math
from pathlib import Path
from typing import Any
from atlas.integrations.skill_adapter import OfficialSkillAdapter,validate_instrument,safe_error
from .common import PublicTransport,RequestBudget,ProviderError,now_iso
from .okx_public_api import OKXPublicAPI,BAR_MAP,normalize_candles,instrument_type,close_time
from .okx_mcp import OKXMCPBridge
from .supplemental import SupplementalProvider,plain_text


class DataService:
    def __init__(self,config:Any,transport:PublicTransport|None=None):
        self.config=config
        self.budget=RequestBudget(int(getattr(config,'max_data_requests',90)),float(getattr(config,'min_request_interval',0.12)))
        self.transport=transport or PublicTransport(config,self.budget)
        self.api=OKXPublicAPI(self.transport,getattr(config,'api_base_url','https://openapi.okx.com'))
        self.adapter=OfficialSkillAdapter(config)
        self.mcp=OKXMCPBridge(getattr(config,'mcp_command',None),float(getattr(config,'timeout_seconds',12)))
        self.supplemental=SupplementalProvider(self.transport)
        self.cli_failed=False
        self.errors=[]
        self.sources=[]
    async def acollect(self,instrument_id,timeframes,limit=300):
        import asyncio
        return await asyncio.to_thread(self.collect,instrument_id,timeframes,limit)
    def close(self):self.transport.close()
    def capabilities(self,refresh:bool=False):return self.adapter.discover(refresh)
    def _error(self,provider:str,exc:Any,**extra):
        item=exc.as_dict() if isinstance(exc,ProviderError) else dict(exc) if isinstance(exc,dict) else {'provider':provider,'code':'fetch_error','message':safe_error(exc)}
        item.update(extra);item.setdefault('severity','warning');self.errors.append(item)
    def _source(self,capability:str,meta:dict,inst:str,unit:str=''):
        self.sources.append({'source':meta.get('source','unknown'),'source_url':meta.get('source_url',''),
            'instrument':inst,'timestamp':meta.get('timestamp'),'retrieved_at':meta.get('retrieved_at',now_iso()),
            'unit':unit or meta.get('unit',''),'timezone':'UTC','status':'available',
            'freshness':meta.get('freshness_seconds',0),'quality_flags':meta.get('quality_flags',[]),
            'capability':capability,'cached':meta.get('cached',False),'routing_reason':meta.get('routing_reason')})
    def _get(self,capability:str,params:dict,inst:str)->tuple[list,dict]:
        if capability=='candles' and str(params.get('bar','')).endswith('utc'):
            # Installed official CLI/MCP 1.4.9 enum rejects UTC bars. Preserve UTC via public API.
            data,meta=self.api.candles(inst,str(params['bar']).replace('utc',''),params.get('limit',300),int(params['after']) if params.get('after') else None)
            meta['routing_reason']='CLI 1.4.9 candle enum lacks UTC daily/weekly/monthly bars'
            return data,meta
        if not getattr(self.config,'offline',False) and self.adapter.cli and not self.cli_failed:
            self.budget.consume()
            result=self.adapter.invoke(capability,**params)
            if result['ok']:
                data=result['data'];return (data if isinstance(data,list) else [data]),{'source':'okx_cli','source_url':'https://www.okx.com/docs-v5/en/','retrieved_at':now_iso(),'cached':False}
            self.cli_failed=True;self._error('okx_cli',result['error'],fallback_attempted=True)
        if not getattr(self.config,'offline',False) and self.mcp.command:
            self.budget.consume();result=self.mcp.call(capability,params)
            if result['ok']:
                data=result['data'];return (data if isinstance(data,list) else [data]),{'source':'okx_mcp','source_url':'https://github.com/okx/agent-trade-kit','retrieved_at':now_iso(),'cached':False}
            self._error('okx_mcp',result['error'],fallback_attempted=True)
        if capability=='candles':return self.api.candles(inst,params.get('bar','1D').replace('utc',''),params.get('limit',300),int(params['after']) if params.get('after') else None)
        return getattr(self.api,capability)(inst)
    def _collect_specialist_markets(self,snapshot:dict)->dict:
        markets={}
        main=snapshot['instrument_id'];market_type=instrument_type(main);quote=main.split('-')[1]
        for asset in ('BTC','ETH'):
            suffix='-'+main.split('-',2)[2] if market_type=='FUTURES' else '-SWAP' if market_type=='SWAP' else ''
            instrument=main if snapshot['asset']==asset else asset+'-'+quote+suffix
            try:
                if instrument==main and snapshot.get('ticker') and snapshot.get('candles',{}).get('1D'):
                    ticker=snapshot['ticker'];rows=snapshot['candles']['1D'][-90:]
                    provenance=[{'source':'primary_snapshot','capability':'ticker + 1D candles'}]
                else:
                    instruments,meta_inst=self._get('instruments',{'instId':instrument,'instType':market_type},instrument)
                    if not any(isinstance(x,dict) and x.get('instId')==instrument for x in instruments):raise ValueError('peer instrument not verified on OKX')
                    ticker_rows,meta_ticker=self._get('ticker',{'instId':instrument},instrument)
                    if not ticker_rows:raise ValueError('peer ticker missing')
                    raw=ticker_rows[0];last=float(raw['last']);ts=int(raw['ts'])
                    if not math.isfinite(last) or last<=0:raise ValueError('peer ticker invalid')
                    ticker={'last':last,'ts':ts,'instrument_id':instrument,'source':meta_ticker.get('source','unknown')}
                    candles,meta_candles=self._get('candles',{'instId':instrument,'bar':BAR_MAP['1D'],'limit':90},instrument)
                    rows,flags=normalize_candles(candles,'1D')
                    if flags:self._error('okx_specialist',{'provider':'okx_specialist','code':'peer_candle_quality','message':','.join(flags)},asset=asset)
                    provenance=[meta_inst,meta_ticker,meta_candles]
                    self._source('specialist:'+asset+':ticker',meta_ticker,instrument)
                    self._source('specialist:'+asset+':1D',meta_candles,instrument)
                markets[asset]={'status':'available' if len(rows)>=31 else 'unavailable','instrument_id':instrument,
                                'market_type':market_type,'ticker':ticker,'candles_1d':rows,'retrieved_at':now_iso(),
                                'sources':provenance,'quality_flags':[] if len(rows)>=31 else ['fewer_than_31_daily_bars']}
            except Exception as exc:
                markets[asset]={'status':'unavailable','instrument_id':instrument,'market_type':market_type,
                                'ticker':{},'candles_1d':[],'quality_flags':['source_unavailable']}
                self._error('okx_specialist',exc,asset=asset)
        return markets
    def collect(self,instrument_id:str,timeframes:list[str]|tuple[str,...],limit:int=300)->dict:
        validate_instrument(instrument_id)
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=5000:raise ValueError('Requested candle limit must be integer 1..5000')
        timeframes=list(timeframes)
        if not timeframes or any(bar not in BAR_MAP for bar in timeframes):raise ValueError('Invalid research timeframes')
        fixture=getattr(self.config,'fixture',None)
        if fixture:
            # Fixtures are user-selected local snapshots; never masquerade as live data.
            obj=json.loads(Path(fixture).read_text())
            if obj.get('instrument_id')!=instrument_id:raise ValueError('Fixture instrument differs from requested instrument')
            obj=copy.deepcopy(obj);obj['mode']='offline_fixture';obj['fixture_path']=str(Path(fixture).resolve())
            obj.setdefault('errors',[]);obj.setdefault('sources',[]);obj.setdefault('retrieved_at',now_iso())
            for source in obj['sources']:source['quality_flags']=list(set(source.get('quality_flags',[])+['offline_fixture']))
            for bar in timeframes:
                rows=obj.get('candles',{}).get(bar,[])
                normalized,flags=normalize_candles(rows,bar)
                obj.setdefault('candles',{})[bar]=normalized
                for flag in flags:obj['errors'].append({'provider':'fixture','code':flag,'message':flag,'severity':'warning'})
            for asset,market in obj.get('specialist_markets',{}).items():
                if asset not in {'BTC','ETH'}:raise ValueError('Fixture specialist asset must be BTC or ETH')
                if market.get('status')=='available':
                    normalized,flags=normalize_candles(market.get('candles_1d',[]),'1D')
                    market['candles_1d']=normalized
                    market.setdefault('quality_flags',[]).extend(['offline_fixture',*flags])
            return obj
        self.errors=[];self.sources=[]
        snapshot={'instrument_id':instrument_id,'asset':instrument_id.split('-')[0],'retrieved_at':now_iso(),
                  'mode':'cache' if getattr(self.config,'offline',False) else 'live','sources':self.sources,'errors':self.errors,
                  'ticker':{},'candles':{},'derivatives':{},'macro':{},'fed':[],'news':[],
                  'macro_missing':['PMI: no verified freely redistributable current source configured','ICE DXY: not substituted by broad-dollar proxy','Global liquidity: no canonical global aggregate configured'],
                  'news_coverage':'official central-bank/macro release feeds; crypto industry coverage may be unavailable'}
        inst_type=instrument_type(instrument_id)
        try:
            instruments,meta=self._get('instruments',{'instId':instrument_id,'instType':inst_type},instrument_id)
            if not instruments or not any(x.get('instId')==instrument_id for x in instruments if isinstance(x,dict)):
                raise ProviderError('invalid_instrument','Instrument not found on OKX','okx')
            snapshot['instrument']=next(x for x in instruments if x.get('instId')==instrument_id)
            self._source('instruments',meta,instrument_id)
        except Exception as exc:
            self._error('okx',exc,severity='error');return snapshot
        try:
            data,meta=self._get('ticker',{'instId':instrument_id},instrument_id)
            if not data:raise ProviderError('empty_ticker','Ticker data unavailable','okx')
            raw=data[0];last=float(raw['last']);ts=int(raw['ts'])
            if not math.isfinite(last) or last<=0:raise ValueError('Invalid ticker price')
            if ts>int(datetime.now(timezone.utc).timestamp()*1000)+60000:raise ValueError('Ticker timestamp is in the future')
            freshness=max(0,int(datetime.now(timezone.utc).timestamp())-ts/1000)
            snapshot['ticker']={'last':last,'ts':ts,'instrument_id':instrument_id,'price_basis':'perpetual_last' if inst_type=='SWAP' else 'spot_last' if inst_type=='SPOT' else 'futures_last','source':meta['source'],'retrieved_at':meta['retrieved_at'],'freshness_seconds':freshness}
            if freshness>120:meta.setdefault('quality_flags',[]).append('stale_price');self._error('okx',{'provider':'okx','code':'stale_price','message':'Ticker older than 120s'},severity='error')
            meta['timestamp']=ts;meta['freshness_seconds']=freshness;self._source('ticker',meta,instrument_id,instrument_id.split('-')[1])
        except Exception as exc:self._error('okx',exc,severity='error')
        for bar in timeframes:
            try:
                data,meta=self._get('candles',{'instId':instrument_id,'bar':BAR_MAP[bar],'limit':min(limit,300)},instrument_id)
                candles,flags=normalize_candles(data,bar)
                if limit>300:
                    after=candles[0]['ts'] if candles else None
                    for _ in range((limit+299)//300):
                        if len(candles)>=limit:break
                        try:page,page_meta=self.api.candles(instrument_id,bar,300,after=after,history=True)
                        except Exception as exc:self._error('okx_public_api',exc,timeframe=bar);break
                        if not page or (after is not None and page[0]['ts']>=after):break
                        candles+=page;after=page[0]['ts'];candles,page_flags=normalize_candles(candles,bar);flags+=page_flags
                        self._source('candles:'+bar+':history_page',page_meta,instrument_id)
                snapshot['candles'][bar]=candles[-limit:]
                if candles and int(datetime.now(timezone.utc).timestamp()*1000)>close_time(candles[-1]['available_at'],bar)+120000:
                    flags.append('stale_candles')
                    self._error('okx',{'provider':'okx','code':'stale_candles','message':'Latest confirmed '+bar+' candle is missing a completed period'},severity='error')
                meta['quality_flags']=sorted(set(meta.get('quality_flags',[])+flags))
                if candles:meta['timestamp']=candles[-1]['available_at']
                if len(candles)<max(30,limit//4):meta['quality_flags'].append('limited_history')
                self._source('candles:'+bar,meta,instrument_id,'base_currency' if inst_type=='SPOT' else 'contracts')
            except Exception as exc:snapshot['candles'][bar]=[];self._error('okx',exc,severity='error',timeframe=bar)
        optional=[('orderbook','orderbook')]
        if inst_type=='SWAP':optional.extend([('funding_rate','funding_rate'),('open_interest','open_interest'),('mark_price','mark_price')])
        for capability,key in optional:
            try:
                params={'instId':instrument_id}
                if capability in {'mark_price','open_interest'}:params['instType']=inst_type
                if capability=='orderbook':params['sz']=20
                data,meta=self._get(capability,params,instrument_id)
                if not data:continue
                raw=data[0]
                if capability=='funding_rate':snapshot['derivatives'][key]=float(raw['fundingRate']);snapshot['derivatives']['funding_time']=raw.get('fundingTime')
                elif capability=='open_interest':snapshot['derivatives'][key]=float(raw['oi']);snapshot['derivatives']['open_interest_unit']='contracts'
                elif capability=='mark_price':snapshot['derivatives'][key]=float(raw['markPx'])
                else:
                    snapshot['orderbook']=raw
                    bids,asks=raw.get('bids',[]),raw.get('asks',[])
                    bid_size=sum(float(x[1]) for x in bids);ask_size=sum(float(x[1]) for x in asks)
                    if bid_size+ask_size:snapshot['derivatives']['depth_imbalance']=(bid_size-ask_size)/(bid_size+ask_size)
                    if bids and asks:snapshot['derivatives']['spread_bps']=(float(asks[0][0])-float(bids[0][0]))/((float(asks[0][0])+float(bids[0][0]))/2)*10000
                meta['timestamp']=raw.get('ts',raw.get('fundingTime'));self._source(capability,meta,instrument_id)
            except Exception as exc:self._error('okx',exc)
        if getattr(self.config,'fetch_supplemental',True):
            with ThreadPoolExecutor(max_workers=2) as pool:
                macro_future=pool.submit(self.supplemental.macro)
                news_future=pool.submit(self.supplemental.news)
                macro,sources,errors=macro_future.result();snapshot['macro']=macro;self.sources+=sources;self.errors+=errors
                news,sources,errors=news_future.result();snapshot['news']=news;self.sources+=sources;self.errors+=errors
                snapshot['fed']=[x for x in news if x['event_category'].startswith('fed_')]
            if not getattr(self.config,'offline',False) and self.adapter.cli:
                # Read-only crypto news is optional and may require separate entitlements.
                try:
                    self.budget.consume();result=self.adapter.invoke('news_latest',coins=snapshot['asset'],limit=10,lang='en-US')
                    if result['ok']:
                        snapshot['crypto_news_raw']=result['data']
                        raw_news=result['data']
                        if isinstance(raw_news,list) and raw_news:raw_news=raw_news[0]
                        details=raw_news.get('details',[]) if isinstance(raw_news,dict) else []
                        for item in details:
                            try:
                                published=datetime.fromtimestamp(int(item.get('cTime',item.get('createTime')))/1000,timezone.utc).isoformat()
                                source_url=item.get('url') or item.get('sourceUrl')
                                if source_url and not str(source_url).startswith('https://'):source_url=None
                                snapshot['news'].append({'event_id':'okx-news-'+str(item.get('id','')),
                                    'title':plain_text(str(item.get('title','')))[:500],'source':'OKX news aggregation',
                                    'source_url':source_url,'published_at':published,'event_occurred_at':None,'observed_at':now_iso(),
                                    'affected_assets':[snapshot['asset']],'event_category':'crypto_news',
                                    'evidence':[plain_text(str(item.get('summary',item.get('content',''))))[:2000]],
                                    'verification_status':'aggregated_unverified','potential_market_impact':'requires_contextual_analysis',
                                    'content_untrusted':True,'quality_flags':[] if source_url else ['original_article_url_missing']})
                            except (TypeError,ValueError,OverflowError):continue
                        self._source('news_latest',{'source':'okx_cli','source_url':'https://www.okx.com/docs-v5/en/','retrieved_at':now_iso()},instrument_id)
                    else:self._error('okx_news',result['error'])
                except Exception as exc:self._error('okx_news',exc)
        if getattr(self.config,'fetch_supplemental',True) and not getattr(self.config,'offline',False) and self.adapter.cli:
            snapshot['sentiment_data']={}
            for capability,params in [('coin_sentiment',{'coins':snapshot['asset']}),('smartmoney_signal',{'instCcyList':snapshot['asset'],'period':'7','lmtNum':100})]:
                try:
                    self.budget.consume();result=self.adapter.invoke(capability,**params)
                    if result['ok']:
                        snapshot['sentiment_data'][capability]={'data':result['data'],'retrieved_at':now_iso(),'source':'okx_cli','quality_flags':['raw_analytics_not_directional_prediction']}
                        self._source(capability,{'source':'okx_cli','source_url':'https://github.com/okx/agent-skills','retrieved_at':now_iso()},instrument_id)
                    else:self._error('okx_sentiment',result['error'])
                except Exception as exc:self._error('okx_sentiment',exc)
        snapshot['specialist_markets']=self._collect_specialist_markets(snapshot)
        snapshot['requests_used']=self.budget.used
        snapshot['sources']=self.sources;snapshot['errors']=self.errors
        return snapshot
    def history(self,instrument_id:str,bar:str='1D',years:int=5)->dict:
        validate_instrument(instrument_id)
        if not 1<=years<=10:raise ValueError('History years must be 1..10')
        if bar not in BAR_MAP:raise ValueError('Unsupported interval')
        now=datetime.now(timezone.utc);start=now-timedelta(days=years*365.25);threshold=int(start.timestamp()*1000)
        fixture=getattr(self.config,'fixture',None)
        if fixture:
            obj=json.loads(Path(fixture).read_text())
            if obj.get('instrument_id')!=instrument_id:raise ValueError('Fixture instrument mismatch')
            data,flags=normalize_candles(obj.get('candles',{}).get(bar,[]),bar)
            return {'data':data,'sources':obj.get('sources',[]),'errors':[],'limitations':['Explicit offline fixture; coverage is not live data',*flags],
                    'complete':bool(data and data[0]['ts']<=threshold),'requested_start':start.isoformat(),
                    'coverage_start':data[0]['ts'] if data else None,'coverage_end':data[-1]['available_at'] if data else None,'mode':'offline_fixture'}
        data=[];sources=[];errors=[];after=None
        try:
            # First page attempts official CLI, preserving the normal routing priority.
            first,meta=self._get('candles',{'instId':instrument_id,'bar':BAR_MAP[bar],'limit':300},instrument_id)
            first,flags=normalize_candles(first,bar);data+=first;sources.append(meta)
            if first:after=first[0]['ts']
        except Exception as exc:errors.append({'provider':'okx','code':getattr(exc,'code','fetch_error'),'message':safe_error(exc)})
        for _ in range(75):
            if data and min(x['ts'] for x in data)<=threshold:break
            try:
                page,meta=self.api.candles(instrument_id,bar,300,after=after,history=True)
                sources.append(meta)
                if not page:break
                earliest=page[0]['ts']
                if after is not None and earliest>=after:break
                data+=page;after=earliest
            except Exception as exc:
                errors.append({'provider':'okx_public_api','code':getattr(exc,'code','fetch_error'),'message':safe_error(exc)});break
        data,flags=normalize_candles(data,bar)
        # Retain one warm-up bar preceding the requested boundary, not arbitrary old periods.
        first_index=next((i for i,x in enumerate(data) if x['ts']>=threshold),len(data))
        data=data[max(0,first_index-1):]
        complete=bool(data and data[0]['ts']<=threshold)
        return {'data':data,'sources':sources,'errors':errors,'limitations':flags+([] if complete else ['Requested historical coverage incomplete; listing age, network or budget may limit data']),
                'complete':complete,'requested_start':start.isoformat(),'coverage_start':data[0]['ts'] if data else None,
                'coverage_end':data[-1]['available_at'] if data else None,'mode':'cache' if getattr(self.config,'offline',False) else 'live','requests_used':self.budget.used}
    def events(self,event_type:str,start_year:int=2021)->dict:return self.supplemental.events(event_type,start_year)
