# Official source review — 2026-10-26

Sources were retrieved at pinned commits. SHA-256 and retrieval/404 status are retained in `upstream/source-lock.json`. Full upstream files were read for implementation/review guidance; they are not ATLAS code.

| Repository | Pinned commit | File | Result |
|---|---|---|---|
| okx/agent-skills | `0ea4378645df` | README.md | retrieved |
| okx/agent-skills | `0ea4378645df` | CONTRIBUTING.md | retrieved |
| okx/agent-skills | `0ea4378645df` | REVIEWING.md | retrieved |
| okx/agent-skills | `0ea4378645df` | SECURITY.md | retrieved |
| okx/agent-skills | `0ea4378645df` | LICENSE | retrieved |
| okx/agent-trade-kit | `c8f7d7654548` | README.md | retrieved |
| okx/agent-trade-kit | `c8f7d7654548` | CONTRIBUTING.md | retrieved |
| okx/agent-trade-kit | `c8f7d7654548` | REVIEWING.md | not_available |
| okx/agent-trade-kit | `c8f7d7654548` | SECURITY.md | retrieved |
| okx/agent-trade-kit | `c8f7d7654548` | LICENSE | retrieved |
| agentskills/agentskills | `69ef37e9424c` | skills-ref/README.md | retrieved |
| agentskills/agentskills | `69ef37e9424c` | skills-ref/pyproject.toml | retrieved |

The Apache-2.0 root and skills-ref licenses were also retrieved at the Agent Skills commit and added to the source ledger to preserve attribution for local review snapshots.

## Relevant findings

- Agent Skills requires matching lowercase/hyphen skill name, description ≤1024 characters, YAML frontmatter and progressive references. Metadata is a string-to-string map. ATLAS uses this portable form; the OKX contribution guide shows a nested `metadata.agent` extension, which is not required for this independent skill.
- OKX review guidance requires real command/tool names, optional-skill fallbacks, proportional write authorization and concise modular instructions. ATLAS delegates to interfaces, does not republish official implementations and blocks research writes.
- The current agent-skills README lists nine official skills; the broader agent-trade-kit README lists a smaller skill table and contains unscoped npm badge names/older links. Actual package/help/source verification takes precedence over illustrative README counts.
- No root `REVIEWING.md` exists at the pinned agent-trade-kit commit (HTTP 404); the agent-skills review checklist is available and was read.
- Both OKX repositories are MIT licensed. Their security policies prioritize credential leaks, unintended fund actions and auth bypass, and request private vulnerability reports. ATLAS retains its own independent authorship and security boundary.

- The local bundled Codex quick validator rejects the current specification's optional top-level `compatibility` field. ATLAS keeps environment requirements in the body so both validators can accept the portable metadata subset.

## Specification and reference validation

Specification: https://agentskills.io/specification

The spec links the official reference library at https://github.com/agentskills/agentskills/tree/main/skills-ref. Its README labels the library as demonstration/reference code, not production assurance. Its validator checks format, not predictive validity or complete security.

```bash
python -m pip install 'https://github.com/agentskills/agentskills/archive/69ef37e9424c0a7ea9dd2293b559e43ec8176379.zip#subdirectory=skills-ref'
skills-ref validate "$PWD"
```

## Marketplace source

https://www.okx.com/agent-tradekit/skills (FAQ reviewed 2026-10-26): community publication requires account/identity eligibility, format checks, security scans and platform approval. Exact upload limits and account-region eligibility were not established from public docs. See `publishing.md`; no submission was made.

Reference-validator behavior observed: validating literal `.` failed because it used the unresolved directory name; validating the absolute skill directory succeeded. Use an absolute directory path (PowerShell users should also pass a complete path). The bundled Codex quick validator also passed after using the portable metadata subset.
