# MSO8104 受控实机验收记录

[English](MSO8104_HARDWARE_ACCEPTANCE_EN.md)

验收日期：2026-08-24 至 2026-08-25

## 范围

本记录覆盖 RIGOL MSO8104 基础身份、输入安全、受控 waveform binary 路径、统计测量 V2、FFT 状态 V2、采集状态 V2、采集运行状态、数字状态 V2 和快照 V2 的首轮验收。不会记录真实资源地址、序列号、原始波形、截图或完整命令日志。

参与设备：

- scope：RIGOL MSO8104，固件 `00.02.02`；
- source：Siglent SDG2122X，固件 `2.01.01.39R7T2`；
- core：WaveBench `0.8.24`；
- transport：LAN/PyVISA，读取重试 `0`。

接线为 SDG CH1 到 MSO CH1、SDG CH2 到 MSO CH2。首轮目标 profile 为 Sine、`1 kHz`、`1 Vpp`、`0 V` offset；本地安全配置进一步限制 `max_source_vpp = 1.0` 和端口电压范围 `-0.6 V` 到 `0.6 V`。

## 安全步骤与结果

1. 先以 Source V2 只读快照读取两路状态。CH1、CH2 均为 Sine、`1 kHz`、`1 Vpp`、`0 V`、High-Z display load、harmonic OFF、output OFF。
2. 以 scope 只读状态读取输入。CH1 返回 `DCL`，CH2 返回 `ACL`，两者均为 WaveBench 高阻安全 token。
3. 对 CH1、CH2 分别请求 `source.output_v2 OFF`，随后以新的只读 Source V2 snapshot 独立确认两路 OFF、snapshot `consistent`、session `healthy`。
4. 分别短时开启 CH1 和 CH2；每次波形事务结束后，外层清理都会请求对应通道 OFF，再以新的只读 snapshot 确认 CH1、CH2 均为 OFF。

最终复核为 CH1 OFF、CH2 OFF、snapshot `consistent`、session `healthy`。本轮没有写入示波器的输入阻抗、时基、触发或 autoscale 设置。

## 已通过的实机证据

- `scope.idn`：严格识别 RIGOL MSO8104；
- `scope.channel_coupling`：CH1=`DCL`、CH2=`ACL`；
- `scope.channel_input_state_v2`：CH1/CH2 均返回 `dc + high_z + 1 MΩ`；
- `scope.measurement_statistics_v2`：`VPP,CHAN1` 与 `VPP,CHAN2` 均返回 6 个有限聚合值，`CNT=1000`；
- `scope.fft_status_v2`：前面板预配置 MATH1 返回 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`；
- `scope.acquisition_status_v2`：当前返回 `NORM + 500 kSa/s + 10 kpts`，average 为 not applicable；
- `scope.acquisition_run_state`：当前 AUTO 保守回报为 acquiring；source 两路 OFF、输入高阻下的 STOP→NORMAL/RUN→STOP 闭环依次确认 stopped、waiting、stopped；
- `scope.digital_status_v2`：D0、D8 均返回显示、标签、所属 POD 范围与 `1.4 V` 阈值，以及共享 `0 s` timing calibration 和 `MEDIUM` size；
- `scope.snapshot_v2`：同次读取 identity 和 13 种授权选件状态；其余 55 个字段明确 unavailable；
- Source V2 双通道读取、OFF 请求和独立 OFF 回读；
- 启用前 safety limit、High-Z display load 和无 active cross-channel relation 的 core preflight。

上述结论只覆盖本记录中的型号、固件、LAN/PyVISA 和受控步骤。

## waveform 受限验收

早期 core `0.8.24` legacy binary 路径曾在 `:WAVeform:DATA?` 后约 `5 s` VISA timeout；同步状态因此为 `unproven`，scope session 按 fail-closed 规则标为 `poisoned`。这条历史结果不作为 payload、频率、Vpp 或恢复成功的证据。

当前 core 工作树实现了标准 waveform bounded binary 合同。空 trailing profile 会以 `binary_transport_trailing_error` 安全拒绝 payload 后的额外字节；使用精确 `LF` trailing 后，core 完成 `source`、`mode`、`format`、`points` 和 `window` 五字段的恢复与新鲜验证。

在确认 SDG CH1 接 MSO CH1、SDG CH2 接 MSO CH2 后，以两路分别短时启用的 `1 kHz / 1 Vpp / 0 V` 信号源进行 `DEF` 读取：

- CH1：返回 `1000` 个样本，时间为 `-2.5 ms` 到 `2.495 ms`、采样间隔 `5 µs`，摘要为 `1.05713 Vpp / 1000 Hz`；
- CH2：返回 `1000` 个样本，时间为 `-2.5 ms` 到 `2.495 ms`、采样间隔 `5 µs`，摘要为 `1.0705 Vpp / 999.167 Hz`。

每次读取后都通过 `EXIT` 清理关闭已启用的 source 通道，并以新的 Source V2 snapshot 确认 CH1、CH2 均为 OFF、`consistent`、`healthy`。

## 停止态 MAX/DMAX 受限验收

在独立进程中，先以只读 public API 复核 source CH1/CH2 为 OFF、`consistent`、`healthy`，scope CH1/CH2 为 `dc + high_z + 1 MΩ`，且 run-state 为 stopped。随后 scope fetch 使用 read-write 配置；source 保持输出关闭。每次 fetch 前再次请求两路 output OFF 并复核，不发送 RUN、STOP、SINGLE、autoscale、时基、垂直、触发或输入设置写入。

bounded `scope.fetch_waveform` 使用 `LF` trailing、no-replay、每响应最多 `250,000` bytes、每操作最多 `4,000,000` bytes、最多 16 次 binary query。MAX/DMAX 在临时 waveform transfer setup 前都要求已观察到 STOP；driver 读取当前 memory depth，并把 `:WAVeform:POINts` 设置为 memory depth、运行时总点数和 16 倍 chunk 上限的最小值。实机当前 memory depth 为 `10,000 pts`；本轮运行时上限设为总计 `20,000 pts`、每块 `2,500 pts`。

- CH1：DMAX 返回 `10,000` 样本；停止态 MAX 返回 `10,000` 样本；
- CH2：DMAX 返回 `10,000` 样本；停止态 MAX 返回 `10,000` 样本。

每次完成后，core 对 `source`、`mode`、`format`、`points`、`window` 五个 transfer 字段执行恢复与 fresh verification；新 scope 会话复核仍为 stopped，新的 Source V2 snapshot 复核 CH1/CH2 均 OFF、`consistent`、`healthy`。这只证明记录型号、固件、LAN/PyVISA、当前 `10 kpts` memory depth 和受限分块下的停止态 MAX/DMAX fetch；不证明运行态 MAX、其他 memory depth、吞吐、timeout、波形准确度或 capture 语义。

## portability V2 只读跟进

在 source 两路 OFF 的只读步骤中，`scope.channel_input_state_v2` 成功读取 CH1、CH2 的独立 coupling、termination 和阻抗。该步骤未写入输入设置。

`scope.cursor_readout_v2` 只接受预配置的全局手动 `TIME/AMPL` 光标，且不移动或重配光标。本次设备返回 `VBA`，driver 在读取任意数值前按预期拒绝；该结果不构成光标读数验收。步骤结束后再次确认 source 两路 OFF、`consistent`、`healthy`。

`scope.measurement_statistics_v2` 使用 `item + sources` selector，不访问旧 slot 接口。分别短时开启 CH1 与 CH2 后，对 `VPP,CHAN1` 和 `VPP,CHAN2` 各发送 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT 6 条只读查询；未发送统计配置、清零、显示或任何示波器写入。

- `VPP,CHAN1`：actual `1.0787 V`、average `0.099304 V`、standard deviation `0.088314 V`、minimum `0.064723 V`、maximum `1.1003 V`、count `1000`；
- `VPP,CHAN2`：actual `1.0705 V`、average `0.095994 V`、standard deviation `0.083057 V`、minimum `0.06554 V`、maximum `1.1142 V`、count `1000`。

该步骤证明 6 个响应字段与数值/整数 count 解析可在记录条件下工作。统计历史由设备既有状态维护，driver 不会重置或重新配置它；因此 average、standard deviation、minimum 和 maximum 不作为统计窗口、信号准确度或跨条件测量结论。每次退出清理均关闭已启用的 source 通道，最终快照确认 CH1、CH2 均 OFF、`consistent`、`healthy`。

`scope.fft_status_v2` 使用前面板已配置的 MATH1，不通过 SCPI 创建、修改或恢复 FFT。先确认 source 两路 OFF、`consistent`、`healthy`，并确认 CH1 为 `dc + high_z + 1 MΩ`；随后只读取 operator、source、window、vertical unit、起始频率和终止频率 6 项。回包为 MATH1 operator `FFT`、source `CHAN1`、window `HANN`、vertical unit `VRMS`、频率范围 `0 Hz` 至 `1 MHz`。本次没有 source 或示波器写入、波形传输、二进制读取、错误队列读取或 FFT 状态恢复动作；结束后的独立 Source V2 snapshot 再次确认 CH1、CH2 均 OFF、`consistent`、`healthy`。

该步骤只证明记录型号、固件、transport 与前面板配置下的 FFT 状态回包和 V2 unavailable 字段边界。`average_complete`、RBW 和 FFT sample rate 仍为 unavailable；不构成 FFT 振幅、频率、频率轴或窗函数效果的准确度结论。

`scope.acquisition_status_v2` 只读取 `:ACQuire:TYPE?`、`:ACQuire:SRATe?` 和 `:ACQuire:MDEPth?`；当前 type 为 NORM，因此不读取 `:ACQuire:AVERages?`。回包为 acquisition type `NORM`、sample rate `500000 Sa/s`、memory depth `10000 pts`；average 分区为 not applicable，run state 和 segmented 分区为 unavailable。该步骤未发送 SINGLE、RUN、STOP、任何 acquisition setter、trigger status、OPC、状态寄存器或错误队列查询，因而没有改变采集或触发状态。验证前后 source 两路均 OFF、`consistent`、`healthy`，CH1 为 `dc + high_z + 1 MΩ`。

该证据只覆盖记录条件下的静态 NORM 采集状态。AVER 配置次数、average completion、run state、segmented 状态和任何 capture 完成条件均未实机验证；尤其不能由 trigger STOP 推导 average complete。

`scope.acquisition_run_state` 单次只读取 `:TRIGger:STATus?`。记录条件下，初始 AUTO 被保守映射为 acquiring；随后在 source 两路 OFF、CH1/CH2 均为 `dc + high_z + 1 MΩ` 的条件下，受管 STOP 返回 stopped，NORMAL/RUN 返回 waiting，最终 STOP 再次返回 stopped。没有读取波形、OPC、状态寄存器或错误队列，也没有改动时基、垂直或采样类型。

Core 将 start、stop 和完成式 SINGLE 绑定为同一 `scope.acquisition_control` capability。使用 public API 的 `start(normal)` 后 `stop` 已在 source 双路 OFF、输入高阻条件下实机返回 active/stopped 的可观察闭环。无信号 SINGLE 试验按预期 fail closed，Core cleanup 与 fresh verification 已实机确认恢复；这只证明失败恢复，不证明采集完成。带 CH1 受限信号的 SINGLE 试验也未形成成功证据：实时安全预检确认正弦、固定频率、High-Z display load、幅度不超过 `1 Vpp` 且端口包络在 `±0.6 V` 内，但首次可观察状态仍为 STOP，未出现既有 Core 所要求的非终态到 STOP 状态迁移。历史 arm/readback 的 VXI-11 EOF 与会话阻塞同样不构成完成证据。两次 source 双路 OFF 的 SINGLE 探测中，`*OPC?` 返回成功后独立 run-state 仍为 waiting，因此它只表示命令处理完成，不能替代触发/完成证据。

[RFC-0009](rfcs/0009-single-mode-readback-terminal-stop.md) 现提议一个更窄的、profile-gated 的 completion proof：`SINGLE` 写入后必须读回 `SING`，随后第一条 trigger-status 才是 `STOP`。本轮没有形成该完整受控 trace；RFC 也尚未由 Core 实现。因此 descriptor 继续不声明 `scope.acquisition_control`，并且该提议不放行 capture。每次 SINGLE 尝试后均以独立新会话确认 source CH1/CH2 OFF、`consistent`、`healthy`，scope stopped 且 CH1/CH2 高阻。

`scope.digital_status_v2` 先只读确认 source 两路 OFF、`consistent`、`healthy`，并确认 CH1/CH2 均为 `dc + high_z + 1 MΩ`。D0 与 D8 的每次调用先查询 LA 模块位；模块存在后，仅查询逐通道 display、label、所属 POD threshold、全局 timing calibration 和 display size，共 6 条文本 query。D0 回包为显示、label `D0`、POD1（D0～D7）、`1.4 V`、`0 s`、`MEDIUM`；D8 对应为显示、label `D8`、POD2（D8～D15）以及相同的共享字段。`position_div`、`label_enabled`、activity、technology 和 hysteresis 均按合同标为 unavailable。该步骤没有发送任何 `:LA:*` setter、波形/二进制、采集/触发、OPC、状态寄存器或错误队列查询，也没有 source 或 scope 写入；结束后的独立 Source V2 snapshot 再次确认 CH1/CH2 均 OFF、`consistent`、`healthy`。

该证据只覆盖记录型号、固件、transport 与 D0/D8 静态状态回包。它不证明数字探头连接、电气阈值准确度、逻辑活动、position 语义、标签显示使能或 digital waveform 编码。

`scope.snapshot_v2` 先确认 source 两路 OFF、`consistent`、`healthy`，并确认 CH1/CH2 均为 `dc + high_z + 1 MΩ`。调用经 core `ScopeService.snapshot_v2()` 的纯读取 profile：一次 `*IDN?` 加上手册列出的 13 种 `:SYSTem:OPTion:STATus? <type>`，共 14 条文本 query。identity 与 options 均来自本次调用；13 项状态明确证明当前安装集合，空 options 不由默认值或缓存构造。返回中 health、channel、timebase、probe、waveform 和 trigger 共 55 个字段按稳定顺序为 unavailable。该步骤没有读取 `*STB?`、`*ESR?`、错误队列、trigger、波形或二进制，也没有 source 或 scope 写入；结束后的独立 Source V2 snapshot 再次确认 CH1/CH2 均 OFF、`consistent`、`healthy`。

该证据只覆盖记录型号、固件、transport 下的 identity 和授权选件状态。它不证明未读取的健康、通道、时基、探头、波形或触发分区，也不构成这些字段的准确度结论。

## 验收范围与后续条件

本记录证明的是当前屏幕 `DEF + LF` 1000 点，以及记录的停止态 `MAX/DMAX + LF` 10000 点路径；均限于记录的型号、固件、transport、memory depth 与步骤。它不构成跨量程、跨时基、跨探头条件的通用 X/Y 换算或测量准确度证明。

`scope.acquisition_control`、运行态 MAX、`SINGLE`、`scope.capture_waveform` 和 `scope.capture_waveforms` 没有获得本轮可发布的实机验收，继续默认拒绝。推进 control 前须先由 Core 接受并实现 [RFC-0009](rfcs/0009-single-mode-readback-terminal-stop.md)，再以低压实机完成 `:SINGle → :TRIGger:SWEep? = SING → :TRIGger:STATus? = STOP`、`WAIT → STOP`、失败恢复与 fresh verification 的独立验收；每一步开始前仍须确认 source 两路 OFF。capture 还需要独立的新鲜性与 13 字段恢复验收。
