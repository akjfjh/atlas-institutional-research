# Optional official capability integration

ATLAS integrates via verified interfaces and adapters rather than redistributing official skill implementations. Use `atlas capabilities --refresh` to compare the pinned baseline manifest with the current official GitHub tree. Actual installed tool availability and authorization are separate checks.

| Baseline skill | Research use | Permission boundary |
|---|---|---|
| okx-cex-auth | Detect/setup user-managed official auth | Auth status only in automatic research |
| okx-cex-market | Market, bars, indicators and derivatives | READ public |
| okx-cex-trade | Capability discovery only | WRITE blocked; no real orders |
| okx-cex-portfolio | Optional account context only if explicitly requested | Private READ, no transfers |
| okx-cex-bot | Capability discovery only | Creation/amend/stop blocked |
| okx-cex-earn | Capability discovery only | Subscribe/redeem/transfer blocked |
| okx-cex-smartmoney | Optional positioning | Private READ if authorized |
| okx-sentiment-tracker | News and sentiment | Private READ if authorized |
| okx-cex-skill-mp | Version/capability discovery | Research does not install or remove skills |

The public Agent Trade Kit documentation can lag the current implementation. The project's pinned source review and `atlas doctor` record observed versions and command support. Missing official skills do not prevent public REST fallback; they do prevent claims that their private capabilities ran. See `docs/provider-verification.md` for actual command/API evidence.
