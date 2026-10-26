# Troubleshooting

Run `atlas doctor` and inspect source errors before interpreting a report. Use the launcher in `scripts/atlas.py` if the `atlas` executable is not on PATH.

- Python absent: install Python 3.11+ from its official distribution or use an existing environment, then run `python scripts/install.py`. Do not hardcode a developer's cached Python path.
- OKX CLI absent: public REST remains available; authenticated sentiment/news and verified CLI capabilities are unavailable until official CLI/auth setup succeeds.
- OAuth logged in but Marketplace error 50106: the installed CLI's Marketplace endpoint may still require request signatures. This does not justify dumping credentials or bypassing signing. Research public endpoints can operate separately. Diagnose against the exact installed CLI version.
- Rate limit/timeouts: use bounded backoff and request budgets; preserve partial-data status. Repeated failure should end the run, not trigger unbounded retries.
- Missing monthly history: use fewer valid indicators with explicit warm-up gaps. Do not create monthly values from a tiny series.
- Full report not APPROVED: inspect review issues and unavailable domains. Missing reliable data is a valid terminal outcome. `atlas audit ID` rechecks a stored report; `atlas research ...` obtains fresh data.
- Other clients: Agent Skills format validation does not prove a client actually launches the engine. Verify each client's install location, command execution and MCP behavior separately.
