from __future__ import annotations
import json, os, sys
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

def default_data_dir() -> Path:
    if sys.platform == 'darwin': return Path.home() / 'Library/Application Support/ATLAS'
    if os.name == 'nt': return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'ATLAS'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'atlas'

class Config(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra='forbid')
    data_dir: Path = Field(default_factory=default_data_dir)
    language: str = 'zh'
    trader_level: str | None = None
    capital_usdt: float | None = Field(default=None, gt=0)
    primary_instruments: list[str] = Field(default_factory=list)
    positions_status: str = 'unknown'
    positions_confirmed_at: str | None = None
    max_notional_fraction: float = Field(default=.25, gt=0, le=1)
    max_portfolio_risk_fraction: float = Field(default=.01, gt=0, le=.05)
    okx_cli: str = 'okx'
    api_base_url: str = 'https://openapi.okx.com'
    timeout_seconds: float = Field(default=12, gt=0, le=120)
    macro_timeout_seconds: float = Field(default=8, gt=0, le=60)
    max_data_requests: int = Field(default=90, ge=1, le=10000)
    max_retries: int = Field(default=2, ge=0, le=5)
    min_request_interval: float = Field(default=0.15, ge=0.1)
    cache_ttl_seconds: int = Field(default=120, ge=0)
    offline: bool = False
    fixture: Path | None = None
    fetch_supplemental: bool = True
    trust_env: bool = True
    mcp_command: list[str] | None = None
    candle_limit: int = Field(default=300, ge=60, le=5000)
    max_rounds: int = Field(default=2, ge=0, le=5)
    research_timeout_seconds: float = Field(default=240, gt=0, le=3600)
    max_llm_calls: int = Field(default=11, ge=0, le=32)
    max_cost_usd: float = Field(default=1, ge=0)
    llm_input_usd_per_million: float | None = Field(default=None, ge=0)
    llm_output_usd_per_million: float | None = Field(default=None, ge=0)
    llm_model: str | None = None
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_max_output_tokens: int = Field(default=2200, ge=128, le=8192)
    weights: dict[str,float] = Field(default_factory=lambda: {'macro':.20,'fed':.15,'news':.10,'technical':.20,'sentiment':.10,'backtest':.25})
    fee_bps: float = Field(default=10, ge=0, le=1000)
    slippage_bps: float = Field(default=5, ge=0, le=1000)
    spread_bps: float = Field(default=2, ge=0, le=1000)
    risk_fraction: float = Field(default=.005, gt=0, le=.05)
    @field_validator('language')
    @classmethod
    def valid_language(cls,v):
        if v not in {'zh','en'}:raise ValueError('language must be zh or en')
        return v
    @field_validator('trader_level')
    @classmethod
    def valid_trader_level(cls,v):
        if v not in {None,'novice','experienced'}:raise ValueError('trader_level must be novice or experienced')
        return v
    @field_validator('primary_instruments')
    @classmethod
    def valid_primary_instruments(cls,v):
        from atlas.integrations.skill_adapter import validate_instrument
        if len(v)>20 or len(v)!=len(set(v)):raise ValueError('primary instruments must be unique and at most 20')
        for instrument in v:validate_instrument(instrument)
        return v
    @field_validator('positions_status')
    @classmethod
    def valid_positions_status(cls,v):
        if v not in {'unknown','none_reported','positions_reported'}:raise ValueError('invalid positions status')
        return v
    @field_validator('api_base_url')
    @classmethod
    def official_base(cls,v):
        from urllib.parse import urlparse
        p=urlparse(v)
        if p.scheme != 'https' or p.hostname not in {'openapi.okx.com','www.okx.com','us.okx.com','eea.okx.com','tr.okx.com'} or p.path not in {'','/'}:
            raise ValueError('OKX base must be an official HTTPS origin (no path, credentials, or query)')
        if p.username or p.password or p.query or p.fragment: raise ValueError('invalid origin')
        return v.rstrip('/')
    @field_validator('llm_base_url')
    @classmethod
    def llm_origin(cls,v):
        from urllib.parse import urlparse
        p=urlparse(v)
        if p.username or p.password or p.query or p.fragment:raise ValueError('credentials/query in model endpoint URL forbidden')
        if p.scheme!='https' and not(p.scheme=='http' and p.hostname in {'localhost','127.0.0.1','::1'}):raise ValueError('model endpoint requires HTTPS or local HTTP')
        return v.rstrip('/')
    @field_validator('mcp_command')
    @classmethod
    def no_command_secrets(cls,v):
        if v:
            import re
            if any(re.search(r'(?i)(?:--?(?:api.?key|secret|passphrase|password|token)|Bearer\s)',part) for part in v):raise ValueError('do not put credentials in command arguments; use official broker/environment')
        return v
    @field_validator('weights')
    @classmethod
    def valid_weights(cls,v):
        if set(v) != {'macro','fed','news','technical','sentiment','backtest'} or any(x<0 for x in v.values()) or abs(sum(v.values())-1)>1e-8:
            raise ValueError('six nonnegative research weights must sum to one')
        return v

def load_config(data_dir=None, **overrides) -> Config:
    root=Path(data_dir).expanduser() if data_dir else Path(os.environ.get('ATLAS_DATA_DIR', default_data_dir())).expanduser()
    path=root/'config.json'
    raw=json.loads(path.read_text()) if path.exists() else {}
    # Credentials are deliberately never loaded from an ATLAS config file.
    for k in raw:
        if any(s in k.lower() for s in ('secret','api_key','password','token')) and k != 'llm_max_output_tokens':
            raise ValueError('credentials do not belong in ATLAS config; use official broker or environment')
    raw.update({k:v for k,v in overrides.items() if v is not None}); raw['data_dir']=root
    return Config(**raw)
