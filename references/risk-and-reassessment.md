# Risk-control and key-level reassessment contract

ATLAS is read-only. A report may describe a conditional order plan, but it never sends an order or claims a stop will fill at the trigger price. The user places and verifies any order separately.

## First use

The installed Skill checks its runtime and calls `atlas doctor`. When `profile_complete=false`, ask for language, USDT trading capital, primary OKX instrument IDs, and existing positions/open orders. Save only nonsecret preferences with `atlas init`. Without an explicit declaration of no positions/open orders, exposure is `unknown` and an entry remains blocked. A no-position declaration expires for entry decisions after 24 hours. The stored capital is a user-reported planning amount, not a read of exchange balances.

## Independent risk gate

`risk_control` runs after source and specialist roles, before strategy and chief review. Its `payload.assessment` is recomputed from the frozen snapshot and recorded policy during audit. It records timestamped current ticker, prior 20 *closed* daily bar support/resistance, entry and stop references, blockers, 0.5% default per-trade loss budget and 25% default notional cap. These defaults are conservative planning parameters, not a validated optimum. For 300 USDT they are 1.50 USDT and 75 USDT respectively. Fees, spread and slippage are included in estimated unit loss. Existing exposure, pending orders, price gaps, stop failure and correlated holdings can increase actual loss. If account exposure is unknown, do not present an executable order.

An entry is blocked unless all of these are documented: live fresh ticker at report publication; selected USDT spot instrument; recent exposure declaration; complete upstream evidence; bullish closed daily trend; no timeframe conflict; a closed daily breakout above prior resistance with volume above the previous 20-day average; independently credible, multiple-testing-adjusted out-of-sample improvement from a full committee replay; final committee `APPROVED`; valid OKX `tickSz`, `lotSz` and `minSz`. Full committee replay is currently unavailable, so current reports should normally say **no entry**. A technical proxy backtest is not enough.

If future evidence satisfies all gates, the plan uses a limit buy with price rounded to exchange tick size. Total base quantity is the smaller of risk-budget sizing and the notional cap, rounded down to lot size. Split 50%/30%/remainder across confirmed breakout, successful retest and continuation only when *each* stage meets the exchange minimum; otherwise one small limit order is shown. The split percentages are an operational convention, not evidence of higher win rate. No plan uses the entire capital. Recheck live book, fees, available balance and stop settings before manually placing each stage. Market orders have uncertain execution price and are not the default. See [OKX order types](https://www.okx.com/en-eu/help/how-do-i-trade-with-different-order-types) and [OKX instrument rules](https://www.okx.com/docs-v5/en/) for the exchange fields and behavior; applicability depends on the user's region and account.

## Watching and rechecking

Support is the minimum low and resistance the maximum high of the 20 confirmed daily bars preceding the latest confirmed bar. They are historical structure, not guaranteed floors or ceilings. Watch for a closed daily bar above resistance with volume greater than the previous 20-day average, or a support test followed by a daily close back above support. A touch alone does not establish a reversal or breakout.

When the user says a previously reported key level was reached and asks for judgment, run `atlas reassess PREVIOUS_RESEARCH_ID`. It creates a new ID and a fresh snapshot for the same instrument, preserves the prior levels as context, and gives a new timestamped decision. Do not assert that the old level was actually touched unless the newly retrieved evidence verifies it. A prior report is never silently updated to look current.

Every market report must end with the observed price and UTC timestamp, the observable range/trend judgment, entry yes/no and reasons, support/resistance with their derivation, what to observe next, and (only when the gates pass) the limit price, split quantities, stop reference and estimated loss. The user can request a recheck at any time.
