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

## 核心合同跟进

core 当前工作树已实现标准 waveform bounded binary 合同。第一次按空 trailing profile 读取时，core
以 `binary_transport_trailing_error` 安全拒绝并在恢复写前 poison session；计数证明 payload 后还有一个字节。
随后以精确 `LF` trailing 的 profile 重试，CH1 `DEF` 成功读取 `1000` 个样本，core 也完成 source、mode、format、points 和 window 五字段的恢复与新鲜验证。两次外部 source 步骤均在 `EXIT` 清理中请求 CH1 OFF，并以新的 Source V2 snapshot 确认 CH1/CH2 OFF、`consistent`、`healthy`。

第二次读取的时间轴为 `-25 ms` 到 `24.95 ms`、采样间隔 `50 µs`，但波形摘要约为 `5.25 mVpp / 8.89 kHz`。该值不符合本轮临时启用的 `1 Vpp / 1 kHz` source，可能涉及前面板 acquisition、探头倍率、通道显示或物理接线状态；本记录不把它作为已知信号的换算或测量准确度证据。

## 后续条件

以新的 session 重做以下验收：

1. 在人工确认 acquisition、探头倍率、通道显示和接线后，重做 CH1 `DEF` 的 `1 kHz / 1 Vpp` 闭环；
2. CH1 payload、X/Y 换算和测量阈值；
3. CH2 单路，再到双路顺序验收；
4. `MAX`、`DMAX` 的单块、总预算和 no-replay 行为。

恢复每一步后都先确认 source 两路 OFF，再继续下一步。
