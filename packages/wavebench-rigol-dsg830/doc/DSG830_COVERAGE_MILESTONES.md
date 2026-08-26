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
| M1 | 离线完成；A3 已完成 | OFF-only CW 频率／dBm 功率配置、独立 readback 与 production `rf_source.cw_configure`。 |
| M2 | 离线完成；A2 已完成 | RF ON/OFF 单次映射、Core safety preflight、独立 readback 和一次性 OFF recovery；production 已开放 `rf_source.output`。 |
| M3 | 离线完成；A4 受控验证中，尚未通过 | 内部 Sine AM／FM／PM 的固定写入序列、严格 readback 与 Core 配置事务／CLI／run／artifact；按模式关闭仅供本地证据与私有恢复，production capability 仍关闭。 |
| M4 | 未开始 | 已声明的 Pulse 与 frequency-only Step Sweep 子集。 |
| A1–A5 | A1、A2、A3 已完成；A4 尚无合格证据；A5 未开始 | A1 提升只读快照；A2 提升端口级 RF 输出；A3 提升 OFF-only CW。 |

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

A1 已完成并经复核，production descriptor 现在声明 `rf_source.idn` 和 `rf_source.snapshot`。M2 的 A2 受控输出证据已另外完成并提升 `rf_source.output`；M1 的 A3 CW 环回证据也已完成并提升 `rf_source.cw_configure`。M3／M4 capability 仍只能存在于 fake descriptor 或离线 driver 测试中，直到取得各自的实机证据。

## M1：OFF-only CW

已完成已冻结的 `:FREQ`／`:LEV` 映射、一次写入和独立 readback。driver 的每次 CW 调用只发送一条 setter；Core CLI、run step 和脱敏 artifact 已接入。A3 通过后，production descriptor 声明 `rf_source.cw_configure`，因此在 `read_write`、目标 `rf_out` 明确 OFF 且完整 OFF-only preflight 通过时，可对已联网的 DSG830 执行单字段频率或功率配置。越界、活动调制／Pulse／Sweep、protection 异常或缺失安全关键状态的请求仍在写入前拒绝。

A3 的本地 harness 和离线回归已经通过受控实机验收：它在内存中临时加入 CW profile，并确认初始 RF OFF、两次 OFF-only CW 写入的独立回读、低功率 RF ON/OFF、CH2 当前缓冲区的可见信号和最终 RF OFF。脱敏证据已复核，production descriptor 已声明 `rf_source.cw_configure`。该提升不授权调制、Pulse、Sweep、trigger 或任意 SCPI passthrough。

## M2：RF 输出

已完成已冻结的 `:OUTP ON|OFF` 映射、独立 readback 和端口级安全预检。DSG830 driver 的 `set_rf_output()` 每次只发送 `:OUTP ON` 或 `:OUTP OFF`，不查询、不重试、不自行 recovery；Core 负责 transaction、snapshot readback 和 session health。RF ON 必须同时满足完整 safety 配置、端接与 dBm 参考阻抗一致、频率与功率均在范围内、调制／Pulse／Sweep 已关闭、无 blocking protection condition，以及所有必要状态可读。

ON 结果不明、readback 失败或 protection 变化时不重试 ON；只有 session health 允许时，Core 才在受 guard 的预算内最多执行一次同端口 RF OFF recovery 并回读 OFF。RF OFF 不依赖频率、功率、端接或 protection readback；其结果不明时不重试。A2 已通过并经复核，production descriptor 现在声明 `rf_source.output`；随后通过的 A3 单独提升了 M1 的 CW，不提升 M3／M4 capability。

## M3：内部正弦调制

M3 的离线实现已完成，但不属于当前 production capability。范围只包含手册和严格 fake transport 测试共同约束的内部 Sine AM／FM／PM：

| 模式 | 固定 driver 配置 | 值范围 | 内部频率范围 |
| --- | --- | --- | --- |
| AM | `:AM:SOUR INT`、`:AM:WAVE SINE`、`:AM:DEPT`、`:AM:FREQ`、`:AM:STAT ON`、`:MOD:STAT ON` | `0–100 %` | `10 Hz–100 kHz` |
| FM | `:FMPM:TYPE FM`、`:FM:SOUR INT`、`:FM:WAVE SINE`、`:FM:DEV`、`:FM:FREQ`、`:FM:STAT ON`、`:MOD:STAT ON` | `0.1 Hz–1 MHz` | `10 Hz–100 kHz` |
| PM | `:FMPM:TYPE PM`、`:PM:SOUR INT`、`:PM:WAVE SINE`、`:PM:DEV`、`:PM:FREQ`、`:PM:STAT ON`、`:MOD:STAT ON` | `0–5 rad` | `10 Hz–100 kHz` |

`get_rf_modulation_state()` 只读取全局 `:MOD:STAT?`、AM／FM／PM 的 enable 状态和 `:STAT:QUES:MOD:COND?`，用于配置前的安全判断。`get_rf_modulation_snapshot()` 在写后或明确需要 profile 时，再读取目标模式的 source、waveform、数值和内部频率；FM／PM 额外读取 `:FMPM:TYPE?` 并将共享选择位与被查询 profile 分开记录。三种模式均 disabled 时，preflight 可接受与目标不同的当前 FM／PM 选择，因为固定写入会先设置目标类型；postcondition 必须确认目标类型。外部 source、非 Sine waveform、未知状态响应或未知调制 condition 位都失败关闭，不用猜测值继续写入。

Core M3 preflight 要求 `rf_out` 明确 OFF、AM／FM／PM 三种模式均 disabled、Pulse／Sweep disabled 且没有活动 protection condition。driver 只发送每种模式对应的固定 bounded sequence；Core 随后重新读取 RF snapshot 和目标调制 snapshot，确认 RF 仍 OFF、仅目标模式 enabled、全局调制开启、内部 source／Sine waveform／数值／内部频率匹配。写入或 postcondition 结果不明时不重试，session 记为不确定；M3 不隐式打开 RF 输出，也不执行输出 recovery。

`disable_rf_modulation()` 只关闭明确请求的 AM、FM 或 PM 模式及全局调制开关。Core 仅在 RF OFF、Pulse／Sweep disabled、无活动 protection，且状态证明该请求模式是唯一活动模式时允许写入；随后独立回读 RF snapshot 和调制状态。已一致关闭时零写返回；混合、未知或矛盾状态不写入。该能力只用于本地 A4 证据与恢复，不进入 production descriptor。

A4 前 production descriptor 不声明 `rf_source.modulation_configure`。当前 M2 的 RF ON 合同要求调制 disabled，因此即使将来 A4 提升 M3 的配置 capability，也不能据此推导已获准在调制开启时输出 RF；这种输出场景需要单独的安全合同和实机证据。

### A4：受控验证中，尚未取得合格证据

源码 checkout 的 `tools/a4_modulation_evidence.py`、回归测试和
`tools/a4_modulation_evidence.setup.template.toml` 已冻结 A4 的第一段验收范围。它是一次性本地 harness，不进入
wheel 或 sdist；production descriptor 在 A4 前仍不声明调制 capability。

静态预检要求 RF 配置为 `read_only`、读重试关闭、driver／型号／当前 production capability 与已提升边界完全匹配，
并且 setup 只包含 `rf_out`、人工确认的端接、已确认选件、`modulation_kind`、一个匹配的模式值和内部频率。setup 不含资源、
序列号、原始响应或 scope 参数。harness 只在内存中添加 `rf_source.modulation_configure`、`rf_source.modulation_disable` 和完整的内部 Sine profile；
descriptor 不注册、不写回、不提前提升。

带 `--execute` 时，一次运行只验证 AM、FM 或 PM 中的一个模式：初始 RF snapshot 必须确认 RF OFF、调制／Pulse／Sweep
关闭且无活动 protection；Core 读取调制状态、执行一次固定的 mode-specific 配置序列并独立回读，然后执行同一模式的受限关闭事务。最终独立 RF snapshot 必须同时确认 RF OFF 和调制关闭。AM 成功路径固定为 72 次 query、8 次 completed write，FM／PM 为 73 次 query、9 次 completed write；所有 write 都是调制配置或关闭命令。A4 不调用 `set_rf_output()`、不读取 scope、不开启 RF，也不在失败后尝试 output recovery。

带 `--recover` 时，harness 只恢复 setup 指定的一个已知活动模式，或记录已一致关闭的零写结果。它要求同样的 RF-OFF 安全前置条件，以权限 `0600` 创建私有恢复记录；恢复记录不计入 A4 能力提升证据。

任何初始／postcondition／最终 RF OFF 不明或不符、模式／数值／内部频率 readback 不符、未知 write outcome、审计计数偏差、
session 异常或关闭后计数变化均为失败。当前受控验证尚未生成可提升 `rf_source.modulation_configure` 的合格记录；production descriptor 继续关闭调制 capability。即使后续 A4 通过，证据也只证明「RF 始终 OFF 时的一个内部 Sine 调制 profile 被配置、读回并关闭」，不证明 RF 调制输出、CH2 信号、Pulse、Sweep 或 trigger。

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

### A2：已完成的受控 RF 输出验收

受控实机序列已完成并经复核：初始 RF OFF、一次 RF ON、独立 readback、CH1／CH2 的补充 scope 观察、一次 RF OFF
及其独立 readback 均成功。证据记录已确认型号、受限固件 token、选件、端口、实际端接、最终 RF OFF、session 关闭和
guard audit；公开状态不包含资源、序列号、原始响应、命令或波形。CH1／CH2 观察只作补充，不替代类型化 RF readback。

源码 checkout 的 `tools/a2_output_evidence.py` 是一次性的本地 harness，不进入 wheel 或 sdist，也不修改
production descriptor。它要求三份本地输入：只读 RF TOML、只读 scope TOML，以及不含资源地址的 A2 setup TOML。
公开模板为 `tools/a2_output_evidence.setup.template.toml`。setup 的端口固定为 `rf_out`，并明确记录实际端接、
已确认选件、频率范围、低功率上限和 CH1／CH2 观察条件；功率上限必须不高于 `-40 dBm`。

不带 `--execute` 时，harness 只进行静态预检，不建立 transport，也不写入仪器。只有显式传入 `--execute` 和一个
尚不存在的本地 `--output` 文件时，才会为本次操作在内存中创建受限的 `read_write` 配置与仅含
`rf_source.output` 的临时 descriptor。RF 配置必须原本为 `read_only`，读重试必须关闭；scope 配置也必须原本为
`read_only`、关闭错误队列与读重试，且其资源必须与 RF 信号源不同。harness 以 `0600` 创建脱敏 JSON 证据文件，
不创建目录，也不打印资源、完整 IDN、原始响应、SCPI 命令或波形。

主序列为初始 snapshot、一次 RF ON、独立 readback、可选 scope 观察、一次 RF OFF 和独立 readback。初始输出为
ON 或输出状态未知时，A2 仍失败；在 session 健康且尚未开始 RF OFF transaction 的条件下，harness 会请求一次受限的
RF OFF 以降低残留输出风险。RF ON 的结果不明时，Core 负责最多一次授权的 OFF recovery；只有该 recovery 明确回读
OFF，harness 才记录最终 OFF 已确认。RF OFF transaction 已开始后，其结果不明不会由 harness 重试。

scope 观察必须显式传入 `--observe-scope`。它只读取 CH1 和 CH2 的当前 `DEF` 缓冲区，每个通道最多一次，不执行
`SINGle`、触发或自动量程。CH2 的 50 Ω 输入必须由 setup 中的 `allow_ch2_50ohm = true` 单独确认；scope fetch
可能改变通道显示和波形传输字段，harness 会将这些未恢复字段写入证据。CH2 在高频下未观察到波形、以及 CH1 的
低频辅助观察，都只产生 warning，不替代 RF 的类型化 readback 和最终 OFF 判定，也不证明 RF 与低频输出之间存在控制关联。

证据状态为 `passed`、最终 RF OFF 已确认且脱敏证据经人工复核后，`rf_source.output` 已加入 production descriptor。
该 historical harness 现在会以 `production_output_gate_changed` 拒绝重跑；普通输出操作必须使用 production descriptor、
`read_write` access 与完整端口 safety 配置。

### A3：已完成的 CW 环回验收

源码 checkout 现提供 `tools/a3_cw_evidence.py`、回归测试与不含资源地址的
`tools/a3_cw_evidence.setup.template.toml`。它只用于取得 A3 的受控证据，不进入 wheel 或 sdist。A3 已通过并经复核；
production descriptor 现在声明 `rf_source.cw_configure`，historical harness 会以 `production_cw_gate_changed` 拒绝重跑。

A3 的静态预检要求 RF 与 scope 配置各自保持 `read_only`、关闭读重试，且两个资源不同；执行阶段才在内存中生成带有
精确频点、功率上限和实际端接的 `read_write` 安全配置。setup 中的功率不得高于 `-40 dBm`，模板使用更低的值。成功路径
仅允许：初始 snapshot、一次频率写入及独立回读、一次功率写入及独立回读、一次 RF ON 及独立回读、一次 CH2 当前 `DEF`
缓冲区读取、一次 RF OFF 及独立回读。证据 audit 会检查成功路径的写入数量、查询数量、无结果不明写入和关闭状态。

CH2 的 50 Ω 输入由 setup 的 `allow_ch2_50ohm = true` 单独确认。CH2 只回答「是否有可见信号」；频率和 dBm 功率的主证据
来自 RF 信号源的类型化独立 readback，不进行 dBm 与 Vpp 换算，也不以 scope 的频率测量替代源端回读。低频输出接入 CH1 的
实验室接线不属于 `rf_out`，A3 未读取或控制它，也未据此推断 RF 与低频输出的开关关系。

不带 `--execute` 时，harness 只做静态预检，不建立 transport，也不写入仪器。带 `--execute` 时必须指定尚不存在的本地
`--output` 文件；证据以 `0600` 创建，且不保存资源、序列号、完整 IDN、原始响应、命令或波形。本次通过记录确认了两项
CW 源端回读、CH2 可见信号、4 次完成写入、72 次查询、健康关闭和最终 RF OFF；频率和功率保留为 setup 指定的测试值。
任一 CW 写入、CH2 可见信号或最终 RF OFF 条件失败时，A3 不通过且不得提升 capability。
