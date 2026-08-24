# SDG2000X 输出控制实机验收

[English](SDG2000X_OUTPUT_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，`wavebench-siglent-sdg2000x` 0.3.0 的 `source.output` 在一台 `SDG2122X` 上完成受控实机验收，目标固件为 `2.01.01.39R7T2`。CH1 与 CH2 分别执行一次 ON→示波器采样→OFF；每路信号源会话均只发送一次 ON 写入和一次 OFF 写入，写结果未知计数为 0。

WaveBench 核心安全上限设为 10 Vpp，实际验收保留仪器原有的 1 kHz、4 Vpp、0 V 偏置正弦配置，未发送频率、幅度或波形写入。`RTM2032` 分别在 CH1 与 CH2 上读取 10,000 点波形，实测频率、Vpp 和均值均通过验收门限。验收结束后，独立新会话确认信号源两路均为 OFF；示波器无过载、错误状态健康，通道、探头、时基和触发快照与验收前一致。

## 验收环境

- 插件：`wavebench-siglent-sdg2000x` 0.3.0。
- 核心：WaveBench 0.8.23。
- 信号发生器：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：SDG CH1 → RTM CH1，SDG CH2 → RTM CH2。
- 访问策略：信号源与示波器均为 `read_write`；所有写入仍由 WaveBench capability 与 transport 守卫层约束。
- 安全配置：`safety_limits.max_source_vpp = 10.0`。
- 错误检查：`source.check_errors = false`，因 E05C 编程手册未定义可验证的错误队列查询。
- 资源、序列号、原始波形和临时配置仅保留在本地会话，未进入仓库。

## M3 事务合同

`set_output(channel, enabled, *, check_errors=True) -> SourceStatus` 与主仓库 `SourceDriver` 接口一致。当 `check_errors` 不为 `false` 时，驱动会在任何 I/O 前拒绝操作，不把缺失的 `source.errors` 伪装成成功检查。

输出开启的正常路径为：

1. 验证通道、布尔参数和错误检查策略。
2. 读取完整 `SourceStatus`；只有在 FIX、Sweep OFF、Vpp 幅度和偏置均已知时才允许开启。
3. 由核心 `SourceService` 核对 `max_source_vpp`。
4. 若当前状态已等于目标，直接返回快照，不发送写命令。
5. 仅发送一次 `C<n>:OUTP ON|OFF`，随后通过完整状态查询独立回读，并要求其它通道字段不变。
6. 写入后任何异常都会锁止本会话的后续 ON 写入，并尝试一次安全 OFF 恢复与回读。恢复失败时明确报告输出状态不确定；锁止状态下仍允许紧急 OFF。

descriptor 对手册列出的三个型号声明 `source.output`。fake transport 使用三种型号身份均验证同一命令合同；本次实机结论仍只归属实际连接的 `SDG2122X` 与对应固件。

## 离线门禁

包级测试共 87 项，覆盖以下路径：

- CH1/CH2 的 ON 与 OFF，以及目标状态幂等时的零写入返回。
- 三个已登记型号的 `source.output` 路由。
- 非法通道、非布尔输出值、不受支持的错误检查、Sweep 状态和无法界定 Vpp 的快照，均在写入前拒绝。
- 回读不符、回读失败、非输出字段漂移、写结果歧义、OFF 恢复成功与恢复失败。
- 锁止后的 ON 在零 I/O 条件下拒绝，紧急 OFF 仍可执行。
- WaveBench 核心在 10 Vpp 边界允许开启，10.0001 Vpp 在零写入条件下拒绝。

## 实机前置状态

| 字段 | CH1 | CH2 |
| --- | ---: | ---: |
| 输出 | `OFF` | `OFF` |
| 波形 | `SIN` | `SIN` |
| 频率 | 1 kHz | 1 kHz |
| 幅度 | 4 Vpp | 4 Vpp |
| 偏置 | 0 V | 0 V |
| 频率模式 | `FIX` | `FIX` |
| Sweep | `OFF` | `OFF` |

RTM2032 两路均已启用，为 `DCL` 高阻输入、2 V/div、16 V 全量程、0 V 偏置和无过载状态；时基范围为 5 ms，波形 metadata 为 10,000 点、500 ns 步长。

## 闭环测量

验收门限为频率误差不超过 5%、Vpp 误差不超过 15%、均值与设定偏置之差不超过 0.2 V。

| 信号源通道 | RTM 通道 | 点数 | 实测频率 | 频率误差 | 实测 Vpp | Vpp 误差 | 实测均值 | 结果 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CH1 | CH1 | 10,000 | 1000.500 Hz | 0.0500% | 4.160 V | 4.00% | -0.023 V | 通过 |
| CH2 | CH2 | 10,000 | 998.502 Hz | 0.1498% | 4.080 V | 2.00% | -0.009 V | 通过 |

每个通道的信号源受控会话审计计数相同：

| 计数器 | 每通道结果 |
| --- | ---: |
| Query | 25 |
| Write request | 2 |
| Write transmitted | 2 |
| Write completed | 2 |
| Write outcome unknown | 0 |
| Binary write request | 0 |
| Instrument mutation write | 2 |

每路 RTM2032 波形读取会话执行 6 次查询和 4 次数据传输配置写入，写结果未知计数为 0。该路径未触发 autoscale、单次采集、截图或示波器复位。

## 恢复与范围边界

- 每路波形读取都在同一信号源会话的 `finally` 路径中执行 OFF 并回读确认。
- 每路验收后又使用独立新会话执行安全 OFF 收尾，并读取 CH1/CH2 状态；两路均为 `OFF`。
- RTM2032 收尾快照显示两路均为 `DCL`、2 V/div、16 V 全量程、0 V 偏置、无过载、错误队列非空标志为 false、questionable condition 为 0。通道、探头、时基和触发字段与前置快照完全一致。
- 本轮仅验收 `source.output`。频率、函数、幅度、占空比、Sweep、Burst、trigger 和任意波写入仍未开放。
- 实机验收未故意注入传输失败；歧义写入、回读异常和恢复失败只在 fake transport 中验证。
- `SDG2042X` 与 `SDG2082X` 已按同一手册命令合同放行 `source.output`，但仍需逐台补充实机证据。
