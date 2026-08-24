# SDG2000X Source V2 A3 实机波形验收

[English](SDG2000X_SOURCE_V2_A3_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 24 日，在一台 `SDG2122X`、固件 `2.01.01.39R7T2` 与一台 RTM2032 上完成了
`source.basic_configure_v2` 的 A3 实机波形验收。验收使用已确认的高阻接线：SDG CH1 → RTM2032 CH1，
SDG CH2 → RTM2032 CH2；两路示波器耦合均读为 `DCL`。

在 CH1／CH2 的 Sine、Square、Ramp、Pulse 四种已声明 Basic 函数上，共完成 8 次示波器采集。所有采集
均在 2 kHz、2 Vpp 工作点进行；方波额外验证了 25% 占空比。每个 plan 的质量门和期望断言均通过，最终独立
V2 快照确认两路均为 Sine／1 kHz／1 Vpp／0 V、Harmonic OFF、输出 OFF。

本记录只证明表中工作点上的 `source.basic_configure_v2` 波形行为，不外推到其它型号、固件、频率、幅度、
负载或未声明字段。它不是 C3 发布签核，也不构成实机故障注入或恢复证据。

## 软件、接线和安全边界

- 核心来源版本：WaveBench `0.8.24` 开发线；Source 合同修订 `R7`。
- 插件：`wavebench-siglent-sdg2000x` `0.8.2`，canonical driver ID 为 `siglent.sdg2000x`。
- 受控配置将 `max_source_vpp` 限制为 5 Vpp；全部 A3 输出为 2 Vpp，低于该限制和已授权的 10 Vpp 上限。
- 每个计划均按 `run check → run verify → run intent → run plan` 执行；未使用 raw SCPI，未修改 `wavebench.toml`。
- 每次开启只涉及一个源通道，持续约 0.3 秒；每次采集后立即关闭该通道。CH1 与 CH2 未同时开启。
- 私有运行记录保留 intent、operation artifact、采集包和报告；资源地址、序列号和原始响应不进入本文件或发行包。

## 工作点与外测结果

所有 capture 均使用 10,000 个样本、约 2 MSa/s 和约 10 个周期。频率质量门为 1.900–2.100 kHz，Vpp
质量门为 1.6–2.4 Vpp；两次方波 capture 另要求占空比为 20%–30%。截图经人工核对，与请求函数一致。

| 源通道 | 请求函数 | 请求值 | 外测 Vpp | 外测频率 | 外测占空比 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| CH1 | Square | 2 kHz、2 Vpp、25% | 2.032 Vpp | 约 2.000 kHz | 25% | 通过 |
| CH1 | Ramp | 2 kHz、2 Vpp | 2.000 Vpp | 约 2.000 kHz | 不适用 | 通过 |
| CH1 | Pulse | 2 kHz、2 Vpp | 2.032 Vpp | 约 2.000 kHz | 40%（观测值） | 通过 |
| CH1 | Sine | 2 kHz、2 Vpp | 2.016 Vpp | 约 2.000 kHz | 不适用 | 通过 |
| CH2 | Ramp | 2 kHz、2 Vpp | 2.016 Vpp | 约 2.001 kHz | 不适用 | 通过 |
| CH2 | Square | 2 kHz、2 Vpp、25% | 2.048 Vpp | 约 2.000 kHz | 25% | 通过 |
| CH2 | Pulse | 2 kHz、2 Vpp | 2.048 Vpp | 约 2.000 kHz | 40%（观测值） | 通过 |
| CH2 | Sine | 2 kHz、2 Vpp | 2.032 Vpp | 约 2.001 kHz | 不适用 | 通过 |

Pulse 的 40% 为当前设备状态下的外测结果，不是当前 Source V2 Basic 的 Pulse duty 配置声明。Square 的
25% 则由 `square_duty_cycle_percent` 请求、独立回读和示波器测量共同确认。Square／Pulse 的波形均值会随占空比变化；
这不等同于 `offset_v` 参数变化。

## 事务与最终状态

三个受控 plan 分别包含 12、20 和 26 个步骤，全部状态为 `ok`。共保存 42 条 Source V2 operation 记录；三条
开始时的 Output OFF 请求已在目标状态，其余请求均完成，未产生 recovery 记录。

三次 plan 结束后重新连接并执行独立 V2 快照，确认：

- CH1：Sine／1 kHz／1 Vpp／0 V、Harmonic OFF、输出 OFF；
- CH2：Sine／1 kHz／1 Vpp／0 V、Harmonic OFF、输出 OFF；
- 每个 Source V2 operation 的 session health 均保持 `healthy`。

scope capture 会改变所选示波器通道的采集、时基、垂直、触发和波形传输设置。RTM2032 当前只提供 `scope status`
的 partial summary，而不提供完整 `scope.snapshot`；本次不声称恢复这些示波器设置。最终读回的 CH1／CH2 耦合均为 `DCL`。

## 未证明的内容

- 未验证其它型号、固件、端接、负载、频率／幅度范围或 CH1／CH2 同时输出。
- `offset_v` 是当前插件的可读安全状态，但不是已开放的 V2 Basic 写字段；本次仅记录其写前与最终回读为 0 V。
- 未人为诱发传输失败、未知写入或写后回读不一致；此类分支只有 A0 故障注入证据。
- 未验证 Harmonic 配置／启用、调制、Sweep、Burst、任意波上传、外部触发或其它高级 capability。
- 验收执行当时尚未生成最终插件 wheel conformance manifest；后续候选 manifest 与发布签核状态单独记录。
