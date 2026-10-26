"""Official-source macro snapshots and release feeds, with explicit vintage limits."""
from __future__ import annotations
import csv
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import io
import re
from urllib.parse import urljoin
from xml.etree import ElementTree
from .common import PublicTransport,ProviderError,now_iso

# FRED is the official distributor; each series retains its own original source/license.
SERIES={
 'CPIAUCSL':('US CPI','index'), 'CPILFESL':('US core CPI','index'),
 'PCEPI':('US PCE price index','index'),'PCEPILFE':('US core PCE price index','index'),
 'PAYEMS':('US nonfarm payroll employment','thousands_of_persons'),'UNRATE':('US unemployment','percent'),
 'GDPC1':('US real GDP','billions_chained_dollars'),
 'DTWEXBGS':('Broad US dollar index (proxy, not ICE DXY)','index'),
 'DGS2':('US Treasury 2-year yield','percent'),'DGS10':('US Treasury 10-year yield','percent'),
 'DFII10':('US real 10-year Treasury yield','percent'),'T10Y2Y':('10y minus 2y curve','percentage_points'),
 'NFCI':('Chicago Fed financial conditions index','index'), 'WALCL':('Fed total assets','millions_USD'),
 'M2SL':('US M2 money stock (liquidity proxy, not global liquidity)','billions_USD'),
 'SP500':('S&P 500 index (risk asset proxy)','index'), 'DFEDTARU':('Fed funds target upper bound','percent')}
FEEDS=[('Federal Reserve monetary policy','https://www.federalreserve.gov/feeds/press_monetary.xml','fed_policy'),
       ('Federal Reserve speeches','https://www.federalreserve.gov/feeds/speeches.xml','fed_speech'),
       ('BLS latest releases','https://www.bls.gov/feed/bls_latest.rss','macro_release')]


def plain_text(value:str)->str:
    return html.unescape(re.sub(r'<[^>]+>',' ',value or '')).strip()


def parse_feed(text:str,source:str,url:str,observed_at:str|None=None)->list[dict]:
    root=ElementTree.fromstring(text);observed_at=observed_at or now_iso();events=[]
    for item in root.findall('.//item'):
        title=plain_text(item.findtext('title',''))[:500]
        link=item.findtext('link','').strip()
        date=item.findtext('pubDate','').strip()
        try:
            dt=parsedate_to_datetime(date).astimezone(timezone.utc)
        except (ValueError,TypeError,AttributeError):continue
        if not title or not link.startswith('https://'):continue
        if dt>datetime.now(timezone.utc)+timedelta(minutes=10):continue
        events.append({'event_id':hashlib.sha256((link+title).encode()).hexdigest()[:20],
                       'title':title,'source':source,'source_url':link,'published_at':dt.isoformat(),
                       'event_occurred_at':None,'observed_at':observed_at,'affected_assets':['BTC','ETH'],
                       'event_category':'fed_policy' if 'Federal' in source else 'macro_release',
                       'evidence':[plain_text(item.findtext('description',''))[:2000]],
                       'verification_status':'official_source','potential_market_impact':'requires_contextual_analysis',
                       'content_untrusted':True,'quality_flags':['publication_time_not_event_time']})
    return events


class SupplementalProvider:
    def __init__(self,transport:PublicTransport):self.transport=transport
    def macro(self)->tuple[dict,list, list]:
        out={};sources=[];errors=[]
        def fetch(key):
            title,unit=SERIES[key]
            start=(datetime.now(timezone.utc)-timedelta(days=3*366)).date().isoformat()
            text,meta=self.transport.get('https://fred.stlouisfed.org/graph/',{'id':key,'cosd':start},ttl=21600,retries=0)
            # Official downloadable CSV endpoint is graph.csv, not HTML chart.
            return key,title,unit,text,meta
        def fetch_csv(key):
            title,unit=SERIES[key]
            start=(datetime.now(timezone.utc)-timedelta(days=3*366)).date().isoformat()
            text,meta=self.transport.get('https://fred.stlouisfed.org/graph/fredgraph.csv',{'id':key,'cosd':start},ttl=21600,retries=0)
            reader=csv.reader(io.StringIO(text));header=next(reader,[])
            if not header or header[0] not in {'DATE','observation_date'}:raise ProviderError('invalid_csv','FRED did not return observation CSV','fred')
            obs=[]
            for row in reader:
                try:
                    if len(row)>1 and re.fullmatch(r'\d{4}-\d{2}-\d{2}',row[0]):obs.append({'date':row[0],'value':float(row[1])})
                except ValueError:continue
            if not obs:raise ProviderError('empty_series',key+' returned no observations','fred')
            return key,{'name':title,'source':'FRED','source_url':'https://fred.stlouisfed.org/series/'+key,'unit':unit,
                        'observations':obs[-800:],'retrieved_at':meta['retrieved_at'],'status':'available',
                        'vintage':'latest_revised_not_point_in_time','timezone':'UTC','cached':meta['cached'],
                        'quality_flags':['observation_date_is_not_release_time','not_suitable_for_point_in_time_macro_backtest']},meta
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures={pool.submit(fetch_csv,key):key for key in SERIES}
            for future in as_completed(futures):
                key=futures[future]
                try:
                    key,data,meta=future.result();out[key]=data;sources.append(dict(meta,source='FRED',instrument=key,unit=data['unit'],timezone='UTC',status='available'))
                except Exception as exc:
                    out[key]={'name':SERIES[key][0],'status':'missing','observations':[],'source_url':'https://fred.stlouisfed.org/series/'+key}
                    errors.append({'provider':'fred','code':getattr(exc,'code','fetch_error'),'series':key,'message':str(exc)[:200],'severity':'warning'})
        return out,sources,errors
    def news(self)->tuple[list,list,list]:
        events=[];sources=[];errors=[]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(self.transport.get,url,None,1800,0):(name,url,kind) for name,url,kind in FEEDS}
            for future in as_completed(futures):
                name,url,kind=futures[future]
                try:
                    text,meta=future.result();items=parse_feed(text,name,url,meta['retrieved_at'])
                    for item in items:item['event_category']=kind
                    events+=items;sources.append(dict(meta,source=name,status='available',unit='release',timezone='UTC'))
                except Exception as exc:errors.append({'provider':name,'code':getattr(exc,'code','feed_error'),'message':str(exc)[:200],'severity':'warning'})
        unique={x['event_id']:x for x in events}
        return sorted(unique.values(),key=lambda x:x['published_at'],reverse=True)[:60],sources,errors
    def events(self,event_type:str,start_year:int=2021)->dict:
        event_type=event_type.upper()
        if event_type not in {'FOMC','CPI'}:raise ValueError('Supported official historical events: FOMC, CPI; other events require user-provided source-verified JSON')
        url='https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm' if event_type=='FOMC' else 'https://www.bls.gov/bls/news-release/cpi.htm'
        try:text,meta=self.transport.get(url,ttl=86400,retries=1)
        except Exception as exc:return {'events':[],'sources':[],'errors':[{'provider':event_type,'code':getattr(exc,'code','fetch_error'),'message':str(exc)}],'limitations':['Historical event source unavailable']}
        if event_type=='FOMC':dates=re.findall(r'(?:href=[\"\'])?([^\"\'<>\s]*?/monetary(\d{8})a\.htm)',text)
        else:dates=re.findall(r'(?:href=[\"\'])?([^\"\'<>\s]*?/cpi_(\d{8})\.htm)',text)
        out={};today=datetime.now(timezone.utc)
        for path,date in dates:
            try:
                dt=datetime.strptime(date,'%Y%m%d' if event_type=='FOMC' else '%m%d%Y').replace(tzinfo=timezone.utc)
                if dt.year<start_year or dt>today:continue
                available=dt+timedelta(days=1)
                event={'event_id':event_type+'-'+dt.date().isoformat(),'event_type':event_type,
                       'title':event_type+' official release '+dt.date().isoformat(),
                       'event_time':available.isoformat(),'publication_time':dt.date().isoformat(),
                       'first_available_time':available.isoformat(),'expected_value':None,'actual_value':None,'surprise':None,
                       'source':'Federal Reserve' if event_type=='FOMC' else 'BLS','source_url':urljoin(url,path),
                       'affected_assets':['BTC','ETH'],'market_regime':None,'time_precision':'date_only',
                       'quality_flags':['exact_release_time_not_verified','conservative_next_UTC_day_entry','expectations_unavailable']}
                out[event['event_id']]=event
            except ValueError:continue
        time_sources=[];time_errors=[]
        if event_type=='FOMC' and out:
            def verify_release(event):
                try:
                    body,source_meta=self.transport.get(event['source_url'],ttl=30*86400,retries=0)
                    stamp=release_timestamp(body,event['event_id'].split('-',1)[1])
                    if stamp:
                        event={**event,'event_time':stamp,'publication_time':stamp,'first_available_time':stamp,'time_precision':'official_release_minute','quality_flags':['expectations_unavailable'],'release_time_basis':'Explicit For release at time and EST/EDT printed on official statement'}
                    return event,source_meta,None
                except Exception as exc:return event,None,{'provider':'Fed release timestamp','code':getattr(exc,'code','fetch_error'),'message':str(exc)[:200],'event_id':event['event_id']}
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as pool:
                for event,source_meta,error in pool.map(verify_release,list(out.values())):
                    out[event['event_id']]=event
                    if source_meta:time_sources.append(source_meta)
                    if error:time_errors.append(error)
        return {'events':sorted(out.values(),key=lambda x:x['event_time']),'sources':[meta]+time_sources,'errors':time_errors,
                'limitations':['Release dates come from official archive links; exact times are used only when explicitly printed with EST/EDT on the official statement. Unverified date-only releases remain rejected by point-in-time studies.',
                               'No historical consensus forecasts or release vintages supplied; surprise-conditioned macro inference is unavailable.',
                               'Archive coverage is bounded by the official page, not a guaranteed complete five-year event universe.']}


def release_timestamp(body:str,release_date:str)->str|None:
    """Use explicitly printed timezone, never assume a standard FOMC meeting hour."""
    text=plain_text(body)
    match=re.search(r'For release at\s+(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\s*(EDT|EST)',text,re.I)
    if not match:return None
    hour=int(match.group(1));minute=int(match.group(2) or 0)
    if not 1<=hour<=12 or not 0<=minute<=59:return None
    meridian=match.group(3).lower().replace('.','');hour=hour%12+(12 if meridian=='pm' else 0)
    offset=-4 if match.group(4).upper()=='EDT' else -5
    day=datetime.fromisoformat(release_date)
    local=day.replace(hour=hour,minute=minute,tzinfo=timezone(timedelta(hours=offset)))
    return local.astimezone(timezone.utc).isoformat()
