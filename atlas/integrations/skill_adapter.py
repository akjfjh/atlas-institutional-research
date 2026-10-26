"""Read-only adapter for verified official OKX CLI capabilities.

Skills are instructions, not callable services. Discovery records upstream skills;
invocation goes through the official CLI with a closed command/parameter list.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

READ_COMMANDS = {
    'ticker': ('market', 'ticker'), 'candles': ('market', 'candles'),
    'instruments': ('market', 'instruments'), 'orderbook': ('market', 'orderbook'),
    'funding_rate': ('market', 'funding-rate'), 'open_interest': ('market', 'open-interest'),
    'mark_price': ('market', 'mark-price'), 'index_ticker': ('market', 'index-ticker'),
    'news_latest': ('news', 'latest'), 'coin_sentiment': ('news', 'coin-sentiment'),
    'smartmoney_signal': ('smartmoney','signal-overview-by-filter'),
}
POSITIONAL = {'ticker', 'candles', 'orderbook', 'funding_rate'}
PARAMS = {
    'ticker': {'instId'}, 'candles': {'instId', 'bar', 'limit', 'after', 'before'},
    'instruments': {'instType', 'instId'}, 'orderbook': {'instId', 'sz'},
    'funding_rate': {'instId', 'history', 'limit'},
    'open_interest': {'instType', 'instId'}, 'mark_price': {'instType', 'instId'},
    'index_ticker': {'instId'}, 'news_latest': {'coins', 'limit', 'lang'},
    'coin_sentiment': {'coins'}, 'smartmoney_signal': {'instCcyList','period','lmtNum'},
}
BASELINE = ['okx-cex-auth','okx-cex-market','okx-cex-trade','okx-cex-portfolio',
            'okx-cex-bot','okx-cex-earn','okx-cex-smartmoney','okx-sentiment-tracker','okx-cex-skill-mp']
MIXED = {'okx-cex-auth','okx-cex-trade','okx-cex-portfolio','okx-cex-bot','okx-cex-earn','okx-cex-skill-mp'}
TOKEN_PATTERN = re.compile(r'(?i)((?:bearer\s+)[A-Za-z0-9_.-]+|(?:(?:api[_-]?key|secret[_-]?key|passphrase|access[_-]?token)\s*[=:]\s*)[^\s,}]+)')


def safe_error(text: Any) -> str:
    return TOKEN_PATTERN.sub('[REDACTED]', str(text))[:500]


def executable_env() -> dict[str, str]:
    env = dict(os.environ)
    paths = [Path.home()/'.local/npm/bin', Path.home()/'.local/bin']
    paths.extend(sorted((Path.home()/'.local/lib/nodejs').glob('*/bin'), reverse=True))
    env['PATH'] = os.pathsep.join(str(p) for p in paths if p.exists()) + os.pathsep + env.get('PATH','')
    return env


def resolve_cli(configured: str = 'okx') -> str | None:
    return shutil.which(configured, path=executable_env()['PATH'])


def validate_instrument(value: str) -> str:
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9]{1,20}(?:-[A-Z0-9_]{1,30}){1,4}',value):
        raise ValueError('Invalid instrument ID; expected uppercase OKX ID, e.g. ETH-USDT-SWAP')
    return value


class OfficialSkillAdapter:
    def __init__(self, config: Any):
        self.config = config
        self.cli = resolve_cli(getattr(config,'okx_cli','okx'))
        self.timeout = float(getattr(config,'timeout_seconds',15))

    def classify(self, capability: str) -> str:
        return 'READ' if capability in READ_COMMANDS else 'WRITE_OR_UNKNOWN'

    def invoke(self, capability: str, **params: Any) -> dict[str, Any]:
        if capability not in READ_COMMANDS:
            raise PermissionError('ATLAS refuses WRITE and unknown capabilities')
        unknown = set(params)-PARAMS[capability]
        if unknown:
            raise ValueError(f'Unknown parameters: {sorted(unknown)}')
        for key,value in params.items():
            if key=='instId': validate_instrument(value)
            elif key=='bar' and value not in {'1m','5m','15m','1H','4H','1D','1W','1M'}:
                raise ValueError('Unsupported candle interval')
            elif key in {'limit','sz','lmtNum'} and (isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=300):
                raise ValueError(f'{key} must be integer 1..300')
            elif key in {'after','before'} and not str(value).isdigit():
                raise ValueError('Timestamp must be integer milliseconds')
            elif key=='instType' and value not in {'SPOT','SWAP','FUTURES','OPTION','MARGIN'}:
                raise ValueError('Unsupported instrument type')
            elif key=='period' and str(value) not in {'3','7','30','90'}:raise ValueError('Unsupported period')
            elif key in {'coins','instCcyList'} and not re.fullmatch(r'[A-Z0-9]{1,20}(?:,[A-Z0-9]{1,20})*',str(value)):
                raise ValueError('Invalid coins')
            elif key=='lang' and value not in {'zh-CN','en-US'}: raise ValueError('Unsupported language')
            elif key=='history' and not isinstance(value,bool): raise ValueError('history must be boolean')
        if not self.cli:
            return {'ok':False,'error':{'provider':'okx_cli','code':'missing_dependency','message':'okx CLI not installed'}}
        args = [self.cli,'--json',*READ_COMMANDS[capability]]
        if capability in POSITIONAL:
            if not params.get('instId'): raise ValueError('instId is required')
            args.append(params['instId'])
        for key,value in params.items():
            if key=='instId' and capability in POSITIONAL: continue
            if value is None or value is False: continue
            args.append('--'+key)
            if value is not True: args.append(str(value))
        try:
            result = subprocess.run(args,capture_output=True,text=True,timeout=self.timeout,
                                    env=executable_env(),shell=False)
            # CLI can return rc=0 on API errors. Never treat unparseable text as data.
            data=json.loads(result.stdout)
            if isinstance(data,dict) and str(data.get('code','0')) not in {'0',''}:
                return {'ok':False,'error':{'provider':'okx_cli','code':str(data.get('code')),'message':safe_error(data.get('msg','API error'))}}
            if result.returncode:
                return {'ok':False,'error':{'provider':'okx_cli','code':'cli_error','message':safe_error(result.stderr)}}
            return {'ok':True,'data':data.get('data',data) if isinstance(data,dict) else data,'source':'okx_cli'}
        except subprocess.TimeoutExpired:
            return {'ok':False,'error':{'provider':'okx_cli','code':'timeout','message':'Read command timed out'}}
        except (ValueError,OSError) as exc:
            # stderr may include credentials supplied by the user's CLI. Retain only sanitized text.
            return {'ok':False,'error':{'provider':'okx_cli','code':'invalid_response','message':safe_error(locals().get('result').stderr if 'result' in locals() else exc)}}

    def status(self) -> dict[str,Any]:
        info={'cli_available':bool(self.cli),'cli_version':None,'auth_status':'unknown','scopes':[],'write_enabled':False}
        if self.cli:
            try:
                p=subprocess.run([self.cli,'--version'],capture_output=True,text=True,timeout=5,env=executable_env())
                info['cli_version']=p.stdout.splitlines()[0][:120] if p.stdout else None
            except (OSError,subprocess.TimeoutExpired): pass
        auth=Path.home()/'.okx/bin'/('okx-auth.exe' if os.name=='nt' else 'okx-auth')
        if auth.is_file():
            try:
                p=subprocess.run([str(auth),'status','--json'],capture_output=True,text=True,timeout=5)
                obj=json.loads(p.stdout)
                # Deliberately omit userCode, verification URI, account and token fields.
                info['auth_status']=obj.get('status','unknown')
                info['scopes']=obj.get('scopes',[])
            except (OSError,ValueError,subprocess.TimeoutExpired): pass
        return info

    def discover(self, refresh: bool=False) -> dict[str,Any]:
        from datetime import datetime,timezone
        manifest_path=Path(__file__).resolve().parents[2]/'references/capability-manifest.json'
        if not manifest_path.exists():manifest_path=Path(__file__).resolve().parents[1]/'providers/capability_manifest.json'
        baseline={}
        if manifest_path.exists():
            try: baseline=json.loads(manifest_path.read_text())
            except ValueError: pass
        names=[x['name'] for x in baseline.get('skills',[])] or BASELINE
        upstream=baseline.get('skills',[])
        error=None
        if refresh:
            try:
                import httpx
                with httpx.Client(timeout=10,follow_redirects=True) as client:
                    response=client.get('https://api.github.com/repos/okx/agent-skills/contents/skills',params={'ref':'github-main'})
                    response.raise_for_status()
                    names=sorted(x['name'] for x in response.json() if x.get('type')=='dir' and re.fullmatch(r'okx-[a-z0-9-]+',x.get('name','')))
                    upstream=[]
                    for name in names:
                        raw=client.get(f'https://raw.githubusercontent.com/okx/agent-skills/github-main/skills/{name}/SKILL.md')
                        raw.raise_for_status()
                        match=re.search(r'^\s+version:\s*[\"\']?([^\s\"\']+)',raw.text,re.M)
                        upstream.append({'name':name,'version':match.group(1) if match else 'unknown','url':f'https://github.com/okx/agent-skills/tree/github-main/skills/{name}',
                                         'permission':'READ_WRITE_MIXED' if name in MIXED else 'READ'})
            except Exception as exc: error=safe_error(exc)
        local=[]
        for base in [Path.home()/'.codex/skills',Path.home()/'.agents/skills']:
            for name in names:
                file=base/name/'SKILL.md'
                if file.exists():
                    text=file.read_text(errors='replace')
                    match=re.search(r'^\s+version:\s*[\"\']?([^\s\"\']+)',text,re.M)
                    local.append({'name':name,'version':match.group(1) if match else 'unspecified','path':str(file)})
        return {'verified_at':datetime.now(timezone.utc).isoformat(),'official_skills':upstream,'local_skills':local,
                'added':sorted(set(names)-set(BASELINE)),'removed':sorted(set(BASELINE)-set(names)),
                'refresh_error':error,'status':self.status(),'read_capabilities':sorted(READ_COMMANDS),'write_enabled':False}
