# ATLAS — Institutional Trading Intelligence

<img src="docs/images/atlas-project-icon.png" alt="ATLAS 项目图标" width="88" height="88">

[简体中文](README.md) · [English](README_EN.md)

**独立开发的 OKX 加密资产研究 Skill 与本地研究台。** 将 OKX 公共行情、分工研究、Codex 证据研读、风险审查和本地档案串成可复查的研究流程。本版本不提供真实下单功能。

ATLAS 的“机构级”描述研究流程组织方式，不表示受到 OKX、美联储或任何金融机构认可。它不承诺收益、胜率提升或所有智能体兼容。

## 首页与研究台

首页可选择新手或资深说明、现货/永续/交割市场、计划持仓时间和研究模式。它显示的是操作入口；行情判断须启动研究后查看。

![ATLAS 首页与研究设置](docs/images/atlas-homepage.png)

研究台展示各角色的证据进度、K 线、Codex 研读结论与风控结果。

![ATLAS 研究角色与 K 线图](docs/images/atlas-research-dashboard.jpg)

![Codex 研读结论与风控记录](docs/images/atlas-codex-review.jpg)

后两张图片展示一次已归档的 BTC-USDT 研究快照。价格与结论只对应截图中的时间；需要当前判断时，请重新运行研究。

## 安装与开始

需要 Python 3.11+。在项目根目录执行：

```bash
python3 -m venv .venv
# macOS / Linux
.venv/bin/python -m pip install '.[dev,mcp]'
.venv/bin/atlas doctor
.venv/bin/atlas ui
.venv/bin/atlas research ETH-USDT-SWAP --mode full --timeframes 15m,1H,1D,1W,1M
```

Windows 使用 `.venv\Scripts\python.exe` 和 `.venv\Scripts\atlas.exe`。只运行研究可安装 `.`；`dev` 用于测试、安全与构建，`mcp` 是可选协议服务依赖。

安装成 Codex 可发现的 Skill：

```bash
.venv/bin/python scripts/install.py
```

安装器在用户数据目录创建独立运行环境并将 Skill 复制到 `~/.codex/skills/atlas-institutional-research`；不复制密钥、缓存、研究记录或开发虚拟环境。默认数据与安装目录分离。已有准备好的环境可用 `--runtime-python PATH`；仅复制 Skill 可用 `--skill-only`。[安装、升级和卸载](docs/installation.md)。

在智能体对话中说：

- “使用 ATLAS 全面研究 ETH，分析日线、周线、月线多空趋势。”
- “研究 FOMC 公布后的 BTC 市场反应。”
- “回测 ETH 策略，并和简单趋势基线比较。”
- “重新审查上一份报告，查看尚未解决的数据冲突。”
- “查看过去一个月的研究记录。”
- “BTC 到了上次的关键位，重新判断现在能否开仓。”

简单价格查询使用轻量行情接口，不必启动完整研究委员会。

## 运行入口

| 目标 | 命令 |
|---|---|
| 打开本地可视化研究台 | `atlas ui`（`--no-open` 仅打印本地链接） |
| 环境与权限诊断 | `atlas doctor` |
| 首次设置语言、本金和交易对 | `atlas init --language zh --capital-usdt 300 --markets BTC-USDT,ETH-USDT --no-open-positions`（仅在确认无持仓和挂单时使用最后一项） |
| 完整研究 | `atlas research ETH-USDT-SWAP --mode full` |
| 快速研究 | `atlas research BTC-USDT --mode quick` |
| 15 分钟至月线研究 | `atlas research ETH-USDT-SWAP --timeframes 15m,1H,1D,1W,1M` |
| BTC 专项中文研究 | `atlas research BTC-USDT --mode full --lang zh` |
| ETH 专项英文研究 | `atlas research ETH-USDT-SWAP --mode full --lang en` |
| 到前次关键位重新判断 | `atlas reassess RESEARCH_ID` |
| 事件研究 | `atlas event-study --asset BTC-USDT --event FOMC` |
| 基线与实验技术代理回测 | `atlas backtest --asset ETH-USDT-SWAP` |
| 本地档案 | `atlas history` / `atlas history show ID` |
| 报告审查 | `atlas audit ID` |
| 导出 | `atlas export ID --format markdown` |
| 配置与能力 | `atlas config show` / `atlas capabilities --refresh` |
| MCP stdio 服务 | `atlas mcp` |

网页按需读取并短时缓存 OKX 现货、永续和交割合约公共目录，提供交易对搜索、研究角色进度、K 线、风险结论、中英报告和本地复盘。角色先整理证据，Codex 再逐项研读并形成结论；没有完成 Codex 审阅就不发布正式简报。一次 Codex 审阅不等于 12 个独立模型的判断。详见 [可视化研究台](docs/visual-dashboard.md) 与 [使用方法](docs/usage.md)。

## 协作、质量与留档

协调员通过带依赖的研究图安排宏观、美联储、新闻、技术、入场时机、情绪、历史/回测、BTC 专项、ETH 专项、独立风险控制、策略与首席审查十二个角色。两个专项研究员使用同类型、同计价货币的 BTC/ETH 已确认 UTC 日线比较相对收益、波动和回撤。风险控制员检查报价时间、关键位、持仓声明、单笔风险预算、交易规则与策略证据，向策略和首席审查提交可否决的评估。角色输出由 Schema 校验；数据校验和风险审查具有否决权。

默认 `--engine codex` 先执行真实计算，再调用本机 Codex CLI 研读冻结证据，报告保留模型与证据记录。`--engine deterministic` 只用于明确指定的计算诊断；`--engine host` 为客户端子智能体生成任务并接收 `atlas submit` 结果；`--engine llm` 需要用户自行配置兼容模型服务。[角色协议](references/agent-roles.md)、[架构](docs/architecture.md)。

OKX CLI、可配置只读 MCP 桥和公开 REST 按能力降级。不可用的新闻权限、宏观指标、市场预期或历史版本会列为缺失；完整研究缺少必要证据时保留 `INSUFFICIENT_DATA`。每次完成的研究同时保存 `report.zh.md`、`report.en.md`、对应 HTML 与 JSON；`--lang zh|en` 选择主报告语言。数据库、原始证据、角色版本、消息与审查记录保存在用户本地。[数据来源](docs/data-provenance.md)。

报告末尾以**报告生成时的报价**回答能否开仓、重点观察的支撑/阻力、确认方法及风险阻断原因。只有全部数据、研究和风险门槛通过才给出限价与分仓数量；目前完整策略优势未获验证，不能因价格触位就自动建议下单。用户请求复查时，`atlas reassess ID` 创建新研究和新快照，保留旧关键位以便比较。[风险控制与复查规则](references/risk-and-reassessment.md)。

## 量化边界

回测采用已收盘数据、次根开盘成交、显式交易成本、时间划分样本外检验和滚动评估。比较实验中的 `atlas` 是可复现的**技术代理策略**；没有逐时点历史委员会特征，就不声称完成全系统历史重演。修订后的宏观数据不能冒充当时公布版本。置信区间、样本量、负结果与缺失资金费率均应显示。[回测方法](references/backtesting.md)。

## 验证与发布

```bash
python -m pytest
python scripts/validate.py
skills-ref validate "$PWD"
python -m pip_audit
python -m build
python scripts/validate.py --package dist/atlas-institutional-research-0.6.0.zip
```

本版实际执行证据与限制见 [0.6.0 验证报告](docs/validation-report-v0.6.md) 和 [验收矩阵](docs/acceptance-matrix.md)。格式检查不证明研究预测有效；Linux、Windows、Claude Code、Cursor、OpenClaw 的未运行项目必须标为未验证。[兼容性](docs/compatibility.md)。

项目采用 [MIT](LICENSE)，已在 GitHub 公开托管，尚未发布到 OKX Marketplace。Marketplace 要求账户/身份条件、格式检查、安全扫描和平台审核，准备了 [提交说明](docs/publishing.md)。提交 Marketplace 前仍需确认数据使用许可和第三方依赖审计结果。
