# Compatibility status

| Surface | Design target | Evidence required before claiming verified |
|---|---|---|
| macOS Apple Silicon | Python 3.11+ user install | Installer, CLI, tests and real public data execution on this host |
| Linux | pathlib, user-space venv, XDG data location | Actual Linux CI/execution; not implied by syntax checks |
| Windows | pathlib, Scripts/python.exe, LOCALAPPDATA | Actual Windows CI/execution; not implied by mocked path tests |
| Codex | Agent Skills SKILL.md + local launcher + host protocol | Discoverable install and real invocation must be distinguished |
| Claude Code | Agent Skills + CLI | Client-specific integration not assumed |
| Cursor | Skill/CLI or stdio MCP | Client-specific launch test not assumed |
| OpenClaw | Agent Skills + CLI | Client-specific launch test not assumed |
| Other clients | Standard Skill/JSON/optional MCP | Feature support and approvals remain client-specific |
| Compatible LLM API | Configured structured research provider | Live external call only if user supplies credentials/consents to use |

The project format and core engine avoid developer-specific paths. Format validation does not prove all clients support delegation, schemas or process execution identically. Actual results and untested surfaces are maintained in `validation-report.md` and the acceptance matrix.
