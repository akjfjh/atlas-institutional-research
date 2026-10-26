"""Closed-candle 15m/1H entry study. It never authorizes an order."""
from __future__ import annotations

import math
from datetime import datetime, timezone


def _positive(value):
    try:
        number=float(value)
        return number if math.isfinite(number) and number>0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def study(timeframes:dict, snapshot:dict, *, simulation:bool=False, fee_bps:float=10, slippage_bps:float=5)->dict:
    fast=timeframes.get('15m') or {}
    slow=timeframes.get('1H') or {}
    ticker=snapshot.get('ticker') or {}
    price=_positive(ticker.get('last'))
    try:
        age=(datetime.fromisoformat(snapshot['retrieved_at'].replace('Z','+00:00')).timestamp()-float(ticker['ts'])/1000)
    except (KeyError, ValueError, TypeError, OverflowError):
        age=None
    fresh=snapshot.get('mode')=='live' and age is not None and -60<=age<=120
    metrics=fast.get('metrics') or {}
    slow_metrics=slow.get('metrics') or {}
    rsi=metrics.get('rsi14')
    volume=metrics.get('volume_change20')
    adx=(slow_metrics.get('adx') or {}).get('adx')
    aligned=fast.get('trend')==slow.get('trend') and fast.get('trend') in {'bullish','bearish'}
    direction=fast.get('trend') if aligned else None
    indicators={'15m_trend':fast.get('trend'),'1h_trend':slow.get('trend'),
                '15m_rsi14':rsi,'15m_volume_vs_20_bar_mean':volume,
                '1h_adx14':adx,'15m_atr14':metrics.get('atr14')}
    reasons=[]
    if not fast or not slow:reasons.append('15m_or_1h_closed_candles_missing')
    if not aligned:reasons.append('timeframes_not_aligned')
    if rsi is None or volume is None or adx is None:reasons.append('indicator_warmup_incomplete')
    if not fresh:reasons.append('ticker_not_fresh_or_not_live')
    try:
        observed=datetime.fromisoformat(snapshot['retrieved_at'].replace('Z','+00:00')).timestamp()*1000
        for label,period,max_age in (('15m',fast,1_800_000),('1H',slow,7_200_000)):
            bar_age=observed-float(period['as_of'])
            if not 0<=bar_age<=max_age:reasons.append(label+'_closed_bar_stale')
    except (KeyError,TypeError,ValueError,OverflowError):reasons.append('closed_bar_time_unavailable')
    if direction=='bullish' and rsi is not None and not 50<=rsi<=70:reasons.append('15m_rsi_outside_long_window')
    if direction=='bearish' and rsi is not None and not 30<=rsi<=50:reasons.append('15m_rsi_outside_short_window')
    if volume is not None and volume<=0:reasons.append('15m_volume_not_above_20_bar_mean')
    if adx is not None and adx<20:reasons.append('1h_trend_strength_below_20')
    support=_positive(fast.get('support'))
    resistance=_positive(fast.get('resistance'))
    atr=_positive(metrics.get('atr14'))
    if not support or not resistance or support>=resistance or not atr:reasons.append('entry_levels_or_atr_missing')
    if support and resistance and atr and price:
        reference=resistance+atr*.1 if direction=='bullish' else support-atr*.1 if direction=='bearish' else None
        if reference and abs(price-reference)/reference>.005:reasons.append('price_not_near_entry_reference')
    result={'direction':'WAIT','signal':'not_confirmed','reasons':reasons,'indicators':indicators,
            'price_as_of':ticker.get('ts'),'bars_as_of':{'15m':fast.get('as_of'),'1H':slow.get('as_of')},
            'entry_reference':None,'invalidation':None,'illustrative_exit':None,'alert':False,
            'order_execution':'disabled','executable':False}
    if not reasons:
        long=direction=='bullish'
        entry=resistance+atr*.1 if long else support-atr*.1
        stop=support-atr*.1 if long else resistance+atr*.1
        risk=abs(entry-stop)
        if entry>0 and stop>0 and risk>0:
            result.update(direction='LONG_WATCH' if long else 'SHORT_WATCH',signal='closed_bar_setup',
                          entry_reference=entry,invalidation=stop,
                          illustrative_exit=entry+2*risk if long else max(0,entry-2*risk),
                          alert=True)
    if simulation:
        # Margin is hypothetical; account mode, tiers, mark price and funding are unknown.
        result['one_usdt_simulation']={
            'margin_usdt':1,'leverage_scenarios':[50,100],
            'notional_usdt':[50,100],
            'adverse_move_for_1_usdt_gross_loss_pct':[2,1],
            'round_trip_fee_slippage_usdt':[
                n*(2*fee_bps+2*slippage_bps)/10000 for n in (50,100)],
            'liquidation_price':None,'liquidation_unverified':True,
            'market_order_or_stop_fill_guaranteed':False,
            'execution_allowed':False,
            'basis':'illustrative isolated 1 USDT margin arithmetic; venue minimums, mark-price liquidation, maintenance margin and funding unverified'}
    return result
