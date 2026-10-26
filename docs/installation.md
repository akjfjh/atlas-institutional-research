# Installation, update and removal

## Runtime requirements

Python 3.11+, HTTPS connectivity, and an authenticated Codex CLI on `PATH` are required for the default research mode. Check with `codex login status` and `atlas doctor`. Codex receives a compact, frozen evidence packet in a read-only invocation; a failed Codex call blocks publication of a completed report. An explicit `--engine deterministic` remains available for fixtures and diagnostics. The official OKX Node CLI is optional; it is preferred when available and verified. Obtain Node/npm and the CLI from their official sources. `npm install -g @okx_ai/okx-trade-cli` installs it; public market requests do not require trading credentials. User-managed news/positioning authorization is optional and never required for public fallback.

## Development installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install '.[dev,mcp]'
.venv/bin/atlas doctor
.venv/bin/python -m pytest
```

On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe` and `.venv/bin/atlas` with `.venv\Scripts\atlas.exe`. Do not assume the shell has activated the environment.

## Discoverable Skill installation

Run `.venv/bin/python scripts/install.py` from a trusted source checkout, or use another verified Python 3.11+ executable. On this macOS host, `python3` is Python 3.9 and cannot run the installer. The installer creates a separate user runtime using Python's venv and pip, then copies a publication allowlist into `~/.codex/skills/atlas-institutional-research` (or `$CODEX_HOME/skills/...`). It does not need administrator rights. Repeat the same command to upgrade: identity is checked before replacing a previous installation, files are staged before replacement, and the runtime is reused. Research records remain in their separate data directory.

When a discoverable Skill is present but its runtime is missing, the same installer can run **inside that installed Skill folder** to bootstrap the runtime in place. Then run `python scripts/atlas.py doctor`. On first use, the Skill asks for language, trading capital in USDT, primary instrument IDs and any positions/open orders; `atlas init` stores those nonsecret answers in the local data directory. Use `--no-open-positions` only after an explicit user statement. That declaration expires after 24 hours for an entry assessment; ATLAS does not query private balances or positions. The user may edit the profile by rerunning `atlas init`.

After environment setup, run `python scripts/atlas.py ui` to open the loopback dashboard. The first page offers the same onboarding fields if the local profile is incomplete. Use `--no-open` to print its local link, and Ctrl-C to stop the server. See [visual dashboard](visual-dashboard.md).

Options: `--skill-dir PATH`, `--venv PATH`, `--python PYTHON_EXECUTABLE`, `--runtime-python PATH` (reuse an existing prepared environment), `--with-mcp` (install the optional SDK), `--skill-only` (copy only). Each has CLI help. A local runtime marker is generated only at installation and excluded from distribution. Use the installed `scripts/atlas.py` by full path when `atlas` is not on PATH.

The installer does not automatically register the Skill in every client's configuration. For Claude Code, Cursor, OpenClaw or another Agent Skills client, use its documented skill location or point it at the installed folder. The core CLI works independently. Only actually tested clients may be claimed as verified.

## Optional compatible LLM and MCP

Deterministic research has no model-service requirement. Set nonsecret `llm_model` and `llm_base_url` in `<data-dir>/config.json`, and supply `ATLAS_LLM_API_KEY` only through the local process environment or secret management. Set both `llm_input_usd_per_million` and `llm_output_usd_per_million` to the chosen provider's verified current prices so a monetary budget can be reserved before a request. Use `max_llm_calls`, `max_cost_usd` and `llm_max_output_tokens` to bound it. `atlas config show` displays the effective nonsecret configuration; keys are rejected in the config file and must not be added to skill files. External service use may transmit selected research inputs and incur the user's provider charges. Host mode uses the existing client's agents with structured task/submission commands.

Install `.[mcp]` to expose `atlas mcp` as a local stdio server. In a client's MCP configuration set command to the full installed `atlas` path and args to `["mcp"]`. Do not add unrelated account/trade modules to research.

For the **optional OKX MCP data source**, set nonsecret `mcp_command` in `<data-dir>/config.json` to an argument array such as `["/absolute/path/to/npx","--yes","@okx_ai/okx-trade-mcp@latest","--modules","market,news,smartmoney","--read-only"]`. Ensure the child process can find Node in its `PATH`; install ATLAS with `.[mcp]` for the bridge SDK. The bridge checks a read-tool allowlist before each call. The tested official server exposes `market_get_ticker` in this read-only module set. Keep exchange credentials in the official profile or process environment, never in this JSON array. Pin the MCP package version for reproducible production operation after verification.

## Removal and data preservation

Remove the installed `atlas-institutional-research` skill directory to remove discovery. Remove its dedicated runtime venv only if no other task uses it; the marker identifies that environment. Neither action removes local research records. Delete/export records deliberately through the installed CLI's documented history commands. Back up `atlas.db` and reports before deletion. Uninstall the Python distribution with `python -m pip uninstall atlas-institutional-research` from the relevant environment.

## Data directory

Default archive paths are `~/Library/Application Support/ATLAS` on macOS, `%LOCALAPPDATA%\ATLAS` on Windows, and `$XDG_DATA_HOME/atlas` (or `~/.local/share/atlas`) on Linux. Override with `ATLAS_DATA_DIR` or `--data-dir PATH`. Nonsecret settings are read from `config.json` in that directory. Research records use `atlas.db`; reports are under `reports/RESEARCH_ID`.
