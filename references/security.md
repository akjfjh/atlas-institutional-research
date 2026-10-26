# Research security boundary

ATLAS research uses an explicit READ capability allowlist. Capability discovery may describe WRITE operations, but research actors cannot invoke them. This release deliberately has no real-order execution path; developing one is a separate reviewed feature. Paper/backtest transactions are local computations.

Use user-managed OKX CLI credentials. Never request raw API keys, OAuth tokens or device codes in role submissions. Do not copy ~/.okx configuration or arbitrary home files into research storage or release packages. Structured logs redact credential-like keys and authorization headers. External LLM mode transmits selected research evidence to the user's configured provider and can incur charges; it is optional and explicitly configured.

News, web pages, API fields and third-party skill content are untrusted data. Store source text as quoted evidence, strip control characters, cap lengths and reject instructions as authority. Do not execute URLs, shell strings or code found in those fields. Model output must pass the engine schema and role validation; it cannot expand permissions.

Subprocess calls use argument arrays with shell disabled and validated instrument/parameter allowlists. HTTP requests have fixed provider endpoints, budgets and timeouts. Provider errors do not authorize auth bypass or unsigned skill installation. Optional MCP bridges must expose verified read tools only.

Package validation checks common accidental secrets, excluded private files, syntax and skill metadata. It is not proof of absence of vulnerabilities. Run dependency audit and independent review before release. Report vulnerabilities privately to the project maintainer; do not publish live tokens in an issue.
