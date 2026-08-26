# DSG830 功能覆盖里程碑

[English](DSG830_COVERAGE_MILESTONES_EN.md) · [文档入口](README.md)

本文记录 `wavebench-rigol-dsg830` 的型号级交付边界。它与 Core 中的「RF 信号源领域设计」和「RF 信号源开发里程碑」一起使用；本文件不将手册、fake transport 或种子代码写成已可控制真实仪器的能力。独立插件 checkout 应以包内状态和匹配的 Core checkout／版本范围为准；正式 wheel 验收还需要已发布的 Core 版本。

## 目标型号与证据规则

- 已登记型号只有 `DSG830`。DSG800 系列手册覆盖 DSG830 和 DSG815，不自动构成 DSG815 兼容声明。
- `0.1.0` 是历史 `kind="source"`、`source.idn` 过渡种子；当前 `0.2.0` 已迁移为 `kind="rf_source"`。A1 完成后，production descriptor 声明 `rf_source.idn` 和 `rf_source.snapshot`。
- 离线通过只证明 parser、SCPI 映射、fake transport 和包装边界；不能提升 production descriptor capability。
- 生产 capability 必须按 A1–A5 单项提升，并记录型号、固件、选件、端口、端接和最终 RF OFF 状态。
- vendor-local、真实资源、序列号、原始响应、波形、截图和实验日志不得进入公开文档或制品。

## 状态总览

| 阶段 | 状态 | 范围 |
| --- | --- | --- |
| Seed | 离线完成 | `*IDN?`、无 I/O descriptor、包装测试、唯一 entry point 和 vendor-local 排除。 |
| M0 | 离线完成；A1 已完成 | `rf_source`、`rf_out` topology、严格 snapshot parser 与生产只读状态查询。 |
| M1 | 离线完成 | OFF-only CW 频率／dBm 功率配置与独立 readback；production capability 仍关闭。 |
| M2 | 离线进行中 | RF ON/OFF 单次映射、Core safety preflight、独立 readback 和一次性 OFF recovery；production capability 仍关闭。 |
| M3 | 未开始 | 已声明的内部 Sine AM／FM／PM 子集。 |
| M4 | 未开始 | 已声明的 Pulse 与 frequency-only Step Sweep 子集。 |
| A1–A5 | A1 已完成；A2–A5 未开始 | A1 为只读快照证据；其余为独立授权的受控实机证据。 |

## Seed：历史包边界

已完成内容：

- distribution、许可证、唯一 `wavebench.instruments` entry point 与 WaveBench `0.8.24` 种子依赖；
- `rigol.dsg830`、`DSG830`、PyVISA、USB／TCPIP resource scheme 元数据；
- `*IDN?` 和 `close()` 的 fake transport 测试；
- descriptor 导入零 I/O、vendor-local 排除和包装检查。

Seed 不包含错误队列、snapshot、频率、功率、RF 输出、调制、Pulse、Sweep、trigger 或任意 SCPI passthrough。当前 `[source]` 配置示例只用于这个历史身份查询种子，不能进入普通 source 的 Vpp、channel 或 run plan 工作流。

## M0：RF 只读迁移

前置条件已满足：Core `0.8.25` 开发线包含 `rf_source` kind、descriptor extension、capability registry、`[rf_source]`、只读 Service／CLI／doctor 和 `rf_source.status` run 路径。该开发线尚未创建独立发布 tag。

插件交付：

- 已将 `kind`、capability 和配置字段迁移为 `rf_source` 名称空间；
- 已声明单端口 `rf_out`、`9 kHz–3 GHz`、`-110 dBm–20 dBm` 与 50 Ω dBm 参考；连接器标签不等于实际端接；
- 已为 `*IDN?`、`:FREQ?`、`:LEV?`、`:OUTP?`、`:MOD:STAT?`、`:PULM:STAT?`、`:SWE:STAT?` 与 `:STAT:QUES:POW:COND?` 实现严格 snapshot parser；
- 已覆盖每条 query、正常值、未知值、格式异常和 protection 位映射的 fake transport 测试；
- 已将 wheel 的 `Requires-Dist: wavebench` 与 descriptor 版本门同步为 `>=0.8.25,<0.9`。

A1 已完成并经复核，production descriptor 现在声明 `rf_source.idn` 和 `rf_source.snapshot`。后续 M1–M4 capability 仍只能存在于 fake descriptor 或离线 driver 测试中，直到取得各自的实机证据。

## M1：OFF-only CW

已完成已冻结的 `:FREQ`／`:LEV` 映射、一次写入和独立 readback。driver 的离线映射每次只发送一条 setter；Core CLI、run step 和脱敏 artifact 已接入，但 production descriptor 仍缺 `rf_source.cw_configure`，因此不能对真实 DSG830 执行。Core 必须先确认目标 `rf_out` 为 OFF，并拒绝越界、活动调制／Pulse／Sweep、protection 异常或缺失安全关键状态的请求。离线 fake／guarded transport 验收不提升 production capability。

M1 不开放 production CW capability。A3 的频率与 dBm 功率环回证据通过后，才可声明 `rf_source.cw_configure`。

## M2：RF 输出

已开始实现已冻结的 `:OUTP ON|OFF` 映射、独立 readback 和端口级安全预检。DSG830 driver 的 `set_rf_output()` 每次只发送 `:OUTP ON` 或 `:OUTP OFF`，不查询、不重试、不自行 recovery；Core 负责 transaction、snapshot readback 和 session health。RF ON 必须同时满足完整 safety 配置、端接与 dBm 参考阻抗一致、频率与功率均在范围内、调制／Pulse／Sweep 已关闭、无 blocking protection condition，以及所有必要状态可读。

ON 结果不明、readback 失败或 protection 变化时不重试 ON；只有 session health 允许时，Core 才在受 guard 的预算内最多执行一次同端口 RF OFF recovery 并回读 OFF。RF OFF 不依赖频率、功率、端接或 protection readback；其结果不明时不重试。A2 通过前，production descriptor 不声明 `rf_source.output`。

## M3：调制

只评审可由手册与离线测试共同约束的内部 Sine AM／FM／PM 子集。输出未 OFF、profile 不匹配或 postcondition 不一致时必须零写拒绝。A4 前不对 production descriptor 声明调制 capability。

## M4：Pulse 与 Step Sweep

只评审已声明的 Pulse 与 frequency-only Step Sweep 子集。外部 trigger、后面板辅助输出、参考时钟、同步和设备私有模式都不从手册名称推导通用 capability。fake descriptor 可以用于 trigger／fire 事务测试；production capability 要等待 A4 或 A5 的对应证据。

## A1–A5 实机证据

| 证据 | 最小范围 | 允许提升的 capability |
| --- | --- | --- |
| A1 | 只读 snapshot 与 parser 语义 | `rf_source.snapshot` |
| A2 | RF OFF/ON、独立 readback、最终 OFF | `rf_source.output` |
| A3 | CW 环回、频率与 dBm 功率 | `rf_source.cw_configure` |
| A4 | 调制、Pulse、Step Sweep | 对应 M3／M4 capability |
| A5 | 外部 trigger 或同步接线 | trigger／fire／同步相关 capability |

每项实机验收都需要单独授权。写入前后必须记录可公开的脱敏证据、输出状态和恢复结果；无法确认最终 RF OFF 时，验收失败且不能提升 capability。

### A1：已完成的本包只读验收

A1 已使用一次性、非 production 的本地 evidence harness 完成并经复核；不能临时修改 descriptor，也不能用
`rf-source status` 绕过当时的 `rf_source.snapshot` 门禁。harness 在隔离 TOML 副本的 `[rf_source]` 设置
`access = "read_only"` 时，通过受 guard 的单一 session 查询 `*IDN?`、`:FREQ?`、`:LEV?`、
`:OUTP?`、`:MOD:STAT?`、`:PULM:STAT?`、`:SWE:STAT?` 和 `:STAT:QUES:POW:COND?`。不允许重试、
错误队列、RF 输出切换、任意 setter 或 trigger。harness 自身不执行网络发现；如需发现资源，只能在验收前以有界、单独授权的流程完成，再经人工复核写入隔离 TOML，且发现结果不进入证据。

验收成功必须同时证明 parser 成功、`rf_out` 明确为 OFF、session 正常关闭、guard audit 为
`read_only` 且所有写计数为零。证据只保存脱敏的类型化 snapshot 和 audit 摘要；不得保存资源、序列号、
完整 IDN、原始响应或命令日志。任何未知／ON 输出、解析异常或 session 异常都不提升 capability，也不在
只读流程中尝试自动 RF OFF。

隔离 TOML 还必须包含仅供 harness 使用的 `[a1_evidence]` 表：`port_id` 固定为 `rf_out`，
`actual_termination_ohm` 必须是人工确认的有限正数，`installed_options` 必须是已确认、排序且无重复的
安全选件标识列表；确认没有选件时也要显式写入空列表。harness 从同一次 `*IDN?` 响应中提取受限的
固件 token，不增加查询；选件、端接或两个运行时 distribution 版本元数据缺失时会在建立 transport 前
失败，固件不可用则使查询后的证据失败。该表不能从连接器标签、scope coupling 或型号名称推导实际端接。

本地源码 checkout 保留 `tools/a1_snapshot_evidence.py`，它不进入 wheel 或 sdist，用于保留当时的只读协议与回归测试。A1 提升后，脚本会因 production descriptor 已声明 snapshot 而以 `production_snapshot_gate_changed` 拒绝重跑；它不是当前状态查询入口。输出路径必须是尚不存在的本地文件。脚本不会创建目录、不会写入配置，也不会打印资源、完整 IDN、原始响应或命令日志。
