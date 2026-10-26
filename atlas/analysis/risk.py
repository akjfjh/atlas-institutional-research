"""Reproducible, read-only spot risk assessment and conditional order sizing."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, InvalidOperation
import math


def _number(value):
    try:
        result=float(value)
        return result if math.isfinite(result) and result>0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _seconds(value):
    try:
        if isinstance(value,(int,float)):
            n=float(value)
            return n/1000 if n>1e11 else n
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def assess_risk(state, policy:dict)->dict:
    """Use only the frozen research snapshot and the recorded, nonsecret risk policy."""
    snap=state.snapshot
    instrument=state.instrument_id
    ticker=snap.get('ticker',{})
    technical=state.results.get('technical')
    day=(technical.payload.get('timeframes',{}).get('1D',{}) if technical else {})
    metrics=day.get('metrics',{})
    price=_number(ticker.get('last'))
    support=_number(day.get('support'))
    resistance=_number(day.get('resistance'))
    atr=_number(metrics.get('atr14'))
    close=_number(metrics.get('close'))
    volume_change=metrics.get('volume_change20')
    observation=_seconds(snap.get('retrieved_at'))
    quote_time=_seconds(ticker.get('ts'))
    age=observation-quote_time if observation is not None and quote_time is not None else None
    buffer=atr*.1 if atr is not None else (resistance-support)*.02 if support and resistance and resistance>support else None
    watch={'support':support,'resistance':resistance,'breakout_confirmation':'daily_close_above_resistance_and_volume_above_prior_20_day_average',
           'support_confirmation':'daily_close_back_above_support_after_test','bar_as_of':day.get('as_of'),
           'current_price':price,'ticker_as_of':ticker.get('ts'),'data_retrieved_at':snap.get('retrieved_at'),
           'distance_above_support_pct':(price/support-1)*100 if price and support else None,
           'distance_below_resistance_pct':(resistance/price-1)*100 if price and resistance else None,
           'nearest_level':'support' if price and support and resistance and abs(price-support)<=abs(resistance-price) else 'resistance' if price and support and resistance else None,
           'market_observation':'above_resistance' if price and resistance and price>resistance else 'below_support' if price and support and price<support else 'inside_range' if price and support and resistance else 'unavailable'}
    blockers=[]
    if snap.get('mode')!='live':blockers.append('non_live_data')
    if age is None or age< -60 or age>120:blockers.append('ticker_not_fresh')
    if not price:blockers.append('price_unavailable')
    if not support or not resistance or support>=resistance:blockers.append('levels_unavailable')
    if instrument not in policy.get('primary_instruments',[]):blockers.append('instrument_not_in_profile')
    if not instrument.endswith('-USDT') or instrument.endswith('-SWAP'):blockers.append('spot_usdt_only')
    capital=_number(policy.get('capital_usdt'))
    if capital is None:blockers.append('capital_unset')
    confirmed=_seconds(policy.get('positions_confirmed_at'))
    if policy.get('positions_status')!='none_reported' or confirmed is None or observation is None or observation-confirmed>86400 or observation-confirmed< -60:
        blockers.append('portfolio_exposure_unconfirmed')
    if not (close and resistance and close>resistance and isinstance(volume_change,(float,int)) and math.isfinite(volume_change) and volume_change>0):
        blockers.append('breakout_unconfirmed')
    if day.get('trend')!='bullish':blockers.append('daily_trend_not_bullish')
    if technical and technical.contradictions:blockers.append('timeframe_conflict')
    for role in ('fed','macro','news','technical','sentiment','backtest','btc_specialist','eth_specialist'):
        result=state.results.get(role)
        if not result or result.status!='complete':blockers.append('incomplete_'+role)
    comparison=state.results.get('backtest')
    comparison_data=comparison.payload.get('comparison',{}) if comparison else {}
    if not (comparison_data.get('statistically_credible_improvement') and comparison_data.get('full_committee_historical_replay') and comparison_data.get('multiple_testing_adjusted')):
        blockers.append('edge_unverified')
    entry=resistance+buffer if resistance and buffer else None
    stop=support-buffer if support and buffer else None
    if price and entry and price>entry*1.01:blockers.append('price_too_far_from_entry')
    risk_per_unit=entry-stop if entry and stop and entry>stop>0 else None
    estimate={'capital_usdt':capital,'risk_fraction':policy.get('risk_fraction'),
              'risk_budget_usdt':capital*float(policy.get('risk_fraction',.005)) if capital else None,
              'portfolio_risk_cap_usdt':capital*float(policy.get('max_portfolio_risk_fraction',.01)) if capital else None,
              'notional_cap_usdt':capital*float(policy.get('max_notional_fraction',.25)) if capital else None,
              'entry_reference':entry,'stop_reference':stop,'risk_per_base_unit_before_costs':risk_per_unit,
              'fees_bps_each_side':policy.get('fee_bps'),'slippage_bps_each_side':policy.get('slippage_bps'),
              'spot_only':True,'order_execution':'read_only_no_order'}
    return {'assessment_version':2,'instrument_id':instrument,'market_type':'SPOT' if instrument.endswith('-USDT') and not instrument.endswith('-SWAP') else 'OTHER',
            'watch':watch,'risk':estimate,'blockers':list(dict.fromkeys(blockers)),
            'preliminary_entry_eligible':not blockers,'source':'frozen_snapshot_and_recorded_profile'}


def final_decision(state)->dict:
    """Apply the final committee gate and current-at-publication freshness check."""
    role=state.results.get('risk_control')
    assessment=role.payload.get('assessment',{}) if role else {}
    watch=assessment.get('watch',{})
    if not watch:
        # Quick scans have no risk-control role, but their observed quote and
        # technical levels can still be shown as a dated, non-executable watch.
        ticker=state.snapshot.get('ticker',{})
        technical=state.results.get('technical')
        day=technical.payload.get('timeframes',{}).get('1D',{}) if technical else {}
        price=_number(ticker.get('last'))
        support=_number(day.get('support'))
        resistance=_number(day.get('resistance'))
        nearest=('support' if abs(price-support)<=abs(resistance-price) else 'resistance') if price and support and resistance else None
        watch={'current_price':price,'ticker_as_of':ticker.get('ts'),
               'support':support,'resistance':resistance,'nearest_level':nearest}
    reasons=list(assessment.get('blockers',[]))
    if state.phase!='APPROVED':reasons.append('committee_not_approved')
    if role is None:reasons.append('risk_officer_not_run')
    elif not assessment.get('preliminary_entry_eligible'):reasons.append('risk_officer_veto')
    final_time=_seconds(state.completed_at)
    quote_time=_seconds(watch.get('ticker_as_of'))
    if final_time is None or quote_time is None or final_time-quote_time>120 or final_time-quote_time< -60:
        reasons.append('ticker_stale_at_publication')
    if reasons:
        return {'can_open':False,'reasons':list(dict.fromkeys(reasons)),'watch':watch,
                'risk':assessment.get('risk',{}),'order_plan':None,'as_of':state.completed_at}
    risk=assessment['risk'];meta=state.snapshot.get('instrument',{})
    try:
        entry=Decimal(str(risk['entry_reference']));stop=Decimal(str(risk['stop_reference']))
        capital=Decimal(str(risk['capital_usdt']))
        budget=min(Decimal(str(risk['risk_budget_usdt'])),Decimal(str(risk['portfolio_risk_cap_usdt'])))
        cap=Decimal(str(risk['notional_cap_usdt']))
        lot=Decimal(str(meta['lotSz']));minimum=Decimal(str(meta['minSz']));tick=Decimal(str(meta['tickSz']))
        if min(entry,stop,capital,budget,cap,lot,minimum,tick)<=0 or entry<=stop:raise InvalidOperation
        # Charge both sides for fee/slippage and one full spread before sizing.
        cost_bps=2*Decimal(str(risk['fees_bps_each_side']))+2*Decimal(str(risk['slippage_bps_each_side']))+Decimal(str(state.budget.get('risk_policy',{}).get('spread_bps',0)))
        loss_per_unit=entry-stop+entry*cost_bps/Decimal('10000')
        quantity=min(budget/loss_per_unit,cap/entry)
        quantity=(quantity/lot).to_integral_value(rounding=ROUND_DOWN)*lot
        rounded_price=(entry/tick).to_integral_value(rounding=ROUND_DOWN)*tick
        if quantity<minimum or rounded_price<=0:raise InvalidOperation
        stages=[]
        for fraction in (Decimal('.5'),Decimal('.3')):
            part=(quantity*fraction/lot).to_integral_value(rounding=ROUND_DOWN)*lot
            stages.append(part)
        stages.append(quantity-sum(stages))
        if any(part<minimum for part in stages):stages=[quantity]
        plan={'side':'buy','order_type':'limit','allocation':'staged' if len(stages)==3 else 'single_small_order',
              'limit_price':str(rounded_price),'stop_reference':str(stop),'total_base_quantity':str(quantity),
              'stage_base_quantities':[str(x) for x in stages],
              'stage_conditions':['confirmed_daily_breakout','successful_retest','continuation_with_fresh_risk_check'] if len(stages)==3 else ['confirmed_daily_breakout'],
              'estimated_max_loss_usdt':str(quantity*loss_per_unit),'estimated_notional_usdt':str(quantity*entry),
              'exchange_rules_verified':True,'user_must_place_and_verify_orders':True}
        return {'can_open':True,'reasons':[],'watch':watch,'risk':risk,'order_plan':plan,'as_of':state.completed_at}
    except (KeyError,TypeError,ValueError,InvalidOperation,ZeroDivisionError):
        return {'can_open':False,'reasons':['exchange_order_rules_or_size_unavailable'],
                'watch':watch,'risk':risk,'order_plan':None,'as_of':state.completed_at}
