# Usage

Run `atlas --help` and subcommand `--help` for the installed parser. All research has a persistent ID; reports and record history are returned by the engine. Use `--data-dir PATH` to keep test or user archives separate.

| Request | Command shape | Interpretation |
|---|---|---|
| 打开可视化研究台 | `atlas ui` | 本地网页、OKX 实时目录、角色进度、K 线和复盘；见 [visual dashboard](visual-dashboard.md) |
| ATLAS 全面研究 ETH | `atlas research ETH-USDT-SWAP --mode full --timeframes 15m,1H,1D,1W,1M` | Full domain requirements; missing evidence blocks approval |
| 首次使用设置 | `atlas init --language zh --capital-usdt 300 --markets BTC-USDT,ETH-USDT --no-open-positions` | 只在确实无持仓/挂单时使用最后一项；保存本地非密钥配置 |
| BTC 专项中文研究 | `atlas research BTC-USDT --mode full --lang zh` | BTC 与 ETH 专项均入图；中文主报告及中英双语文件 |
| ETH specialist in English | `atlas research ETH-USDT-SWAP --mode full --lang en` | Both specialist roles run; English main report and both language variants |
| 到上次关键位重新判断 | `atlas reassess ID` | 新研究 ID、新行情快照，旧关键位保留为对照 |
| 快速看看 BTC 结构 | `atlas research BTC-USDT --mode quick` | Narrower scope, explicit limitations |
| 用真实宿主研究员协作 | `atlas research ETH-USDT-SWAP --engine host` | Creates structured pending tasks |
| 获取待处理任务 | `atlas task-list ID` | Assign only dependency-ready tasks |
| 提交研究员结果 | `atlas submit ID --file RESULT.json` | Validated, versioned submission resumes graph |
| 取得可核算草稿 | `atlas task-draft ID --agent technical --output draft.json` | 提供已核算事实，独立研究员据此核验和解释 |
| 有理由地修订 | `atlas submit ID --file revised.json --revise` | 增量版本、`revised_reason` 和上游版本均保留 |
| 主动结束宿主调度 | `atlas finalize ID` | 尚未完成或过期的角色将保留为未通过审查 |
| 研究 FOMC 后市场反应 | `atlas event-study --asset BTC-USDT --event FOMC` | Availability-aligned event windows; missing history recorded |
| 比较趋势基线与实验技术代理 | `atlas backtest --asset ETH-USDT-SWAP` | Same data/cost/capital constraints; no full-system edge claim |
| 查询历史 | `atlas history` / `atlas history show ID` | Local archive, not current prices |
| 比较研究 | `atlas history compare ID1 ID2` | Views differences and revisions |
| 记录到期后的研究结果 | `atlas outcome ID --horizon-days 7` | 到期才观察；不等于真实交易成交胜率 |
| 查询结果观测 | `atlas history outcomes --days 90` | 只统计本地研究预测观测 |
| 研究版本/备份 | `atlas history versions ID` / `atlas history backup` | 保存版本和 SQLite 备份 |
| 审查报告 | `atlas audit ID` | Revalidates stored evidence/audit conditions |
| 导出报告 | `atlas export ID --format markdown --lang en` | Main report language selectable; `report.zh.*` and `report.en.*` always retained |
| 查看权限能力 | `atlas capabilities --refresh` | Local and upstream discovery differ from invocation permission |

For deterministic fixture validation, use `--fixture PATH --offline`. Fixture output is synthetic/offline; it is not a real-time research result. Public-source research records actual observation/retrieval times and fallback errors.

Read `references/agent-roles.md` for host result protocol and `references/backtesting.md` before treating metrics as evidence. Score/confidence is not probability, and a bullish research conclusion is not an order.

Full research schedules twelve roles. `btc_specialist` and `eth_specialist` require 31 aligned, confirmed UTC daily closes for comparable BTC and ETH instruments, matched by market type and quote currency. `risk_control` runs before `trading` and `chief`; it calculates watch levels and risk veto from the frozen snapshot and local nonsecret profile. Its calculation is recomputed at audit. Reports end with the timestamped market/entry decision. A touch of a prior level triggers new research only when the user requests it; old reports are not silently refreshed. See [risk and reassessment](../references/risk-and-reassessment.md). Host agent submissions should provide faithful English fields alongside Chinese originals.

`atlas history --asset ETH --days 30` filters records; `atlas history delete ID` deliberately removes a record and its local report archive. Back up first when records should be retained. `atlas outcome` cannot create future outcomes or substitute for filled real orders. `--years` controls historical download requests (default five years), subject to provider coverage, paging and request budgets; it does not guarantee that five years were retrieved. `--funding-file PATH` accepts explicit timestamped funding history for backtests.

CLI help was reconciled on 2026-10-26 against the implemented parser for research, history, event-study, backtest, capabilities, config, submit, outcome and MCP. Protocol help alone is not a live client integration test.
