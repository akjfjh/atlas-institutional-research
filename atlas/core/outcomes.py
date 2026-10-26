from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from atlas.core.state import now
from atlas.core.reviewer import parse_time

def observe_outcome(state,config,repo,horizon_days=7):
    if not 1<=horizon_days<=365:raise ValueError('horizon_days must be 1..365')
    reference=state.completed_at or state.created_at;target=parse_time(reference)+horizon_days*86400
    if datetime.now(timezone.utc).timestamp()<target:
        return {'research_id':state.research_id,'status':'pending','horizon_days':horizon_days,'eligible_after':datetime.fromtimestamp(target,timezone.utc).isoformat(),'real_trading_win_rate':None}
    if state.snapshot.get('mode')!='live':raise ValueError('offline/cache fixtures cannot enter live prediction outcome records')
    from atlas.providers import DataService
    service=DataService(config)
    try:history=service.history(state.instrument_id,'1D',years=min(10,max(1,(datetime.now(timezone.utc).year-datetime.fromtimestamp(parse_time(reference),timezone.utc).year)+1)))
    finally:service.close()
    bars=history['data'];t0=parse_time(reference)*1000
    before=[c for c in bars if c['ts']>=t0]
    entry=before[0] if before else None
    after=[c for c in bars if entry and c['ts']>=entry['ts']+horizon_days*86400000]
    if not before or not after:return {'research_id':state.research_id,'status':'insufficient_data','limitations':history['limitations']}
    entry=before[0];exit=after[0];ret=exit['open']/entry['open']-1
    hit=(ret>0 if state.decision=='BULLISH' else ret<0) if state.decision in {'BULLISH','BEARISH'} else None
    result={'research_id':state.research_id,'status':'observed','horizon_days':horizon_days,'reference_price':entry['open'],'reference_available_at':entry['ts'],'outcome_price':exit['open'],'outcome_available_at':exit['ts'],'return':ret,'decision':state.decision,'directional_hit':hit,'sample_kind':'research_forecast_observation_not_trade','observed_at':now(),'real_trading_win_rate':None,'limitations':['first daily open AFTER report time, then first daily open at horizon; not actual fills or portfolio PnL']}
    with repo.connect() as db:db.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?)',(state.research_id,horizon_days,result['observed_at'],json.dumps(result)))
    return result
