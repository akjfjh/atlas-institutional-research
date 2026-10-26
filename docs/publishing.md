# Release and OKX Marketplace preparation

ATLAS is an independent project. No release or Marketplace submission is made by these scripts. Local validation is not platform approval or endorsement.

## Prepare a reproducible release

1. Run the actual full test suite and capture results; run the dependency audit and resolve/report findings. Run the official Agent Skills validator and this project's private-file/source scan.
2. Re-run a real public-data research example and archive its ID, source timestamps, status, limits and generated reports. Keep an explicitly labeled offline fixture example as an additional reproducibility aid, not as a substitute for live proof.
3. Review `acceptance-matrix.md`, `validation-report-v0.3.md` and the release notes. Untested clients, missing vintage/consensus data, unsupported liquidation models or incomplete prediction-calibration work must remain visible.
4. Build the Python wheel/sdist with `python -m build`. Build the Skill ZIP with `python scripts/validate.py --package dist/atlas-institutional-research-0.3.0.zip`. The ZIP excludes .venv, authentication files, database/cache records, local reports, runtime markers and developer inputs. Inspect the actual archive inventory and checksum before sharing.
5. For a user-authorized GitHub release, create a repository/release with MIT license, version, installation/removal steps, reproducible commands, source provenance and the validation record. No repository URL is invented here.

## Marketplace workflow

The [official Marketplace FAQ](https://www.okx.com/agent-tradekit/skills) states that community submission requires an OKX account with completed identity verification, standard skill format checks and security scans, followed by approval. It also describes platform signing of listed skills. These are platform controls; ATLAS cannot self-award a safety score or signature.

The [official agent-skills contribution guide](https://github.com/okx/agent-skills/blob/github-main/CONTRIBUTING.md) separately describes contributing a `skills/<skill-name>/SKILL.md` folder by pull request. A PR to that repository and a community Marketplace submission are distinct paths. Confirm the actual interface and current publication terms in the user's account before submission. The public documentation reviewed does not establish every upload size/type/field limit, review SLA or eligibility for a particular jurisdiction.

A user must explicitly authorize publishing and complete any required account/legal acceptance. Supply the release ZIP or repository URL through the platform's actual submit interface, add a truthful description and screenshots from the saved example, and wait for its review result. Do not state that listing has occurred until the platform confirms it.

## Submission copy

**Chinese title:** ATLAS 机构研究与量化验证  
**English title:** ATLAS Research and Quantitative Validation

**Chinese description:** 基于 OKX 行情与可核实宏观/政策资料的独立研究工具。提供日/周/月多周期指标、结构化研究角色协作、事件研究、含成本回测、证据审查与本地历史档案。数据缺失会显示限制；默认只读，不提供收益或胜率保证。

**English description:** Independent research tool combining OKX market data with verifiable macro and policy context. Includes multi-timeframe analysis, structured research collaboration, event studies, cost-aware backtests, evidence audit and local archives. Missing data remains visible; research-only by default, with no promised returns or win rate.

**Screenshot plan:** capture a real report's source/status header; three-timeframe table; baseline/proxy comparison with costs and CI; unresolved review issues; local history listing. Do not hide rejected/insufficient-data status or select only profitable examples.

**Release notes:** Version 0.3.0 adds first-use profile setup, an independent risk-control role, timestamped final entry/observation sections, and fresh reassessment of prior levels. Consult the executed validation report and acceptance matrix for supported and unverified capabilities. No independent statistical evidence of a full-system trading advantage is claimed.
