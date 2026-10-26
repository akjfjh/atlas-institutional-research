# Data provenance and allowed gaps

Priority is verified OKX CLI, a deliberately configured verified READ MCP bridge, then official OKX public REST. Every fallback is recorded. No bridge configuration means MCP is unavailable, not silently simulated. Default UTC bars map to 1Dutc, 1Wutc and 1Mutc in OKX. Distinguish confirm=0 from confirmed bars; do not mix mark/index/spot/swap prices.

Supplemental official data can include FRED, Federal Reserve releases, BLS, BEA and Treasury. Current/revised observations have that status. Series licensing and provider terms still apply to redistribution. PMI, consensus forecasts, options analytics and social sentiment may require licensed feeds or authorization; record them as unavailable rather than fabricating them.

Price freshness uses market-scale thresholds; macro monthly observations use release-scale timing. Older but not superseded monthly data can remain valid context, while an old market price cannot be described as live. Offline fixtures are intentionally synthetic test inputs and are never an operational feed. Cache use preserves original observation and retrieval times and labels its mode.

Raw source URLs, source identities, request/result fingerprints, units and timestamps are retained with the Research ID. Do not store authorization headers or user secrets. Public data retrieval sends only the needed instrument/series parameters to the provider.
