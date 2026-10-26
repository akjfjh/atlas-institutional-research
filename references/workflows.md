# Mode workflows

Use the Python launcher `python /path/to/atlas-institutional-research/scripts/atlas.py` wherever `atlas` is shown if it is not on PATH. Check `atlas --help` and each subcommand's help for the installed version.

## Full and quick research

`atlas research ETH-USDT-SWAP --mode full --timeframes 15m,1H,1D,1W,1M`

The coordinator validates the instrument, fetches current data and historical bars, schedules evidence roles by dependencies, reviews conflicts, and checks risk. Codex CLI then reviews the frozen evidence and writes the final bilingual synthesis and per-role interpretation. A missing Codex review blocks report publication. A critical missing data domain blocks approval; a partial report remains useful but must be labeled as partial.

Quick mode narrows the research scope. It never turns a smaller evidence set into a full committee approval or a calibrated win rate. Use `--offline --fixture PATH` only for explicit fixture/cached research, preserving offline labels.

## Codex, host or diagnostic research

The default is `--engine codex`. It requires a signed-in Codex CLI and uses one structured, read-only Codex run over the role evidence. One run is not twelve independent model agents. The data, indicator and risk computations remain independently checked. Use `--engine deterministic` only when an explicit calculation-only diagnostic or fixture result is wanted.

`atlas research ETH-USDT-SWAP --engine host`

Read the returned Research ID and pending tasks with `atlas task-list ID`. Submit role JSON using `atlas submit ID --file RESULT.json`. Submission is an append-only versioned research artifact, not permission to run arbitrary commands. A configured compatible LLM service can be selected with `--engine llm`; inspect the provider settings and usage budget first. Deterministic mode has no LLM API requirement.

## Audit and history

`atlas audit ID` rechecks evidence, conflicts and approval invariants for a saved research record. It does not silently replace observations with current prices. Re-run research for an updated view.

`atlas history` lists local records; `atlas history show ID` opens structured history; `atlas history compare ID1 ID2` compares research versions; `atlas export ID --format markdown` creates an export. Confirm exact supported arguments with help before deleting records. Back up the local database before intentional deletion.

Reports, evidence, versions, messages and review issues share the Research ID. Export only data the user intends to share; local defaults do not imply cloud upload authorization.

`atlas history --days 30 --asset ETH` filters history. Use `atlas history versions ID` for revised role records and `atlas history backup` for a database backup. `atlas outcome ID --horizon-days 7` records a matured research forecast observation; `atlas history outcomes --days 90` retrieves such observations. These are not filled-order results or a real-trading win rate.
