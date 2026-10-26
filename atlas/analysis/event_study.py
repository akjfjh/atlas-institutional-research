"""Point-in-time event windows and transparent historical similarity.

Returns describe market association after public availability, not causal impact.
Daily bars cannot measure minute-level surprise response; execution anchors to
first known opening at/after public availability, with resolution reported.
"""
from __future__ import annotations
import math
import statistics
from bisect import bisect_left
from datetime import datetime, timezone
from .indicators import validate_candles
from .backtesting import block_bootstrap_ci


def timestamp_ms(value):
    if value is None: raise ValueError("Missing event timestamp")
    if isinstance(value,(int,float)) or str(value).isdigit():
        n=float(value)
        if not math.isfinite(n) or n<0: raise ValueError("Invalid event timestamp")
        return int(n if n>100_000_000_000 else n*1000)
    text=str(value).strip()
    if len(text)==10: raise ValueError("Event date without release time is insufficient for point-in-time study")
    try: dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("Invalid ISO event timestamp") from exc
    if dt.tzinfo is None: raise ValueError("Event timestamp must include timezone")
    return int(dt.timestamp()*1000)


def validate_event(event):
    if not isinstance(event,dict): raise ValueError("Event must be an object")
    occurred=timestamp_ms(event.get("event_time",event.get("event_occurred_at")))
    publication=timestamp_ms(event.get("publication_time",event.get("published_at",event.get("event_time",event.get("event_occurred_at")))))
    available=timestamp_ms(event.get("first_available_time",event.get("first_available_at",publication)))
    if available<publication: raise ValueError("Lookahead: first availability predates publication")
    # A future scheduled event must not be treated as realized evidence.
    actual=event.get("actual_value")
    expected=event.get("expected_value")
    surprise=None
    if actual is not None and expected is not None:
        try:
            actual=float(actual); expected=float(expected)
            if not math.isfinite(actual) or not math.isfinite(expected): raise ValueError("Nonfinite event values")
            surprise=actual-expected
        except (TypeError,ValueError) as exc: raise ValueError("Invalid actual/expected values") from exc
    vintage=event.get("vintage_time",event.get("revision_time"))
    if vintage is not None and timestamp_ms(vintage)>available:
        raise ValueError("Data leakage: revised macro vintage used before it was available")
    return {**event,"event_id":str(event.get("event_id",f"event-{occurred}")),"event_time":occurred,"publication_time":publication,"first_available_time":available,"surprise":surprise,"effective_time":max(occurred,available)}


def study_events(candles, events, horizons=(1,3,7,14,30)):
    c=validate_candles(candles,min_count=2)
    if any(not isinstance(h,(int,float)) or h<=0 for h in horizons): raise ValueError("Horizons must be positive days")
    times=[b["ts"] for b in c]
    step=statistics.median([times[i]-times[i-1] for i in range(1,len(times))])
    results=[]; rejected=[]
    for raw in events:
        try: event=validate_event(raw)
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({"event_id":str(raw.get("event_id","unknown")) if isinstance(raw,dict) else "unknown","error":str(exc)})
            continue
        start=bisect_left(times,event["effective_time"])
        if start>=len(c):
            rejected.append({"event_id":event["event_id"],"error":"No tradable bar after event public availability"}); continue
        entry=c[start]["open"]; window={}
        # Do not anchor an event before the dataset starts: this would silently
        # substitute unrelated price history for the actual release response.
        if event["effective_time"]<times[0]:
            rejected.append({"event_id":event["event_id"],"error":"Event predates available price history"}); continue
        for horizon in horizons:
            end=bisect_left(times,times[start]+int(horizon*86_400_000))
            if end>=len(c):
                window[str(horizon)]={"status":"insufficient_future_history"}; continue
            bars=c[start:end]
            endpoint=c[end]["open"]
            high=max(b["high"] for b in bars); low=min(b["low"] for b in bars)
            before=c[max(0,start-(end-start)):start]
            volume_after=statistics.mean(b["volume"] for b in bars)
            volume_before=statistics.mean(b["volume"] for b in before) if before else None
            def vol(series):
                logs=[math.log(series[i]["close"]/series[i-1]["close"]) for i in range(1,len(series))]
                return statistics.stdev(logs) if len(logs)>=2 else None
            va,vb=vol(bars),vol(before)
            change=endpoint/entry-1
            window[str(horizon)]={"status":"complete","return":change,"max_upside":high/entry-1,"max_downside":low/entry-1,"maximum_favorable_excursion_long":high/entry-1,"maximum_adverse_excursion_long":low/entry-1,"volume_change":volume_after/volume_before-1 if volume_before else None,"volatility_before":vb,"volatility_after":va,"volatility_change":va/vb-1 if va is not None and vb else None,"end_time":times[end],"end_price":endpoint,"direction":"up" if change>0 else "down" if change<0 else "flat"}
        results.append({"event":event,"entry_time":times[start],"entry_price":entry,"anchor_delay_ms":times[start]-event["effective_time"],"windows":window})
    summary={}
    for horizon in horizons:
        values=[r["windows"][str(horizon)]["return"] for r in results if r["windows"][str(horizon)]["status"]=="complete"]
        summary[str(horizon)]={"sample_count":len(values),"mean_return":statistics.mean(values) if values else None,"median_return":statistics.median(values) if values else None,"positive_fraction":sum(v>0 for v in values)/len(values) if values else None,"mean_return_ci":block_bootstrap_ci(values),"statistically_reliable":len(values)>=30}
    warnings=["Descriptive association only; overlapping event windows are dependent and do not identify causal impact.","Positive fraction is a historical event-window statistic, not real trading win rate."]
    if step>=86_400_000: warnings.append("Daily or coarser bars: intraday release reactions are not resolved; next bar opening is used after public availability")
    if not results: warnings.append("No usable, timestamp-verified events")
    if any(x["sample_count"]<30 for x in summary.values()): warnings.append("Small event sample; event-window statistics are not robust")
    return {"events":results,"rejected_events":rejected,"summary":summary,"horizons_days":list(horizons),"candle_resolution_ms":step,"sample_kind":"historical_event_study","causal_estimate":False,"warnings":warnings}


def similar_events(query, events, *, limit=10):
    """Rank all eligible historical cases using disclosed, untrained distances.

    Only events available before query time qualify; missing dimensions reduce
    coverage rather than being imputed. Positive/negative outcomes are retained.
    """
    q=validate_event(query)
    numeric_scales={"surprise":1.0,"policy_rate":5.0,"inflation":5.0,"volatility":1.0,"funding_rate":0.001,"liquidity_change":1.0}
    categories=("event_type","market_regime","trend")
    ranked=[]
    for raw in events:
        try: e=validate_event(raw)
        except (ValueError,TypeError,KeyError): continue
        if e["first_available_time"]>=q["first_available_time"]: continue
        differences=[]; available=[]
        for k in categories:
            if q.get(k) is not None and e.get(k) is not None:
                differences.append(0 if q[k]==e[k] else 1); available.append(k)
        for k,scale in numeric_scales.items():
            if q.get(k) is not None and e.get(k) is not None:
                try: distance=min(2.0,abs(float(q[k])-float(e[k]))/scale)
                except (ValueError,TypeError): continue
                differences.append(distance); available.append(k)
        if not differences: continue
        ranked.append({"event":e,"distance":statistics.mean(differences),"matched_dimensions":available,"coverage":len(available)/(len(categories)+len(numeric_scales))})
    ranked.sort(key=lambda x:(x["distance"],-x["coverage"],x["event"]["event_id"]))
    return {"cases":ranked[:limit],"eligible_cases":len(ranked),"method":"untrained_equal_dimension_distance","selection_uses_outcome":False,"warning":"Exploratory analogues; missing dimensions and regime changes may dominate similarities"}
