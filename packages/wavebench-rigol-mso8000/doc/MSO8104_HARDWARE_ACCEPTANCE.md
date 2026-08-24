# MSO8104 受控实机验收记录

[English](MSO8104_HARDWARE_ACCEPTANCE_EN.md)

验收日期：2026-08-24

## 范围

本记录只覆盖 RIGOL MSO8104 基础身份、输入安全和受控 waveform binary 路径的首轮验收。不会记录真实资源地址、序列号、原始波形、截图或完整命令日志。

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
4. 仅短时开启 CH1；CH2 始终保持 OFF。无论波形事务结果如何，外层清理都会依次请求 CH1 OFF、CH2 OFF，再以新的只读 snapshot 确认最终状态。

最终复核为 CH1 OFF、CH2 OFF、snapshot `consistent`、session `healthy`。本轮没有写入示波器的输入阻抗、时基、触发或 autoscale 设置。

## 已通过的实机证据

- `scope.idn`：严格识别 RIGOL MSO8104；
- `scope.channel_coupling`：CH1=`DCL`、CH2=`ACL`；
- Source V2 双通道读取、OFF 请求和独立 OFF 回读；
- 启用前 safety limit、High-Z display load 和无 active cross-channel relation 的 core preflight。

上述结论只覆盖本记录中的型号、固件、LAN/PyVISA 和受控步骤。

## waveform 阻断结论

CH1 短时开启后，MSO 返回了有效的 10 字段 preamble：BYTE、`1000` 点、有限 X/Y 标定值。`:WAVeform:DATA?` 随后在 core `0.8.24` 的 legacy binary 路径约 `5 s` 后发生 VISA timeout。core 将该读取的同步状态标为 `unproven`，按 fail-closed 规则将 scope session 标为 `poisoned`；后续 waveform transfer restore 写入被正确拒绝。

因此本轮没有接受 payload、频率、Vpp、X/Y 换算或 transfer-state restore 的成功结果，也没有执行 CH2、双通道、MAX、DMAX 或 SINGLE 的实机验收。问题和恢复条件见 [RFC-0008](rfcs/0008-bounded-waveform-block-trailing-contract.md)。

## 后续条件

WaveBench core 提供可声明的 definite-block trailing 和大小合同后，再以新的 session 重做以下验收：

1. CH1 `DEF` 无 trailing block 读取；
2. CH1 payload、`1 kHz`、`1 Vpp` 和 transfer-state restore；
3. CH2 单路，再到双路顺序验收；
4. `MAX`、`DMAX` 的单块、总预算和 no-replay 行为。

恢复每一步后都先确认 source 两路 OFF，再继续下一步。
