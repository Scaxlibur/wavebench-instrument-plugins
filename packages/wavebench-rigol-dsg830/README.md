# WaveBench RIGOL DSG830 插件

[English](README_EN.md)

面向 RIGOL DSG830 射频信号发生器的 WaveBench 可执行仪器插件。DSG800 系列编程手册覆盖
DSG830 和 DSG815；本包首版仅将 DSG830 作为已登记目标型号。

## 当前状态

版本 `0.2.0` 已完成 RF M0 只读迁移、M1 离线 CW 映射、M2 离线输出映射和 M3 内部正弦调制映射：descriptor 使用 `kind="rf_source"`，声明单端口 `rf_out` 的静态范围与 50 Ω dBm 参考，并实现严格的 snapshot parser、`:FREQ`／`:LEV`／`:OUTP ON|OFF` 的单次 driver 映射，以及 AM／FM／PM 的内部 Sine 配置与 readback。

A1 只读证据、A2 受控输出证据和 A3 CW 环回证据均已完成并复核。production descriptor 现在声明 `rf_source.idn`、`rf_source.snapshot`、`rf_source.cw_configure` 和 `rf_source.output`。在 `read_write` session 中，CW 写入要求目标端口明确 OFF 和完整 OFF-only preflight；RF ON/OFF 还要求完整端口 safety 配置、fresh snapshot 与独立 readback。示例配置仍保持 `read_only`，不会默认开放写入。

A2 的本地受控输出 harness、回归测试和不含资源地址的 setup 模板保留在源码 checkout，作为验收协议的回归保护。证据已确认最终 RF OFF；harness 在 production descriptor 已声明 `rf_source.output` 后会拒绝重跑，避免用临时 descriptor 绕过正式 capability。A2 本身不授权 CW，后者由独立 A3 证据提升。

A3 的本地 CW 环回 harness、回归测试和不含资源地址的 setup 模板也保留在源码 checkout。它确认初始 RF OFF、两次 OFF-only CW 写入的独立回读、一次低功率 RF ON/OFF、CH2 的当前缓冲区可见信号和最终 RF OFF；CH2 只用于确认可见信号，频率与功率仍以源端 readback 为准。脱敏证据通过后，`rf_source.cw_configure` 已单独进入 production descriptor。

M3 driver 已实现 `get_rf_modulation_snapshot()` 与 `configure_rf_modulation()` 的离线映射。范围仅为内部 Sine：AM 深度 `0–100 %`、FM 频偏 `0.1 Hz–1 MHz`、PM 相偏 `0–5 rad`，三种模式的内部频率均为 `10 Hz–100 kHz`。Core 在写入前要求 RF OFF、AM／FM／PM 全部关闭、Pulse／Sweep 关闭和无活动 protection condition。FM／PM 的共享选择位会被单独读回：三种模式均关闭时可从另一选择切换到目标类型，写后必须独立确认目标类型、仅目标模式与全局调制开关开启。M3 不打开 RF 输出，也不重试结果不明的写入。

production descriptor 不声明错误队列、调制、Pulse、Sweep、trigger 或任意 SCPI passthrough。`rf_source.cw_configure` 只覆盖已审计的 `rf_out` OFF-only 频率／dBm 功率单字段写入，`rf_source.output` 只覆盖已审计的 `rf_out` ON/OFF；`rf_source.modulation_configure` 仍等待 A4 实机证据，不能因 driver 方法或离线测试而提前声明。其余 capability 继续经过对应的 A4–A5 实机证据门。

## 开发文档

- [DSG830 插件文档入口](doc/README.md)
- [DSG830 功能覆盖里程碑](doc/DSG830_COVERAGE_MILESTONES.md)
- [A2 本地证据 setup 模板](tools/a2_output_evidence.setup.template.toml)
- [A3 本地证据 setup 模板](tools/a3_cw_evidence.setup.template.toml)

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
- 默认测试只使用 fake transport，不会连接硬件。production 的普通 `read_only` 配置不会执行 reset、RF 输出切换、功率／频率设置、触发、调制或扫频；A2/A3 的受控证据已分别开放 safety-gated 输出与 OFF-only CW，普通写入仍须显式 `read_write`、相应 capability 和完整 preflight。
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
