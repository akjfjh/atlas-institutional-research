"""Bounded pooled HTTP, data-request budget, provenance and public-data cache."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import threading
import tempfile
import time
from datetime import datetime,timezone
from typing import Any
from urllib.parse import urlparse
import httpx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProviderError(RuntimeError):
    def __init__(self,code:str,message:str,provider:str='http'):
        super().__init__(message); self.code=code; self.provider=provider
    def as_dict(self): return {'provider':self.provider,'code':self.code,'message':str(self)}


class RequestBudget:
    def __init__(self,maximum:int=80,interval:float=0.12):
        self.maximum=maximum; self.used=0; self.interval=interval; self.lock=threading.Lock(); self.last=0.0
    def consume(self):
        with self.lock:
            if self.used>=self.maximum: raise ProviderError('budget_exhausted','Maximum data requests reached')
            delay=self.interval-(time.monotonic()-self.last)
            if delay>0: time.sleep(delay)
            self.used+=1; self.last=time.monotonic()


class PublicTransport:
    """Only GETs public data. Never receives or reads OKX credentials."""
    def __init__(self,config:Any,budget:RequestBudget,client:httpx.Client|None=None):
        self.config=config; self.budget=budget
        self.cache_dir=Path(config.data_dir)/'cache'; self.cache_dir.mkdir(parents=True,exist_ok=True)
        self.client=client or httpx.Client(timeout=float(getattr(config,'timeout_seconds',12)),follow_redirects=True,
                                          limits=httpx.Limits(max_connections=6,max_keepalive_connections=4),
                                          trust_env=getattr(config,'trust_env',True))
        self.owns_client=client is None
    def close(self):
        if self.owns_client:self.client.close()
    def get(self,url:str,params:dict|None=None,ttl:int=30,retries:int|None=None)->tuple[str,dict]:
        scheme=urlparse(url)
        if scheme.scheme!='https' or scheme.username or scheme.password:
            raise ProviderError('unsafe_url','Only credential-free HTTPS source URLs are permitted')
        key=hashlib.sha256((url+json.dumps(params or {},sort_keys=True)).encode()).hexdigest()
        path=self.cache_dir/(key+'.json')
        if path.exists():
            try:
                cached=json.loads(path.read_text())
                age=time.time()-cached['saved_at']
                if age<=ttl or getattr(self.config,'offline',False):
                    return cached['body'],{'source_url':url,'retrieved_at':cached['retrieved_at'],'cached':True,
                                           'freshness_seconds':age,'quality_flags':['offline_cache'] if getattr(self.config,'offline',False) else []}
            except (ValueError,OSError,KeyError): pass
        if getattr(self.config,'offline',False): raise ProviderError('offline_cache_miss','No cached response; network disabled')
        max_retries=getattr(self.config,'max_retries',2) if retries is None else retries
        for attempt in range(max_retries+1):
            self.budget.consume()
            try:
                r=self.client.get(url,params=params)
                if r.status_code in {429,500,502,503,504} and attempt<max_retries:
                    try:retry=float(r.headers.get('Retry-After','0'))
                    except ValueError:retry=0
                    time.sleep(min(max(retry,0.3*2**attempt),3));continue
                r.raise_for_status()
                if len(r.content)>10_000_000:raise ProviderError('response_too_large','Public response exceeded 10 MB')
                retrieved=now_iso(); body=r.text
                try:
                    candidate=json.loads(body)
                    cacheable=not (isinstance(candidate,dict) and str(candidate.get('code','0')) not in {'0',''})
                except ValueError:cacheable=True
                if cacheable:
                    temp_name=None
                    try:
                        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',prefix=key+'.',suffix='.tmp',dir=self.cache_dir,delete=False) as fh:
                            temp_name=fh.name
                            json.dump({'saved_at':time.time(),'retrieved_at':retrieved,'body':body},fh)
                        Path(temp_name).replace(path)
                    finally:
                        if temp_name:Path(temp_name).unlink(missing_ok=True)
                return body,{'source_url':url,'retrieved_at':retrieved,'cached':False,'freshness_seconds':0,'quality_flags':[]}
            except httpx.HTTPStatusError as exc:
                raise ProviderError('http_'+str(exc.response.status_code),'HTTP request failed at '+scheme.netloc) from exc
            except httpx.RequestError as exc:
                if attempt==max_retries:raise ProviderError('network_error',type(exc).__name__+' at '+scheme.netloc) from exc
                time.sleep(min(0.3*2**attempt,3))
        raise ProviderError('network_error','Request failed')
    def json(self,url:str,params:dict|None=None,ttl:int=30)->tuple[Any,dict]:
        retries=int(getattr(self.config,'max_retries',2))
        for attempt in range(retries+1):
            body,meta=self.get(url,params,ttl)
            try:obj=json.loads(body)
            except ValueError as exc:raise ProviderError('invalid_json','Provider response is not JSON') from exc
            code=str(obj.get('code','0')) if isinstance(obj,dict) else '0'
            if code in {'50011','50040'} and attempt<retries:
                time.sleep(min(0.3*2**attempt,3));continue
            if code not in {'0',''}:
                raise ProviderError(code,'OKX public API: '+str(obj.get('msg','error'))[:200],'okx_public_api')
            return obj,meta
        raise ProviderError('retry_exhausted','JSON request retries exhausted')
