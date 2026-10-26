# ATLAS acceptance matrix

This matrix describes release 0.3.0 scope and evidence. Earlier studies remain in `validation-report.md` and `validation-report-v0.2.md`; current onboarding, risk-control and reassessment checks are in `validation-report-v0.3.md`. Entries below cannot be upgraded to verified solely because code exists.

| Requirement group | Implemented surface | Evidence / remaining boundary |
|---|---|---|
| Official review | Pinned READMEs, contribution/security/license files, Agent Skills spec and Marketplace FAQ | `source-review.md` + source lock; missing root trade-kit REVIEWING recorded |
| Portable install | User-space Python venv + source allowlist + launcher | Installer and packaging tests; Linux/Windows runtime requires actual OS verification |
| Official Skills | Version/capability/auth discovery and READ adapter | `capability-manifest.json`, provider tests/live verification; no official code republished |
| Data | Instrument verification, closed UTC bars, pagination/cache/budgets/provenance | Provider tests + actual live checks; cache/fixtures remain labeled |
| Quantitative indicators | Formula-based numerical engine and warm-up validation | Independent numeric tests; no predictive validity claim |
| Research graph | Coordinator + twelve roles including BTC/ETH specialists and independent risk control | Integration tests and saved event log; execution mode recorded |
| First-use profile | Language, USDT planning capital, primary instruments and recent no-position declaration in local nonsecret config | CLI/init tests; private balance is not queried, declaration expires after 24 hours |
| BTC/ETH specialists | Matching market/quote BTC and ETH closed UTC daily data; relative return/volatility/drawdown with recomputation gate | Synthetic and live runs; no invented dominance or on-chain metric |
| Evidence exchange | Versioned evidence, challenges and bounded rework | Contradiction/stale-upstream tests; unresolved severe issues block approval |
| Macro/Fed/news | Official feeds/series and read-only optional private providers | Missing consensus, revision vintages, licensed series or inaccessible feeds remain unavailable |
| Backtest/event study | Next-bar execution, explicit costs, chronological validation and event windows | Quant tests; full historical committee replay is not established by technical proxy |
| Strategy | Separate long/short/wait conditions and risk review | No orders; insufficient data can terminate with no candidate |
| Risk control and reassessment | Recomputed risk veto, publication-time quote freshness, 20-bar key levels, new-ID reassessment | Unit/integration/live examples; no all-capital order and no execution command |
| Calibration/edge | Qualitative confidence separated from empirical performance | Full-system statistical trading advantage and live win rate unproven |
| Memory | SQLite archive, versions, messages, audit, export/history | Storage/CLI tests; backup/deletion behavior documented |
| Reports | Chinese and English Markdown/HTML plus JSON; final timestamped market/entry section | Both variants generated together; archived observations become stale and must be refreshed |
| Security | Read allowlist, no arbitrary shell commands, redaction, source/package checks | Tests and dependency audit required; no comprehensive penetration audit claimed |
| Skill/client compatibility | Standard SKILL + Codex metadata + CLI + optional MCP | Official format check; only actually launched clients/OS can be verified |
| Publishing | MIT, descriptions, release notes, package builder and checklist | Not submitted, not signed/listed/approved by OKX; user action and platform review required |
