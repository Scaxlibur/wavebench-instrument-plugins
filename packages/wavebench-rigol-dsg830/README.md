# WaveBench RIGOL DSG830 插件

[English](README_EN.md)

面向 RIGOL DSG830 射频信号发生器的 WaveBench 可执行仪器插件。DSG800 系列编程手册覆盖
DSG830 和 DSG815；本包首版仅将 DSG830 作为已登记目标型号。

## 当前状态

版本 `0.2.0` 已完成 RF M0 只读迁移、M1 离线 CW 映射、M2 离线输出映射、M3 内部正弦调制映射、M3-MO 受限调制输出合同，以及 M4 的 Pulse 与 frequency-only Step Sweep 生产子集：descriptor 使用 `kind="rf_source"`，声明单端口 `rf_out` 的静态范围与 50 Ω dBm 参考，并实现严格的 snapshot parser、`:FREQ`／`:LEV`／`:OUTP ON|OFF` 的单次 driver 映射、AM／FM／PM 的内部 Sine 配置与 readback、internal／single Pulse 的 period／width／polarity 配置与读回，以及保持 Sweep disabled 的 Step Sweep profile 映射。

A1 只读证据、A2 受控输出证据、A3 CW 环回证据、A4 调制／Pulse／Step Sweep 证据和 A4-MO 固定调制输出证据均已完成并复核。production descriptor 现在声明 `rf_source.idn`、`rf_source.snapshot`、`rf_source.cw_configure`、`rf_source.output`、`rf_source.modulation_configure`、`rf_source.modulation_disable`、`rf_source.modulated_output_enable`、`rf_source.pulse_configure` 和 `rf_source.sweep_configure`。在 `read_write` session 中，CW、调制、Pulse 与 Step Sweep 配置要求目标端口明确 OFF 和完整 OFF-only preflight；普通 RF ON/OFF 还要求完整端口 safety 配置、fresh snapshot 与独立 readback，且普通 ON 仍要求调制关闭。示例配置仍保持 `read_only`，不会默认开放写入。

A2 的本地受控输出 harness、回归测试和不含资源地址的 setup 模板保留在源码 checkout，作为验收协议的回归保护。证据已确认最终 RF OFF；harness 在 production descriptor 已声明 `rf_source.output` 后会拒绝重跑，避免用临时 descriptor 绕过正式 capability。A2 本身不授权 CW，后者由独立 A3 证据提升。

A3 的本地 CW 环回 harness、回归测试和不含资源地址的 setup 模板也保留在源码 checkout。它确认初始 RF OFF、两次 OFF-only CW 写入的独立回读、一次低功率 RF ON/OFF、CH2 的当前缓冲区可见信号和最终 RF OFF；CH2 只用于确认可见信号，频率与功率仍以源端 readback 为准。脱敏证据通过后，`rf_source.cw_configure` 已单独进入 production descriptor。

M3 driver 已实现状态读取、`get_rf_modulation_snapshot()`、`configure_rf_modulation()` 与 `disable_rf_modulation()` 的离线映射。离线范围仅为内部 Sine：AM 深度 `0–100 %`、FM 频偏 `0.1 Hz–1 MHz`、PM 相偏 `0–5 rad`，三种模式的内部频率均为 `10 Hz–100 kHz`。当前 production descriptor 保持较窄的已验证 profile：AM `0–100 %`、FM `0.1 Hz–1 MHz`、PM 精确 `1.25 rad`，内部频率均为 `10 Hz–100 kHz`。Core 在配置写入前要求 RF OFF、AM／FM／PM 全部关闭、Pulse／Sweep 关闭和无活动 protection condition。FM／PM 的共享选择位会被单独读回：三种模式均关闭时可从另一选择切换到目标类型，写后必须独立确认目标类型、仅目标模式与全局调制开关开启。`disable_rf_modulation()` 只在 RF OFF 且仅目标模式活动时关闭该模式和全局调制；它不是 reset，也不重试结果不明的写入。A4 调制与 A4-MO 清理证据已覆盖该事务，因此 production descriptor 声明 `rf_source.modulation_disable`。

源码 checkout 已提供 A4 的 RF-OFF 调制 evidence harness、fake 回归与不含资源地址的 setup 模板。每次只能验证一个内部 Sine 模式；成功路径在配置读回后关闭同一模式，并在最终状态确认 `rf_out` 与调制均为关闭。显式 `--recover` 只恢复已明确识别的单一活动模式，并写入私有恢复记录。显式 `--diagnose` 保留原始 `read_only` 配置，只读取初始／最终 RF snapshot 与指定模式 profile，并要求 transport audit 为零写。A4 不读取 CH2、不调用 RF 输出控制，恢复或诊断记录均不构成新的 capability 提升证据。AM／FM／PM 的 RF-OFF 序列均已通过；为使 production profile 与 PM 的严格读回证据一致，PM 仅开放 `1.25 rad`。

M3-MO 把调制开启时的 RF 输出定义为独立的 `rf_source.modulated_output_enable`，不会放宽普通 `rf_source.output`。它只接受已经激活、完整 readback 精确匹配的内部 Sine profile，并要求 RF OFF、Pulse／Sweep disabled、protection 清晰、完整端口 safety 配置和明确的 50 Ω 实际端接；成功时只执行一次 RF ON。写入或 readback 不确定时不重试 ON，只可能调用一次既有的受 guard RF OFF recovery。A4-MO 已以 AM `50 %`／`1 kHz`、RF `1 MHz`／`-50 dBm` 通过受控实机验收：CH2 当前 `DEF` 缓冲区观察到信号，CH2 明确为 50 Ω，最终 RF OFF、AM／全局调制关闭且两个 session 健康关闭。scope 不读取或控制 CH1，也不把 LF OUTPUT 解释为调制测量，不推断 dBm、频率或调制深度。production descriptor 因此只声明同一 AM `50 %`／`1 kHz`、最大 `-50 dBm` 的 profile；结束时必须显式 RF OFF，再用 `rf_source.modulation_disable` 清理调制。

M4 Pulse 只覆盖 internal／single 子集。`configure_rf_pulse()` 固定设置 source、mode、period、width 和 polarity，并以 `:PULM:STAT OFF` 收尾；它不调用 RF 输出、后面板 Pulse I/O 或 trigger。源码 checkout 的 `tools/a4_pulse_evidence.py`、fake 回归与无资源 setup 模板已完成受控实机验证：normal／inverted 两种 polarity 都经过一次 RF-OFF／Pulse-OFF 配置、独立读回和最终关闭复核；每次成功路径均为 38 次 query、6 次配置 write。`--diagnose` 保持 `read_only` 且零写；两种模式均不读取 CH1／CH2。证据复核后，`rf_source.pulse_configure` 已进入 production descriptor，historical harness 会拒绝重跑。

M4 frequency-only Step Sweep 仅覆盖固定的 `STEP`／`FWD`／`RAMP`／`LIN` profile。`get_rf_sweep_snapshot()` 查询 type、direction、shape、spacing、起止频率、点数、驻留时间和状态；`configure_rf_sweep()` 只写这些 profile 字段，并以 `:SWE:STAT OFF` 收尾。它不写 `:SWE:EXEC`、任何 trigger、Level Sweep、list、RF 输出或后面板接口命令。Core 在写前和写后都要求 RF 输出、调制、Pulse、Sweep 关闭且无活动 protection，写后独立读回完整 profile。源码 checkout 的 `tools/a4_step_sweep_evidence.py` 与无资源 setup 模板已通过 fake 回归和专项实机验收：`--diagnose` 固定 25 次 query、零 write，显式 `--execute` 的成功路径固定 41 次 query、9 条配置 write。工具不读取 Scope、不调用 RF output、不 arm／fire Sweep；最终独立复核 RF 输出、调制、Pulse、Sweep 关闭且无活动 protection。证据复核后，`rf_source.sweep_configure` 已进入 production descriptor，historical harness 会拒绝重跑。

A5-0 已在离线代码中提供 `get_rf_trigger_snapshot()`：它固定读取 Pulse trigger mode、external trigger edge、external gate polarity、Sweep mode、Sweep period trigger 与 Sweep point trigger，并严格拒绝未知响应。六条命令均为 query；driver 不发送 setter、`*TRG`、`:TRIG:PULS`、`:TRIG:SWE`、`:SWE:EXEC`、`:PULM:OUT` 或 RF 输出写入。该映射只观察逻辑 configuration，`rf_out` 不是物理 trigger／sync connector。

production descriptor 不声明错误队列、`rf_source.trigger_snapshot`、trigger、Sweep execute／fire、Level Sweep、list 或任意 SCPI passthrough。`rf_source.cw_configure` 只覆盖已审计的 `rf_out` OFF-only 频率／dBm 功率单字段写入，`rf_source.output` 只覆盖已审计的 `rf_out` ON/OFF，且普通 ON 仍要求调制关闭；`rf_source.modulation_configure` 只覆盖已验收的 RF-OFF 内部 Sine profile（PM 精确 `1.25 rad`），`rf_source.modulation_disable` 只关闭 RF OFF 时唯一已知活动模式，`rf_source.modulated_output_enable` 只覆盖 AM `50 %`／`1 kHz`、最大 `-50 dBm`，`rf_source.pulse_configure` 只覆盖已验收的 RF-OFF internal／single 配置并保持 Pulse OFF，`rf_source.sweep_configure` 只覆盖已验收的 fixed profile 配置并保持 Sweep disabled；其余 capability 继续经过对应的 A4–A5 实机证据门。

## 开发文档

- [DSG830 插件文档入口](doc/README.md)
- [DSG830 功能覆盖里程碑](doc/DSG830_COVERAGE_MILESTONES.md)
- [A2 本地证据 setup 模板](tools/a2_output_evidence.setup.template.toml)
- [A3 本地证据 setup 模板](tools/a3_cw_evidence.setup.template.toml)
- [A4 本地证据 setup 模板](tools/a4_modulation_evidence.setup.template.toml)
- [A4-MO 本地证据 setup 模板](tools/a4_modulated_output_evidence.setup.template.toml)
- [A4 Pulse 本地证据 setup 模板](tools/a4_pulse_evidence.setup.template.toml)
- [A4 Step Sweep 本地证据 setup 模板](tools/a4_step_sweep_evidence.setup.template.toml)
- [A5-0 trigger configuration 本地诊断 setup 模板](tools/a5_trigger_snapshot_evidence.setup.template.toml)

里程碑明确区分当前种子、离线合同和 A1–A5 实机证据。production descriptor 的 capability 不会因种子代码或 fake transport 测试自动提升。

## 身份与兼容范围

- distribution：`wavebench-rigol-dsg830`
- canonical driver ID：`rigol.dsg830`
- 已登记型号：`DSG830`
- WaveBench：`>=0.8.25,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`
- 手册记载的连接方式：USB、LAN

该插件不声明 alias，也不覆盖 WaveBench 内置驱动。使用时应显式配置 canonical ID `rigol.dsg830`。

## 本地编程手册

厂商原文保存在被忽略的 [`doc/vendor-local/`](doc/vendor-local/README.md) 目录。推荐文件名：

```text
DSG800_ProgrammingGuide_EN.pdf
DSG800_ProgrammingGuide_EN.md
```

官方原文为 [DSG800 ProgrammingGuide V1.0](https://www.rigol.com/intl/dam/global/downloads/brochures/en/program-guide/rf-signal-generators/DSG800_ProgrammingGuide_EN.pdf)。
普源官网将其列为 DSG800 系列的 Programming Guide，页面记录版本 `V1.0`、日期 `2019-09-30`。
手册前言说明该系列包含 DSG830 和 DSG815，且命令说明默认以 DSG830 为例。原始 PDF 和转换稿均不得进入 Git 或发行包。

## 当前配置（只读身份和状态）

以下示例使用 RFC 5737 文档保留地址，并以 `read_only` 权限执行身份查询和状态快照：

```toml
[rf_source]
driver = "rigol.dsg830"
resource = "TCPIP::192.0.2.83::INSTR"
access = "read_only"
```

该 `[rf_source]` 配置用于 production descriptor 的 `rf_source.idn` 与 `rf_source.snapshot`。它不属于普通 source 的 Vpp、channel 或 run plan 工作流。未来能量相关 capability 还要求按 `port_id` 提供完整安全配置和真实端接声明；本包不会从连接器标签推断实际端接。

## 安全边界

- descriptor 导入不创建 transport、不扫描端口、不发送 SCPI。
- factory 只通过 `DriverContext` 打开当前配置的 transport。
- 默认测试只使用 fake transport，不连接真实仪器。
- snapshot 仅发送 `*IDN?`、`:FREQ?`、`:LEV?`、`:OUTP?`、`:MOD:STAT?`、`:PULM:STAT?`、`:SWE:STAT?` 与 `:STAT:QUES:POW:COND?`；A1 已使这条只读路径成为 production capability。
- 默认测试只使用 fake transport，不会连接硬件。production 的普通 `read_only` 配置不会执行 reset、RF 输出切换、功率／频率设置、触发、调制或扫频配置；A2/A3/A4/A4-MO 的受控证据已分别开放 safety-gated 输出、OFF-only CW、RF-OFF 调制及关闭、Pulse、Step Sweep 和固定 profile 调制输出，普通写入仍须显式 `read_write`、相应 capability 和完整 preflight。M3-MO 只接受 AM `50 %`／`1 kHz`、最大 `-50 dBm`，普通 RF ON 仍要求调制关闭。Step Sweep 不包含 execute、arm、fire、trigger、Level Sweep 或 list。
- 实机测试必须单独授权，并先确认资源、固件、终止符、RF 输出状态、安全限制和恢复方式。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dsg830/tests
python -m ruff check packages/wavebench-rigol-dsg830
python -m wavebench plugin package check packages/wavebench-rigol-dsg830
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。正式验收仍使用真实 wheel 和一次性虚拟环境。

## 许可证

本插件采用 [MIT License](LICENSE)。
