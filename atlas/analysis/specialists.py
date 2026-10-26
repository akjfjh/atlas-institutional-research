"""Causal, descriptive BTC/ETH specialist measures from confirmed UTC daily bars."""
from __future__ import annotations
import math
from statistics import stdev

DAY_MS=86_400_000

def summarize_specialist(asset:str,markets:dict)->dict:
    if asset not in {'BTC','ETH'}:raise ValueError('specialist asset must be BTC or ETH')
    peer='ETH' if asset=='BTC' else 'BTC'
    own=markets.get(asset,{})
    benchmark=markets.get(peer,{})
    if own.get('status')!='available' or benchmark.get('status')!='available':
        return {'status':'unavailable','asset':asset,'peer':peer,'reason':'Both verified BTC and ETH daily markets are required'}
    if own.get('market_type')!=benchmark.get('market_type'):
        return {'status':'unavailable','asset':asset,'peer':peer,'reason':'BTC and ETH market types differ'}
    if own.get('instrument_id','').split('-')[1:2]!=benchmark.get('instrument_id','').split('-')[1:2]:
        return {'status':'unavailable','asset':asset,'peer':peer,'reason':'BTC and ETH quote currencies differ'}
    def indexed(entry):
        out={};available={}
        for bar in entry.get('candles_1d',[]):
            if not bar.get('confirm') or int(bar['available_at'])<int(bar['ts'])+DAY_MS:
                raise ValueError('specialist bar is not a confirmed available UTC daily close')
            close=float(bar['close'])
            if not math.isfinite(close) or close<=0:raise ValueError('invalid specialist close')
            ts=int(bar['ts']);out[ts]=close;available[ts]=int(bar['available_at'])
        return out,available
    own_rows,own_available=indexed(own);peer_rows,peer_available=indexed(benchmark)
    common=sorted(set(own_rows)&set(peer_rows))
    if len(common)<31:
        return {'status':'unavailable','asset':asset,'peer':peer,'reason':'Fewer than 31 aligned confirmed daily closes','aligned_bars':len(common)}
    dates=common[-31:]
    if any(b-a!=DAY_MS for a,b in zip(dates,dates[1:])):
        return {'status':'unavailable','asset':asset,'peer':peer,'reason':'Aligned 30-day window has missing UTC days','aligned_bars':len(common)}
    closes=[own_rows[t] for t in dates];peer_closes=[peer_rows[t] for t in dates]
    own_return=closes[-1]/closes[0]-1
    peer_return=peer_closes[-1]/peer_closes[0]-1
    ratio_start=closes[0]/peer_closes[0];ratio_end=closes[-1]/peer_closes[-1]
    changes=[math.log(b/a) for a,b in zip(closes,closes[1:])]
    peak=closes[0];max_drawdown=0.0
    for close in closes:
        peak=max(peak,close)
        max_drawdown=max(max_drawdown,1-close/peak)
    return {'status':'available','asset':asset,'peer':peer,'instrument_id':own['instrument_id'],
            'peer_instrument_id':benchmark['instrument_id'],'market_type':own['market_type'],
            'aligned_bars':len(common),'window_bars':31,'window_start':dates[0],
            'window_end':dates[-1],'latest_available_at':max(own_available[dates[-1]],peer_available[dates[-1]]),
            'own_return_30d':own_return,'peer_return_30d':peer_return,
            'relative_return_spread_30d':own_return-peer_return,'relative_price_ratio_change_30d':ratio_end/ratio_start-1,
            'realized_volatility_30d_annualized':stdev(changes)*math.sqrt(365),
            'max_drawdown_30d':max_drawdown,
            'method':'31 aligned confirmed UTC daily closes; 30 log returns; descriptive, not a prediction',
            'forecast_probability':None}
