# Event study and backtesting protocol

Run `atlas backtest --asset ETH-USDT-SWAP` or `atlas event-study --asset BTC-USDT --event FOMC`; inspect subcommand help for supplied data/event files and history limits. Keep the exact run configuration and original data provenance with the saved result.

Indicators at bar t use only observations available through t. A signal formed at t's close can fill no earlier than the next bar's open. Event windows start with the first eligible observable price at/after first availability, not a price chosen because it gives a favorable result. Reject publication/availability times earlier than the source can justify. Coincident events and overlapping windows limit causal interpretation.

Time-based training/OOS splits and walk-forward segments remain chronological. Fix parameter choices before independent evaluation. Account for both entry and exit costs, bid/ask spread, adverse slippage and signed perpetual funding at known funding times. No funding history means funding-adjusted performance is not established. Model position sizing and capital constraints consistently between methods. Do not report a leverage guarantee or a liquidation model that the implementation has not verified.

Report trade count, net return, gross/mean wins and losses, win rate, payoff ratio, expectancy, profit factor, drawdown, Sharpe/Sortino/Calmar where defined, and IS/OOS results. Undefined ratios should be null/explained, not infinity disguised as excellent performance. Bootstrap intervals need a stated seed and sampling unit; dependent returns call for blocks. Small samples and correlated event windows reduce reliability.

`baseline` and `atlas` technical proxy comparisons use the same asset, bars, chronology, capital and cost assumptions. A technical proxy is **not** a historical replay of full macro/news/Fed committee research. Without archived point-in-time committee features, no full-system performance improvement may be claimed. Show unfavorable cases, unstable parameters and no-improvement outcomes.

Event history supplied by the user needs event type, event time, publication time, first availability, source and affected asset. Actual/expected/surprise may be null. Revised macro series cannot substitute for their first-release vintages. Historical similarity is descriptive matching; display both favorable and adverse analogues and unmatched features.
