# Actors and host-agent protocol

ATLAS separates computation and collaboration from model narration. Every run records the execution engine. A deterministic actor is an executable role with validated structured inputs and outputs; it does not claim a separate human or independent model ran.

| Role | Responsibility | Required exchanges |
|---|---|---|
| Coordinator | Scope, dependency scheduling, budgets, conflict arbitration and final state | All actors; may request bounded revisions |
| Macro | Inflation, labor, growth, rates, liquidity proxies and limitations | Fed, news, technical, strategy |
| Fed | Official policy documents, policy environment and conditional transmission | Macro, news, technical, backtest, strategy |
| News | Dated, sourced events; duplicates; verification and freshness | Fed, sentiment, strategy |
| Technical | Closed-bar numerical indicators on 1D/1W/1M UTC | Sentiment, history, strategy |
| Sentiment | Funding/OI/positioning and available authenticated sentiment | Technical, news, strategy |
| Historical/backtest | Point-in-time studies, OOS metrics, costs and contrary cases | Fed, technical, strategy |
| BTC specialist / BTC 专项 | Verified BTC daily structure, volatility, drawdown and relative return versus ETH | Technical, macro, news, ETH specialist, strategy |
| ETH specialist / ETH 专项 | Verified ETH daily structure, volatility, drawdown and relative return versus BTC; no inferred on-chain metrics | Technical, macro, news, BTC specialist, strategy |
| Risk control / 风险控制 | Independently calculate entry veto, current quote freshness, support/resistance, capital budget, exposure and exchange-order constraints | Reports to strategy and chief review; recomputed by final audit |
| Strategy | Independently conditioned long, short and wait scenarios | Every upstream role |
| Chief review | Retain all specialist and committee conflicts and apply final research judgment | All upstream roles |
| Data Integrity Validator | Instrument, timestamps, sources, gaps, values and freshness | Blocks invalid inputs and final approval |
| Risk & Research Audit | Unsupported claims, uncertainty, costs, contradictions and review completeness | Blocks unsupported final approval |

## Host-managed independent agents

Start a host run and inspect `atlas task-list ID`. Each task contains its role and dependencies. Assign these tasks to actual host subagents when the client supports them. Supply only the research state, selected role guidance and raw evidence necessary for that task. Do not supply an expected conclusion. Researchers must read confirmed upstream outputs before forming a final downstream view.

A result needs the fields listed in `schemas/` and the engine's returned schema: research ID, role ID, asset/instrument, task, timeframes, source and data timestamps, evidence, findings, regime, bullish and bearish arguments, uncertainty, contradictions, confidence, requests to other agents, status and version. Use `atlas submit ID --file result.json`; schema failures are errors, not accepted free text. Engine-generated IDs and asset identity must match the existing run.

The specialist roles are `btc_specialist` and `eth_specialist`. Preserve `payload.quant` exactly as the host-provided deterministic draft calculates it: the final auditor recomputes every specialist number from immutable BTC/ETH daily snapshots. State whether data is spot or swap and retain source/availability timestamps. The `risk_control` role follows the specialists and precedes trading/chief. Preserve its `payload.assessment` exactly as derived from the frozen snapshot and recorded profile; the auditor recomputes it and can veto unsupported changes. For bilingual delivery, write Chinese primary findings plus faithful English `claim_en` on each finding, `summary_en`, `uncertainties_en`, and `contradictions_en`; do not translate source facts by inference or invent unavailable metrics. The engine writes both language reports even when the main requested language is one of them. Read [risk and reassessment](risk-and-reassessment.md) before interpreting an entry plan.

A useful challenge identifies an evidence ID, the contested finding, its opposing evidence and the smallest additional research request that could resolve it. Revisions preserve earlier versions and reasons. A changed fixed dependency invalidates its dependents; a cross-role message requires the exact sender version that issued it, and a later sender revision without a new request does not create a permanent feedback loop. Unresolved major conflicts survive into the final report. Future data needs belong in uncertainties or a future research plan; a current `requests_to_other_agents` entry triggers a bounded current-round review.

The engine controls round, time, model-call and data-request budgets. Reaching a limit produces partial/rejected status with a reason. Do not keep revising until a trade recommendation appears.

The optional LLM provider uses structured JSON and bounded calls. Do not claim independent host-agent execution unless logs identify those agents. Host/model opinions remain subject to the same data and risk gates as deterministic analysis.
