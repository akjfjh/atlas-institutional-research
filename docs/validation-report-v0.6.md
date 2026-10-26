# ATLAS 0.6.0 验证记录

日期：2026-10-26。网页与 CLI 默认要求 Codex CLI 完成证据研读；数值计算、来源时间、风控和审查仍由本地引擎验证。

| 检查 | 结果 |
|---|---|
| Codex CLI | 本机已使用 ChatGPT 登录；`codex exec --sandbox read-only --output-schema` 返回结构化 JSON |
| 真实行情端到端 | BTC-USDT 快速研究 `atlas_348eedff0a2a43f2`：`engine=codex`、`codex_review.status=complete`、模型 `gpt-6.1-sol`，新手版结论由 Codex 生成，报告写明先等待且快速扫描未运行完整风控 |
| 完整委员会 | BTC-USDT `atlas_44cb22f973b54420`：12 个角色均有 Codex 的新手与资深双语结果；宏观、情绪与回测证据不完整，最终为 `INSUFFICIENT_DATA`，不能开仓 |
| 自动化回归 | `pytest -q`：101 通过；JavaScript 语法检查通过；技能包静态验证 96 个文件通过（含两张研究台截图） |
| 风控 | 该快速研究没有独立风控员，开仓门槛为否；Codex 只提供观察方向，不能覆盖门槛 |
| 失败处理 | Codex 无法运行、超时、结构不完整或引用未知证据时不发布正式报告 |

Codex 调用使用只读沙箱、临时空目录、结构化输出，并只接收经过精简的冻结研究证据。外部新闻和链接被标记为数据，不得改变任务指令。这个实现是一轮 Codex 对多个职务议题的综合研读，不是 12 个独立模型。以上验证不证明预测能力或交易胜率，也未启用真实下单。
