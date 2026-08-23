# WaveBench SIGLENT SDG2000X 插件

[English](README_EN.md)

面向 SIGLENT SDG2042X、SDG2082X 和 SDG2122X 函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 当前开发基线

版本 `0.8.2` 保留 8 项既有 V1 capability，并新增 `source.snapshot_v2`、`source.basic_configure_v2`、
`source.output_v2` 和 `source.harmonics_disable_v2`。四项均有 A0 离线合同；`SDG2122X` 固件
`2.01.01.39R7T2` 已完成 V2 snapshot 的 A1，以及 Basic、Output 和 Harmonic 关闭正常路径的有限 A2 验收。
A3 已在已确认的高阻 CH1→CH1、CH2→CH2 接线下完成 Basic 的双通道 Sine、Square、Ramp、Pulse 工作点波形验收；
其它型号或固件、实机故障恢复和发布签核仍未完成。C3 仅完成审计准备，不能视为发布完成。完整边界见
[Source V2 A0 离线适配记录](doc/SDG2000X_SOURCE_V2_A0.md)、[Source V2 A1／A2 实机验收](doc/SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE.md)
、[Source V2 A3 实机波形验收](doc/SDG2000X_SOURCE_V2_A3_ACCEPTANCE.md) 和
[Source V2 C3 发布审计准备](doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)。

V1 基础接口仍包括 `source.set_frequency`、`source.set_function`、`source.set_amplitude_vpp`、
`source.set_square_duty_cycle`、`source.output` 和只读 `source.arbitrary_probe`。V2 Basic 当前覆盖
Sine、Square、Ramp、Pulse 的函数、频率、Vpp 和方波占空比；每次只写一个字段，`offset_v` 尚未开放。
Noise/DC 保持输出 OFF 的 V1 配置语义：驱动不把 `STDEV` 或标称值伪装为 Vpp，核心会将无法无损表达的
旧 `set_function` 调用留在 V1 setter。调制、Sweep、Burst、任意波上传和 Counter capability 仍未开放。

`source.harmonics_disable_v2` 只关闭已读到的 Harmonic 状态，不配置或启用 Harmonic。它仅在
`SDG2122X` 固件 `2.01.01.39R7T2` 的 Sine、目标输出 OFF 状态下对 CH1/CH2 生效；已关闭时不发送 MAIN 写入，
已开启时只发送一条 `HARMSTATE,OFF`。核心随后独立回读 Harmonic 与输出状态。其它型号、固件和所有 Harmonic 配置写入继续拒绝。

`SDG2122X` 固件 `2.01.01.39R7T2` 已完成既有 8 项 V1 capability 的实机验收。五项基础写能力均通过核心
`SourceService` 在 CH1/CH2 闭环；Harmonic、调制、Sweep、Burst、Pulse、Noise/DC、TARB、199 项内置任意波、
Combine、相位/反相、跟踪/耦合/复制和辅助全局状态也已按可用接线完成协议或 A4 验收。该证据不外推为新
Source V2 capability 的 A3 结果；后者另见专项 A3 记录。最大实测 4.24 Vpp；最终独立只读会话确认两路 Sine / 1 kHz / 4 Vpp /
OFF，除 Harmonic 按原状态恢复外，其余复合模式关闭，RTM2032 无过载。

## 身份与兼容范围

- distribution：`wavebench-siglent-sdg2000x`
- canonical driver ID：`siglent.sdg2000x`
- 已登记型号：`SDG2042X`、`SDG2082X`、`SDG2122X`
- WaveBench：`>=0.8.24,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件不声明 alias，也不覆盖 WaveBench 内置驱动。安装后必须显式配置 canonical ID `siglent.sdg2000x`。

## 本地编程手册

厂商编程手册保存在被忽略的 [`doc/vendor-local/`](doc/vendor-local/README.md) 目录：

```text
SDG_Series_Programming_Guide_E05C.pdf
```

手册原文件不进入 Git 或发行包。公开的命令覆盖状态见 [SDG2000X 功能覆盖矩阵](doc/SDG2000X_COVERAGE_MATRIX.md)，分阶段开发门见 [SDG2000X 覆盖里程碑](doc/SDG2000X_COVERAGE_MILESTONES.md)。基础公共接口的最终双通道证据见 [公共 Source 接口双通道验收](doc/SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE.md)，其它分域证据列于文末「公开资料」。

## 配置示例

以下片段需合并到已包含 `[connection]` 与 `[scope]` 的有效 `wavebench.toml`。示例使用 RFC 5737 文档保留地址，并以更安全的 `read_only` 状态起步。`source.output` 需要显式改为 `read_write`，同时保留 Vpp 安全上限：

```toml
[source]
driver = "siglent.sdg2000x"
resource = "TCPIP::192.0.2.40::INSTR"
default_channel = 1
check_errors = false
access = "read_only"

[safety_limits]
max_source_vpp = 10.0
```

将 `access` 改为 `read_write` 后才能调用基础 Source 写 capability；保留 `read_only` 时，身份和通道状态仍可查询，写操作会由核心拒绝。`check_errors = false` 表示错误队列尚未形成已认证 capability；驱动不会伪装错误队列检查。

## 安全边界

- descriptor 导入不创建 transport，也不访问仪器。
- factory 只通过 `DriverContext` 打开当前配置的 transport。
- 默认测试只使用 fake transport，不扫描资源、不连接仪器。
- `source.output` 开启前必须读取 FIX、Sweep OFF、Vpp 幅度、偏置和所有已知复合波模式，并由核心检查 `max_source_vpp`。
- `source.set_frequency` 检查型号与当前波形上限；Sweep 自动切回 FIX 只允许在输出 OFF 时执行。
- `source.set_amplitude_vpp` 只接受 2 mVpp 至 10 Vpp，并要求幅度与偏置不越过 ±10 V 包络。
- `source.set_function` 允许四种有界周期波实时切换；Noise/DC 必须在输出 OFF 时配置，且不会绕过输出安全门禁。
- `source.set_square_duty_cycle` 仅适用于 FIX 模式方波；频率相关钳位必须导致回读失败关闭。
- Source V2 的 Basic 和 Output MAIN 各只发送一个已审计写命令，最终状态由核心独立快照回读；合同允许独立通道同时 ON，但该组合尚无 Source V2 实机验收。
- Source V2 Harmonic 关闭只在精确的运行时型号/固件、Sine 和输出 OFF 条件下生效；它不会配置或启用 Harmonic，已关闭时不写入，已开启时最多发送一条 `HARMSTATE,OFF`，随后由核心独立回读 Harmonic 与输出状态。
- Source V2 的 Noise/DC 不猜测 Vpp；无法无损表示的旧 `set_function` 仍调用 V1 setter，输出 ON 继续要求可读最终 Vpp 与 Offset。
- 目标配置只写入一次；任何写后异常都会尝试 OFF 恢复并锁止本会话的全部配置写入。
- 除上述 Harmonic 关闭外，高级命令域即使已有分域实机验收，在核心缺少无损模型时仍不开放写 capability，也不提供 raw SCPI。
- 实机测试必须单独授权，并先确认资源、固件、终止符、输出状态、安全上限和恢复方式。

## 开发验证

```bash
python -m pytest -q packages/wavebench-siglent-sdg2000x/tests
python -m ruff check packages/wavebench-siglent-sdg2000x
python -m wavebench plugin package check packages/wavebench-siglent-sdg2000x
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。正式验收仍使用真实 wheel 和一次性虚拟环境。

## 许可证

本插件采用 [MIT License](LICENSE)。

## 公开资料

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- [SDG2000X 协议审计](doc/SDG2000X_PROTOCOL_AUDIT.md)
- [SDG2000X 只读实机验收](doc/SDG2000X_READONLY_ACCEPTANCE.md)
- [SDG2000X 输出控制实机验收](doc/SDG2000X_OUTPUT_ACCEPTANCE.md)
- [SDG2000X 频率写入实机验收](doc/SDG2000X_FREQUENCY_ACCEPTANCE.md)
- [SDG2000X 基础写入实机验收](doc/SDG2000X_BASIC_WRITE_ACCEPTANCE.md)
- [SDG2000X Source V2 A0 离线适配记录](doc/SDG2000X_SOURCE_V2_A0.md)
- [SDG2000X Source V2 A1／A2 实机验收](doc/SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE.md)
- [SDG2000X Source V2 A3 实机波形验收](doc/SDG2000X_SOURCE_V2_A3_ACCEPTANCE.md)
- [SDG2000X Source V2 C3 发布审计准备](doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)
- [Source V2 能力、状态与复合输出安全 RFC](doc/RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)
- [SDG2000X 谐波协议与频谱验收](doc/SDG2000X_HARMONIC_ACCEPTANCE.md)
- [SDG2000X 调制协议与波形验收](doc/SDG2000X_MODULATION_ACCEPTANCE.md)
- [SDG2000X 扫频协议与波形验收](doc/SDG2000X_SWEEP_ACCEPTANCE.md)
- [SDG2000X Burst 协议与波形验收](doc/SDG2000X_BURST_ACCEPTANCE.md)
- [SDG2000X Pulse 协议与波形验收](doc/SDG2000X_PULSE_ACCEPTANCE.md)
- [SDG2000X 任意波只读探测验收](doc/SDG2000X_ARBITRARY_PROBE_ACCEPTANCE.md)
- [SDG2000X 内置任意波全目录验收](doc/SDG2000X_BUILTIN_ARB_ACCEPTANCE.md)
- [SDG2000X 特殊波形协议与实机验收](doc/SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE.md)
- [SDG2000X 双通道波形合成验收](doc/SDG2000X_COMBINE_ACCEPTANCE.md)
- [SDG2000X 相位模式、等相位与反相验收](doc/SDG2000X_PHASE_INVERT_ACCEPTANCE.md)
- [SDG2000X 通道跟踪、耦合、复制与双通道触发验收](doc/SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE.md)
- [SDG2000X 辅助与全局状态只读验收](doc/SDG2000X_AUXILIARY_READONLY_ACCEPTANCE.md)
- [SDG2000X 公共 Source 接口双通道验收](doc/SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE.md)
