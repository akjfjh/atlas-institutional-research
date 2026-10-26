#!/usr/bin/env python3
"""Render historical validation figures from the checked-in summary (optional matplotlib)."""
from __future__ import annotations
import json
from pathlib import Path

def main() -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    root=Path(__file__).resolve().parent.parent
    example=root/'docs'/'examples'
    data=json.loads((example/'validation-summary.json').read_text())
    backtest=data['backtest']
    values=[backtest['baseline_oos']['net_return']*100,backtest['technical_proxy_oos']['net_return']*100]
    fig,ax=plt.subplots(figsize=(8,5.2))
    fig.subplots_adjust(left=.13,right=.97,top=.88,bottom=.27)
    fig.patch.set_facecolor('#f5f7fb');ax.set_facecolor('#fff')
    bars=ax.bar(['Simple trend baseline','ATLAS technical proxy'],values,color=['#3d7ca6','#bc7d32'],width=.55)
    ax.axhline(0,color='#334155',linewidth=.8)
    ax.set_ylim(0,max(values)*1.22)
    for bar,value in zip(bars,values):ax.annotate(f'{value:+.2f}%',(bar.get_x()+bar.get_width()/2,bar.get_height()),xytext=(0,6),textcoords='offset points',ha='center')
    ax.set_ylabel('Out-of-sample simulated net return (%)')
    ax.set_title('ETH-USDT-SWAP | five-year-history backtest')
    ci=backtest['paired_mean_bar_return_difference_ci95']
    fig.text(.5,.035,f"Paired daily mean difference 95% CI: [{ci['low']*100:+.4f}%, {ci['high']*100:+.4f}%]",ha='center',fontsize=9)
    fig.text(.5,.065,'No credible improvement established',ha='center',fontsize=9)
    fig.savefig(example/'backtest-comparison.png',dpi=170)
    plt.close(fig)

    event=data['fomc'];horizons=sorted(event['horizons'],key=int)
    means=[event['horizons'][h]['mean_return']*100 for h in horizons]
    lower=[(event['horizons'][h]['mean_return']-event['horizons'][h]['ci95']['low'])*100 for h in horizons]
    upper=[(event['horizons'][h]['ci95']['high']-event['horizons'][h]['mean_return'])*100 for h in horizons]
    fig,ax=plt.subplots(figsize=(8,5.2))
    fig.subplots_adjust(left=.13,right=.97,top=.88,bottom=.30)
    fig.patch.set_facecolor('#f5f7fb');ax.set_facecolor('#fff')
    ax.errorbar([int(h) for h in horizons],means,yerr=[lower,upper],fmt='o-',capsize=5,color='#217e87',ecolor='#8899a8')
    ax.axhline(0,color='#334155',linewidth=.8,linestyle='--')
    ax.set_xticks([int(h) for h in horizons]);ax.set_xlabel('Days after first eligible UTC daily open')
    ax.set_ylabel('Mean historical BTC return (%)')
    ax.set_title(f"FOMC historical event windows | n={event['usable_events']}")
    fig.text(.5,.035,'95% bootstrap intervals; historical association, not a causal or trading estimate',ha='center',fontsize=9)
    fig.savefig(example/'fomc-event-study.png',dpi=170)
    plt.close(fig)

if __name__=='__main__':main()
