# ATLAS 0.4.0 本地可视化验证记录

日期：2026-10-26，macOS arm64，Python 3.12.14。

| 检查 | 实际结果 |
|---|---|
| Python 测试 | `94 passed`；新增目录缓存/状态过滤、回环 Host/令牌/Origin/本地配置测试 |
| JS 语法 | `node --check atlas/web/static/app.js` 通过 |
| Skill 源码验证 | `scripts/validate.py` 通过，检查 90 个发布文件 |
| Agent Skills 格式 | `skills-ref validate` 通过 |
| Python 构建 | sdist 与 wheel 0.4.0 构建成功；wheel 中包含三个网页静态文件 |
| 依赖漏洞扫描 | 开发环境旧 pip 25.0.1 报告已知问题；升至 PyPI pip 26.2.2 后，`pip_audit --skip-editable` 报告无已知漏洞。可编辑的本地 ATLAS 包不在 PyPI 漏洞索引中 |
| 用户安装 | `scripts/install.py --with-mcp` 升级独立 runtime 与 Skill；`atlas doctor` 报告 0.4.0、资料已配置、OKX CLI 已登录、权限 READ_ONLY |
| 实时 OKX 目录 | 公共接口返回 SPOT 1212（live 1199）、SWAP 522（live 522）、FUTURES 281（live 279）；校验后保留率均为 100%。数量只代表该时刻该区域接口返回值 |
| 浏览器实测 | 本地页面加载、动态首页、FUTURES 弹窗、切回 BTC-USDT 现货、运行完整委员会、角色状态轨道/依赖与行情图、风险结论、中文/英文切换、本地操作记录均出现；内嵌报告窗显示正文与 SVG 图 |
| 新格式合约 | `BTC-USD_UM-261030` 快速研究完成并保留 1D/1W/1M 历史不足事实；没有生成开仓结论 |
| 实时研究 | BTC-USDT 完整网页研究生成 `atlas_2d0b8ba7e7a942af`；ETH-USDT 安装版 CLI 生成 `atlas_e6e077c155aa4245`。两者均为 `INSUFFICIENT_DATA`，未通过开仓门槛 |

本记录不证明收益、真实交易胜率、所有地区仪器可用性或独立 LLM 智能体协作。网页当前使用确定性研究图。交割合约可选择并研究公开行情，换月与保证金策略及可执行仓位未验证，因此不生成开仓计划。历史报告是当时快照。
