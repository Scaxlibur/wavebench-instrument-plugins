# MSO8104 受控实机验收记录

[English](MSO8104_HARDWARE_ACCEPTANCE_EN.md)

验收日期：2026-08-24 至 2026-08-25

## 范围

本记录覆盖 RIGOL MSO8104 基础身份、输入安全、受控 waveform binary 路径、统计测量 V2 和 FFT 状态 V2 的首轮验收。不会记录真实资源地址、序列号、原始波形、截图或完整命令日志。

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

## portability V2 只读跟进

在 source 两路 OFF 的只读步骤中，`scope.channel_input_state_v2` 成功读取 CH1、CH2 的独立 coupling、termination 和阻抗。该步骤未写入输入设置。

`scope.cursor_readout_v2` 只接受预配置的全局手动 `TIME/AMPL` 光标，且不移动或重配光标。本次设备返回 `VBA`，driver 在读取任意数值前按预期拒绝；该结果不构成光标读数验收。步骤结束后再次确认 source 两路 OFF、`consistent`、`healthy`。

`scope.measurement_statistics_v2` 使用 `item + sources` selector，不访问旧 slot 接口。分别短时开启 CH1 与 CH2 后，对 `VPP,CHAN1` 和 `VPP,CHAN2` 各发送 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT 6 条只读查询；未发送统计配置、清零、显示或任何示波器写入。

- `VPP,CHAN1`：actual `1.0787 V`、average `0.099304 V`、standard deviation `0.088314 V`、minimum `0.064723 V`、maximum `1.1003 V`、count `1000`；
- `VPP,CHAN2`：actual `1.0705 V`、average `0.095994 V`、standard deviation `0.083057 V`、minimum `0.06554 V`、maximum `1.1142 V`、count `1000`。

该步骤证明 6 个响应字段与数值/整数 count 解析可在记录条件下工作。统计历史由设备既有状态维护，driver 不会重置或重新配置它；因此 average、standard deviation、minimum 和 maximum 不作为统计窗口、信号准确度或跨条件测量结论。每次退出清理均关闭已启用的 source 通道，最终快照确认 CH1、CH2 均 OFF、`consistent`、`healthy`。

`scope.fft_status_v2` 使用前面板已配置的 MATH1，不通过 SCPI 创建、修改或恢复 FFT。先确认 source 两路 OFF、`consistent`、`healthy`，并确认 CH1 为 `dc + high_z + 1 MΩ`；随后只读取 operator、source、window、vertical unit、起始频率和终止频率 6 项。回包为 MATH1 operator `FFT`、source `CHAN1`、window `HANN`、vertical unit `VRMS`、频率范围 `0 Hz` 至 `1 MHz`。本次没有 source 或示波器写入、波形传输、二进制读取、错误队列读取或 FFT 状态恢复动作；结束后的独立 Source V2 snapshot 再次确认 CH1、CH2 均 OFF、`consistent`、`healthy`。

该步骤只证明记录型号、固件、transport 与前面板配置下的 FFT 状态回包和 V2 unavailable 字段边界。`average_complete`、RBW 和 FFT sample rate 仍为 unavailable；不构成 FFT 振幅、频率、频率轴或窗函数效果的准确度结论。

## 验收范围与后续条件

本记录证明的是当前屏幕、`DEF + LF`、1000 点、记录的型号/固件/transport 和信号源条件。它不构成跨量程、跨时基、跨探头条件的通用 X/Y 换算或测量准确度证明。

`MAX`、`DMAX`、`SINGLE`、`scope.capture_waveform` 和 `scope.capture_waveforms` 没有获得本轮实机验收，继续默认拒绝。后续如需推进，须先完成相应 bounded profile、采集状态恢复和离线故障合同，再拟定独立的低电压实机步骤；每一步开始前仍须确认 source 两路 OFF。
