# ATLAS local visual research floor / 本地可视化研究台

![ATLAS 首页与研究设置 / Home and research setup](images/atlas-homepage.png)

首页先选择交易经验、市场类别、交易对、计划持仓时间和研究模式；下方研究台展示这次研究的证据、进度与结论。The home screen selects experience level, market, instrument, planned holding period and research mode; the dashboard below shows evidence, progress and findings.

Run the installed `scripts/atlas.py ui` or `atlas ui`. A browser opens a random local URL on `127.0.0.1`; `--no-open` prints the URL without opening it, and `--port 8765` selects a port. Leave the terminal process running while using the page. Close it with Ctrl-C. The server has no remote bind or order endpoint.

首次使用时，Skill 检查并安装本地 Python 运行环境。若语言、本金、主要交易对尚未设置，网页会出现引导表单。配置存放在本机 ATLAS 数据目录的 `config.json`；已有配置不会再次询问。现有持仓/挂单必须由用户确认，旧确认会在开仓风险评估中失效。

## Controls / 界面操作

1. 选择 **现货 SPOT、永续 SWAP、交割 FUTURES**。目录从 OKX `/api/v5/public/instruments` 读取并显示当前状态，缓存最长 10 分钟。搜索框覆盖当前类别的全部返回项目；暂停交易的项目不可发起研究。
2. 选择交易对、完整委员会或快速技术扫描，并可写一条研究问题/备注。备注作为研究问题交给 Codex，同时记录在本地；它不改变价格计算或风控门槛。
3. 点击“开始研究”。12 个角色在完整模式下依赖排序执行；卡片、事件时间线和证据摘要显示存储的实际状态。快速模式只运行技术角色。网页必须完成 Codex CLI 研读才能发布正式简报。角色先整理来源与数值证据，再由一次 Codex 调用逐项写出判断；这不是 12 个独立模型。Codex 失败时任务明确失败，不用参数结果替代。
4. 查看已确认 15 分钟/1 小时及 UTC 日/周/月 K 线、成交量、风险控制的支撑/阻力、最新快照的开仓门槛和否决原因。点击中英文简报查看每个角色做了什么、得到什么。历史报告是其生成时的快照。
5. 到达旧关键位后点击“重新判断”会读取新行情并生成一个新研究 ID，与前次记录关联。不能仅凭触价自动下单。
6. “复盘档案”读取本机 SQLite 的研究版本/证据/事件摘要；交互日志位于 `ui-journal.jsonl`。两个文件都在 ATLAS 用户数据目录，权限限制为当前用户。

## Scope and data boundaries

- The web server accepts only loopback `Host`, checks a random per-process session token for every data endpoint and checks request origin on writes to the local profile or research queue. The URL token remains in the browser fragment and is removed from the visible address once loaded. Static assets contain no account data.
- There are no account-balance, position-fetch, order, transfer or bot endpoints. Profile capital is a planning input, not a verified OKX balance.
- Public inventory can include instruments outside the supported execution/risk model. Research still records data gaps. Only spot USDT can pass the current order-size risk gate; swap and expiry futures remain blocked for executable order plans. Expiry futures historical backtest does not model rollover or margin.
- Availability depends on the user's OKX region and live public data. The UI does not promise a complete market universe beyond the instruments returned by the selected OKX public endpoint at fetch time.
- A full committee report requires the existing data and audit gates. A quick scan is not a full committee approval. Trading edge and win rate have not been validated for the complete system.

The official API reference for the public catalog is [OKX V5 Get instruments](https://www.okx.com/docs-v5/en/#public-data-rest-api-get-instruments).

## 入场研究与分级简报

首页选择新手或资深交易员；新手页面和中英文简报使用大白话，资深版补充关键指标。短期计划可选 1h/4h/12h/1d，长期计划可选 1d/1w/1mo/3mo/1y。持仓时间是用户计划，并非价格预测。

入场时机研究员检查已收盘 15m 与 1H 的趋势、15m RSI 和成交量、1H ADX。图中白色粗线标所选周期的观察位；红色粗线是条件入场参考，未确认时仍只是观察情景。中心闪红只表示最新已收盘指标出现预设条件形态，并显示仍需风控复核，不等于即将出现大行情。每个角色的开始和结果都记在时间线。

1U 模式只对 OKX 永续合约做算术模拟：假设 1 USDT 保证金，50/100 倍对应 50/100 USDT 名义仓位。实际强平价、最小张数、资金费、标记价格与账户档位尚未核验。网页没有委托接口，不会代替用户下单；真实操作须另行获得具体交易授权并核验实时账户与规则。
