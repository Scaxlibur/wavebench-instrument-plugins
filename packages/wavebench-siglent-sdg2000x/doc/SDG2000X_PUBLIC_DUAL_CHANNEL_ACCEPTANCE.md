# SDG2000X 公共 Source 接口双通道验收

[English](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，`wavebench-siglent-sdg2000x` 0.8.0 通过 WaveBench 0.8.23 的 `SourceService` 在一台 `SDG2122X` 上完成 CH1/CH2 公共写 capability A4 验收。测试覆盖：

- `source.set_amplitude_vpp`；
- `source.set_frequency`；
- `source.set_function` 的 Sine、Square 与 Ramp；
- `source.set_square_duty_cycle`；
- `source.output`。

两路均覆盖输出 OFF 配置、输出 ON、ON 状态实时改频/改幅和最终恢复。正式轮次执行 23 次写入，全部已发送并完成，未知结果为 0。最高实测 0.80 Vpp，低于 9 V 停止阈值和 10 Vpp 硬上限。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.8.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH1 → 示波器 CH1；信号源 CH2 → 示波器 CH2；两路均为高阻输入。

此前谐波验收按原始状态恢复后，两路 Harmonic 为 ON。首次预检因此被插件的高级模式门禁正确拒绝，没有发送基础配置写入，两路输出保持 OFF。正式轮次在审计计数之外保存并关闭 Harmonic，公共 API 完成后恢复原启用状态。

所有功能调用均经过 descriptor 声明、`SourceService`、`SourceStateGuard`、插件驱动和核心 transport 审计。没有公共 raw SCPI 旁路。

## CH1 结果

| 阶段 | 请求 | RTM2032 结果 |
| --- | --- | --- |
| Square | 1.3 kHz、0.5 Vpp、30% | FFT 栅栏 1.4 kHz、0.64 Vpp、High fraction 28.70% |
| Ramp | 1.3 kHz、0.5 Vpp | FFT 栅栏 1.4 kHz、0.64 Vpp |
| Sine 实时写 | 1.5 kHz、0.6 Vpp | FFT 栅栏 1.6 kHz、0.80 Vpp |

## CH2 结果

| 阶段 | 请求 | RTM2032 结果 |
| --- | --- | --- |
| Square | 1.7 kHz、0.5 Vpp、70% | FFT 栅栏 1.8 kHz、0.72 Vpp、High fraction 69.49% |
| Ramp | 1.7 kHz、0.5 Vpp | FFT 栅栏 1.8 kHz、0.64 Vpp |
| Sine 实时写 | 1.9 kHz、0.6 Vpp | FFT 栅栏 2.0 kHz、0.72 Vpp |

当前 RTM2032 记录的 FFT 间隔为 200 Hz，因此非整数栅栏频率落在相邻中心。本轮频率判据使用 FFT 结果并允许一个栅栏误差。当前量程下，基于原始过零的估计会被 80 mV 量化台阶与噪声污染，未作为验收判据。

## 核心事务证据

正式轮次执行：

- 查询：510 次；
- 写请求：23 次；
- 已发送：23 次；
- 已完成：23 次；
- 写结果未知：0 次；
- 仪器变更写入：23 次。

查询数较高来自每次公共写入的身份、完整状态、安全上下文、回读闭包与核心后置条件验证，不是轮询错误队列。

结束后：

- CH1/CH2 均恢复 Sine / 1 kHz / 4 Vpp / 0 V / OFF；
- 原 Harmonic 启用状态恢复；
- RTM2032 两路通道、探头、时基与触发快照无漂移，且无过载。

## 放行边界

- 三个登记型号 `SDG2042X/SDG2082X/SDG2122X` 均通过相同协议合同和离线模型矩阵；按用户授权，未持有的两个型号按协议放行。
- A4 电气证据只来自当前 SDG2122X 固件，不宣称其它型号已实机校准。
- Noise/DC 仍不是可安全开启的周期波 Vpp 状态；公共输出门禁继续拒绝。
- 高级模式开启时，基础写 capability 按设计拒绝；调用方必须显式结束高级事务，而不是由插件暗中清状态。
