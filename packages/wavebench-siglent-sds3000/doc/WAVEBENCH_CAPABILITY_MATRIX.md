# SDS3000 WaveBench capability 覆盖矩阵

[English](WAVEBENCH_CAPABILITY_MATRIX_EN.md)

## 结论

本矩阵覆盖 WaveBench `0.8.24` 的全部 26 项 `scope` capability。当前插件实现并声明 6 项；其余 20 项均有明确处置，没有创建 WaveBench 不存在的接口，也没有通过 raw SCPI 或任意 VBS 绕过 capability 边界。

机器可读事实源见 [`wavebench-capability-matrix.json`](wavebench-capability-matrix.json)。测试会将其中的 26 项与 WaveBench `CAPABILITY_METHODS` 逐项核对，并要求所有手册锚点都存在于 [`command-catalog.json`](command-catalog.json)。

状态含义：

- `implemented`：代码和离线测试已存在，descriptor 已声明；实机证据级别单独记录。
- `firmware-unverified`：手册存在候选路径，但未证明 SDS3054 固件 `8.4.1` 能满足当前 capability 的完整字段和语义。
- `option-unconfirmed`：依赖尚未确认的硬件、探头或选件，不在 descriptor 中提前声明。
- `core-gap-rfc`：仪器能提供部分信息，但 WaveBench 当前模型要求无法诚实填充的字段；只提出跨厂商 RFC。
- `contract-incompatible`：WaveBench 已有可选合同，但当前设备语义无法诚实满足；保留能准确表达的既有 capability，不为通过验证而冒充新合同。
- `unsafe-quarantined`：候选指令需要外部 hardcopy、仪器文件或其他不可安全恢复的路径，不进入生产接口或自动实机测试。

## 26 项 capability

| Capability | 处置 | 证据 | 当前边界 |
| --- | --- | --- | --- |
| `scope.idn` | `implemented` | 实机通过 | 严格接受 SDS3054 与固件 `8.4.1`；同时兼容仪器实际返回的可选 `*IDN ` 头。 |
| `scope.errors` | `implemented` | 离线通过 | 固定读取 `CMR?`、`EXR?`、`DDR?`；三者是读后清除操作，不伪装成无副作用 health 查询。 |
| `scope.autoscale` | `firmware-unverified` | 仅手册 | `ASET` 会同时改变垂直、时基和触发；未完成固件与恢复边界验收前不声明。 |
| `scope.fetch_waveform` | `implemented` | CH1/CH2 实机通过 | 使用现有 `query_bin_block()`；完整快照并逆序恢复 `CHDR/CFMT/CORD/WFSU`。 |
| `scope.capture_waveform` | `implemented` | 实机通过 | 采用 `STOP → ARM → WAIT → *OPC?`，完成后检查 `TRMD STOP` 并恢复被修改状态。 |
| `scope.capture_waveforms` | `implemented` | 实机通过 | 一次 acquisition 后读取全部请求通道，不逐通道重新触发；1 Vpp、1 kHz 三轮验收通过。 |
| `scope.screenshot` | `unsafe-quarantined` | 手册语义核对 | `SCDP` 把画面发送到当前 hardcopy 设备，`SCDP?` 只返回状态，不能返回当前 capability 所需的 PNG 字节；不通过仪器文件系统或任意 VBS 绕行。 |
| `scope.channel_coupling` | `implemented` | 实机通过 | `D1M/A1M/D50/GND` 映射到 WaveBench 现有耦合语义；`OVL` 失败关闭。 |
| `scope.snapshot` | `core-gap-rfc` | 手册与核心模型评审 | 当前 `ScopeSnapshot` 强制要求完整 health、probe、waveform、edge trigger 等字段；SDS3054 无法在一次只读事务中诚实填满。 |
| `scope.acquisition_status` | `core-gap-rfc` | 手册与核心模型评审 | 当前模型强制要求 average 与 segmented 选件状态；`IsTriggerReady`、`TRMD`、`SEQ` 只能提供其中一部分。 |
| `scope.capture_average` | `firmware-unverified` | 仅手册 | `ClearSweeps` 不是完整平均采集协议；平均模式、完成判定和恢复字段尚无固件证据。 |
| `scope.digital_status` | `option-unconfirmed` | 仅手册 | 机身有数字接口，但数字探头、选件许可和固件 Automation 路径未确认。 |
| `scope.digital_waveform` | `option-unconfirmed` | 仅手册 | Result Interface 描述了数字数组，但不能据此推断当前实机已安装并可安全读取。 |
| `scope.history_timestamps` | `firmware-unverified` | 仅手册 | `SEQ`、History 对象和结果时间属性存在；逐段时间表、字节布局和固件行为尚未验证。 |
| `scope.measurement_statistics` | `firmware-unverified` | 仅手册 | `PAST?` 与结果统计属性存在；配置槽确认、响应解析和读取消耗语义尚未验证。 |
| `scope.math_metadata` | `firmware-unverified` | 仅手册 | Math trace 与结果轴属性存在；不能从 2026 年滚动手册外推到固件 `8.4.1`。 |
| `scope.fft_status` | `firmware-unverified` | 仅手册 | 当前 capability 要求 RBW、sample rate 与平均完成状态；尚无可完整填充这些字段的固件证据。 |
| `scope.reference_metadata` | `firmware-unverified` | 仅手册 | Memory trace 与结果轴属性存在；不创建或覆盖 reference 来制造验收数据。 |
| `scope.cursor_readout` | `firmware-unverified` | 仅手册 | `CRVA?` 可读取已配置光标，但当前响应格式和 WaveBench 字段映射尚未实机确认。 |
| `scope.screenshot_profile` | `unsafe-quarantined` | 手册语义核对 | `SCDP?` 只返回 hardcopy 状态，无法证明 PNG 格式、菜单状态和颜色模式；不通过文件系统或任意 VBS 补造 profile。 |
| `scope.screenshot_v2` | `unsafe-quarantined` | 手册语义核对 | 核心要求 PNG payload、显示状态快照、恢复和独立验证；现有 `SCDP` 路径不满足该事务合同。 |
| `scope.acquisition_run_state` | `firmware-unverified` | 手册与驱动评审 | `TRMD?` 的 `AUTO/NORM/SINGLE` 更接近 trigger mode，只有 `STOP` 能证明停止；无法区分 ready、arming、waiting 和 acquiring。 |
| `scope.acquisition_control` | `firmware-unverified` | 部分实机证据 | 现有 capture 已验证 `STOP → ARM → WAIT → *OPC?`，但未覆盖通用连续开始、停止、单次采集的 typed baseline、失败恢复和独立回读合同。 |
| `scope.trace_metadata` | `firmware-unverified` | 仅模拟通道候选 | `WAVEDESC` 已用于模拟通道波形换算，但尚未实现 `ScopeTraceRef` 与 typed metadata；digital、math 和 reference 也没有完整固件证据。 |
| `scope.fetch_trace` | `firmware-unverified` | 部分传输实机证据 | `CHDR/CFMT/CORD/WFSU` 传输状态已验证，但新合同还要求 trace source/mode、run state、typed baseline 与独立恢复验证，不能把旧 `fetch_waveform` 直接冒充为完整实现。 |
| `scope.error_drain_v1` | `contract-incompatible` | 固定寄存器合同评审 | `CMR?`、`EXR?`、`DDR?` 是三个固定的读后清除寄存器，无法诚实满足单一终止 sentinel、overflow record 和 `query_count == records + 1` 合同；继续保留旧 `scope.errors`。 |

## 与手册 100% 覆盖的关系

本矩阵回答「WaveBench 当前接口能否表达」；[`COMMAND_COVERAGE.md`](COMMAND_COVERAGE.md) 与机器目录回答「手册的每个明确实体如何处置」。两者分母不同：前者是 26 项 capability，后者是 578 个明确手册实体。

因此，100% 覆盖不等于 100% 实机执行。复位、校准、文件、网络、hardcopy、选件激活、关机和任意脚本仍必须隔离；选件缺失、型号不适用、固件未确认和核心模型缺口也必须保留为可审计结论。
