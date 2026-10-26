from __future__ import annotations
import math,re
from typing import Any
SECRET_KEYS=re.compile(r'(api.?key|secret|passphrase|password|authorization|access.?token|refresh.?token|usercode)',re.I)
TOKEN_PATTERNS=[re.compile(r'Bearer\s+[A-Za-z0-9_.\-]+',re.I), re.compile(r'\bsk-[A-Za-z0-9_-]{12,}'), re.compile(r'(?i)(api[_-]?key|secret[_-]?key|passphrase|access[_-]?token)\s*[:=]\s*[^\s,;]+')]
def redact(value:Any)->Any:
    if isinstance(value,dict): return {str(k):('[REDACTED]' if SECRET_KEYS.search(str(k)) else redact(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [redact(x) for x in value]
    if isinstance(value,str):
        for pat in TOKEN_PATTERNS: value=pat.sub('[REDACTED]',value)
        return value
    if isinstance(value,float) and not math.isfinite(value): return None
    return value

def untrusted_text(value:Any,limit:int=24000)->str:
    import json
    # Data envelope only; never execute news/HTML/provider text or expose it as tool instructions.
    text=json.dumps(redact(value),ensure_ascii=False,allow_nan=False,default=str)
    return '<untrusted_research_data>\n'+text[:limit]+'\n</untrusted_research_data>'
