"""OKX V5 public endpoints; UTC bars, ascending confirmed candles."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import calendar
import math
from typing import Any
from urllib.parse import urlparse
from .common import PublicTransport, ProviderError
from atlas.integrations.skill_adapter import validate_instrument

BAR_MAP={'1D':'1Dutc','1W':'1Wutc','1M':'1Mutc','4H':'4Hutc','1H':'1H','15m':'15m','5m':'5m','1m':'1m'}
ALLOWED_HOSTS={'www.okx.com','openapi.okx.com','us.okx.com','eea.okx.com','tr.okx.com'}


def instrument_type(instrument_id:str)->str:
    validate_instrument(instrument_id)
    return 'SWAP' if instrument_id.endswith('-SWAP') else ('FUTURES' if instrument_id.rsplit('-',1)[-1].isdigit() else 'SPOT')


def close_time(ts:int,bar:str)->int:
    dt=datetime.fromtimestamp(ts/1000,timezone.utc)
    if bar in {'1M','1Mutc'}:
        year,month=(dt.year+1,1) if dt.month==12 else (dt.year,dt.month+1)
        return int(dt.replace(year=year,month=month,day=1).timestamp()*1000)
    days={'1D':1,'1Dutc':1,'1W':7,'1Wutc':7}
    hours={'4H':4,'4Hutc':4,'1H':1}
    delta=timedelta(days=days[bar]) if bar in days else timedelta(hours=hours[bar]) if bar in hours else timedelta(minutes=int(bar[:-1]))
    return int((dt+delta).timestamp()*1000)


def normalize_candles(rows:list,bar:str,now_ms:int|None=None)->tuple[list[dict],list[str]]:
    result={};flags=[];now_ms=int(datetime.now(timezone.utc).timestamp()*1000) if now_ms is None else now_ms
    for row in rows:
        try:
            if isinstance(row,dict):
                ts=int(row['ts']);v=[float(row[k]) for k in ('open','high','low','close','volume')]
                confirmed=row.get('confirm',False) in (True,1,'1')
            else:
                ts=int(row[0]);v=list(map(float,row[1:6]));confirmed=len(row)>8 and str(row[8])=='1'
            end=close_time(ts,bar)
            available=int(row.get('available_at',end)) if isinstance(row,dict) else end
            if available<end:
                flags.append('invalid_available_at_excluded');continue
            if available>now_ms:
                flags.append('not_yet_available_candle');continue
            if not confirmed or end>now_ms:
                flags.append('unclosed_candles_excluded');continue
            if not all(math.isfinite(x) for x in v) or min(v[:4])<=0 or v[4]<0 or v[1]<max(v[0],v[2],v[3]) or v[2]>min(v[0],v[1],v[3]):
                flags.append('invalid_ohlcv_excluded');continue
            if ts in result:flags.append('duplicate_timestamps_removed')
            result[ts]={'ts':ts,**dict(zip(('open','high','low','close','volume'),v)),'confirm':True,'available_at':available}
        except (TypeError,ValueError,KeyError,IndexError,OverflowError):flags.append('malformed_candles_excluded')
    out=sorted(result.values(),key=lambda x:x['ts'])
    if any(close_time(a['ts'],bar)!=b['ts'] for a,b in zip(out,out[1:])):flags.append('candle_gaps')
    return out,sorted(set(flags))


class OKXPublicAPI:
    def __init__(self,transport:PublicTransport,base_url:str='https://openapi.okx.com'):
        url=urlparse(base_url)
        if url.scheme!='https' or url.hostname not in ALLOWED_HOSTS or url.path not in {'','/'} or url.username or url.password or url.query:
            raise ValueError('OKX API base URL must be an official regional HTTPS host')
        self.transport=transport;self.base_url=base_url.rstrip('/')
    def call(self,path:str,params:dict)->tuple[list,dict]:
        if not path.startswith('/api/v5/') or any(x in path for x in ('trade/','asset/','account/')):
            raise PermissionError('Only public market endpoints are available')
        obj,meta=self.transport.json(self.base_url+path,params,ttl=int(getattr(self.transport.config,'cache_ttl_seconds',30)))
        return obj.get('data',[]) if isinstance(obj,dict) else obj,dict(meta,source='okx_public_api',timezone='UTC',status='available')
    def instruments(self,inst_id:str):return self.call('/api/v5/public/instruments',{'instType':instrument_type(inst_id),'instId':validate_instrument(inst_id)})
    def ticker(self,inst_id:str):return self.call('/api/v5/market/ticker',{'instId':validate_instrument(inst_id)})
    def candles(self,inst_id:str,bar:str='1D',limit:int=300,after:int|None=None,history:bool=False):
        if bar not in BAR_MAP:raise ValueError('Unsupported timeframe')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=300:raise ValueError('Candle page limit must be integer 1..300')
        params={'instId':validate_instrument(inst_id),'bar':BAR_MAP[bar],'limit':limit}
        if after is not None:params['after']=str(int(after))
        rows,meta=self.call('/api/v5/market/history-candles' if history else '/api/v5/market/candles',params)
        data,flags=normalize_candles(rows,bar)
        return data,dict(meta,quality_flags=flags,unit='base_currency' if instrument_type(inst_id)=='SPOT' else 'contracts',bar=BAR_MAP[bar],instrument=inst_id)
    def orderbook(self,inst_id:str):return self.call('/api/v5/market/books',{'instId':validate_instrument(inst_id),'sz':'20'})
    def funding_rate(self,inst_id:str):return self.call('/api/v5/public/funding-rate',{'instId':validate_instrument(inst_id)})
    def open_interest(self,inst_id:str):return self.call('/api/v5/public/open-interest',{'instId':validate_instrument(inst_id),'instType':instrument_type(inst_id)})
    def mark_price(self,inst_id:str):return self.call('/api/v5/public/mark-price',{'instId':validate_instrument(inst_id),'instType':instrument_type(inst_id)})
