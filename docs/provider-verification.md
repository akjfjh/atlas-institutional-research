# Provider implementation and verification (2026-10-26)

This document describes implemented and measured behavior. It is not a claim of institutional endorsement or predictive accuracy.

## Verified upstream implementation

- `okx/agent-skills` official GitHub directory discovery found nine official skills; all current SKILL.md metadata versions were **1.4.9**. Snapshot: `references/capability-manifest.json`. `atlas capabilities --refresh` resamples names and versions; it does not install or execute discovered skills.
- The installed official `@okx_ai/okx-trade-cli` reports **1.4.9 (15d41f22)**. Commands/flags and MCP names were checked against its installed `dist/index.js` registry, including `market ticker`, `market candles`, `market instruments`, `market orderbook`, `market funding-rate`, `market open-interest`, `market mark-price`, `news latest`, `news coin-sentiment` and `smartmoney signal-overview-by-filter`.
- The current CLI candle enum **rejects `1Dutc`, `1Wutc`, `1Mutc`** although the public OKX API supports those UTC-opening bars. ATLAS deliberately routes daily/weekly/monthly UTC bars through public API instead of silently substituting the CLI's UTC+8-opening bars. Each source records `routing_reason`. Supported intraday queries retain CLI → configured MCP → public API priority.
- Agent Trade Kit's reference documentation explicitly says it may lag the source repository; CLI source and observed behavior resolve that discrepancy.

## Implemented boundary

`OfficialSkillAdapter` discovers official skills, detects local skill versions/CLI/auth state, validates a closed list of parameters, invokes read-only commands with `shell=False`, normalizes API/CLI failures and timeouts, and never accepts free-form flags or WRITE operations. OAuth status returned to callers excludes user codes, account identifiers, credential material and tokens. Status does not trigger a login, expand scopes or alter credentials.

The nine skill packages are discovered, not copied into this project. Working read wrappers integrate market data, news/sentiment and smart-money analytics. Auth is inspected only. Portfolio, trading, bots, earn and marketplace mutation capabilities are deliberately unavailable in the research adapter. No claim is made that all operations in the nine packages have been implemented.

`OKXMCPBridge` is optional and uses the official MCP Python SDK's stdio protocol. It checks tool discovery before invoking only the same read allowlist. It requires an explicitly configured command and optional `mcp` dependency; it does not automatically install or start arbitrary servers. **A real external OKX MCP server was not exercised on this machine.** Mock/interface validation is not live MCP validation.

## Public data and timestamps

Canonical OHLCV rows are sorted, deduplicated and checked for finite valid values. Incomplete/future candles are excluded. Daily, weekly and calendar-month `available_at` values are their actual UTC closing boundaries. Monthly periods use calendar arithmetic, not a fixed 30-day approximation. Explicit delayed availability times are preserved; availability earlier than candle close or later than now is rejected. Missing full completed periods are flagged stale. Requests above a 300-row endpoint page are paginated up to the bounded 5,000-row collection cap. Sources distinguish last trade, mark price, current funding and open interest; contract volume and base-currency volume are not conflated. Current funding is not treated as historical funding.

HTTP uses a pooled `httpx.Client`, global request budget and rate interval, bounded HTTP and OKX JSON-level throttling retries, timeouts, response-size cap and source-specific cache TTL. Cache writes use unique temporary files with atomic replacement, avoiding concurrent writers sharing one temp filename. Cached/offline/fixture provenance is explicit. Offline mode forbids fresh network/CLI calls. Only credential-free HTTPS public HTTP sources are accepted and OKX endpoints are restricted to official regional hosts.

## Supplemental sources

- FRED graph CSV supplies CPI, core CPI, PCE, core PCE, nonfarm employment, unemployment, real GDP, broad dollar, 2y/10y Treasury yields, 10y real yield, yield-curve spread, Chicago Fed NFCI, Fed assets, US M2, S&P 500 and Fed funds target upper bound.
- **FRED snapshots are latest revised series, not historical release vintages.** Observation dates are not release timestamps. These data are prohibited as point-in-time macro inputs for historical backtesting unless separately verified vintages/availability times are supplied.
- Broad dollar is labeled as a **proxy**, never ICE DXY. US M2 is a US liquidity proxy, never a canonical global-liquidity aggregate. PMI, ICE DXY and global liquidity remain explicit missing metrics.
- Fed monetary policy and speeches RSS and BLS latest-release RSS provide dated official announcements. OKX aggregated crypto news is marked `aggregated_unverified`; original article URLs may be missing. External text is untrusted data, not executable instructions. Publication time and actual event occurrence time are distinct; occurrence time is left null when unknown.
- FOMC event dates are extracted from official statement archive links. Exact intraday release times are **not** verified; event entry is conservatively aligned to the next UTC midnight. Those studies cannot claim announcement-minute effects. Consensus forecasts, surprise values and point-in-time macro vintages are null rather than invented.

## Actual live verification

Commands were run with the project `.venv` on macOS arm64. Outputs are recorded, not simulated:

- Live ETH-USDT-SWAP collection: **299 closed daily, 299 closed weekly, 81 closed monthly bars**, 17 available FRED series, 30 Fed feed items and 41 news items, 27 requests, 11.73 seconds; no provider errors in that run. See `provider-live-result.json`. The timestamp and price there are a historical verification snapshot, not a current trading quote.
- Live five-year ETH-USDT-SWAP daily history: **1,827 closed bars**, coverage complete for the requested boundary, six public requests, 4.1 seconds. See `provider-history-result.json`.
- FOMC archive extraction: **47 release dates** from 2021 through observed date, with conservative date-only alignment. See `provider-events-result.json`.
- BLS CPI historical archive HTTP returned **403**. See `provider-cpi-result.json`. Therefore a five-year CPI event backtest and surprise/vintage study **have not been validated**; source-verified user-supplied events can be loaded separately. The system does not bypass the restriction.
- Current CLI coin-sentiment and smart-money reads both returned real ETH analytics. The former returned published sentiment counts/label; the latter returned trader ratios/notional positioning. These are raw positioning data, never calibrated win probabilities. Regional entitlement may differ for other users.

A first implementation used a custom HTTP User-Agent that FRED timed out on. Replacing that nonstandard header with httpx's standard truthful client identifier resolved access. A repeat full live run verified all 17 series. No authentication or access warning was bypassed.

## Test scope

`python -m pytest tests/test_providers.py -q` passed **23 tests**, including numeric UTC close boundaries, incomplete/gap/duplicate OHLCV handling, request budgets, offline cache isolation, HTTP/JSON throttling, HTTP auth no-retry behavior, subprocess argument isolation, command injection and write denial, RSS injection-as-data, verified Fed release timestamps, optional MCP response envelopes, public host restrictions, fixture provenance, incomplete historical coverage, installed-wheel manifest fallback, requested-page limit bounds, concurrent same-URL cache writes and preservation/rejection of explicit candle availability times.

## Source links

- https://github.com/okx/agent-skills
- https://github.com/okx/agent-trade-kit
- https://www.okx.com/docs-v5/en/
- https://www.okx.com/docs-v5/agent_en/
- https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- https://www.federalreserve.gov/feeds/feeds.htm
- https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
- https://www.bls.gov/bls/news-release/cpi.htm
