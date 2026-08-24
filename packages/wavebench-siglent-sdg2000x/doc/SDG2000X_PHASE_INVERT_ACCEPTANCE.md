# SDG2000X 相位模式、等相位与反相验收

[English](SDG2000X_PHASE_INVERT_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成 `MODE`、`EQPHASE` 与双通道 `INVT` 验收。两路 1 kHz、0.5 Vpp 正弦在 `PHASE-LOCKED` 模式执行 `EQPHASE` 后，相差 -0.27°；反相 CH2 后相差 179.54°，反相 CH1 后相差 179.90°。最大实测 0.72 Vpp，低于 9 V 停止阈值和 10 Vpp 硬上限。

正式轮次的 44 次写入全部完成，未知结果为 0。结束后两路输出均为 OFF，反相状态和原始相位模式均恢复。

实机还确认当前固件使用 `MODE PHASE-LOCKED`，查询也返回带连字符的 `MODE PHASE-LOCKED`。编程手册 E05C 写作 `PHASELOCKED`；不带连字符的设置在样机上被静默忽略。

当前核心 `SourceChannelProfile` 虽含输出极性，却同时强制要求 Noise 比例、Sync 极性、Marker、Modulation 类型和 Pulse hold 等本机无法权威查询的字段。插件不能为了发布 Invert 而伪造其余字段，因此不声明该整体 profile。通用拆分方案见 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.8.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH1 → 示波器 CH1；信号源 CH2 → 示波器 CH2；两路均为高阻输入。
- 基准：两路 Sine、1 kHz、0.5 Vpp、0 V 偏置、0°。

两路 Harmonic、Modulation、Sweep、Burst、Combine、Noise Add 与 Coupling 均关闭。示波器先执行一次共同的 `SINGle`，再在冻结的同一 acquisition 中读取 CH1/CH2，最后恢复 `RUN`，避免顺序采集产生伪相位差。

## 协议差异

| 操作 | 样机结果 |
| --- | --- |
| `MODE?` | `MODE PHASE-LOCKED` 或 `MODE INDEPENDENT` |
| `MODE INDEPENDENT` | 接受并回读 |
| `MODE PHASELOCKED` | 静默忽略 |
| `MODE PHASE-LOCKED` | 接受并回读 |
| `C1:INVT ON/OFF` | 接受并严格回读 |
| `C2:INVT ON/OFF` | 接受并严格回读 |
| `EQPHASE` | 动作命令，无独立查询；由双通道波形证明 |

调试轮次曾因手册 token 被静默忽略而把相位模式暂留为 `INDEPENDENT`。两路输出在此期间始终 OFF；随后使用带连字符 token 显式恢复为最初观察到的 `PHASE-LOCKED`，独立回读确认后重新执行完整正式轮次。正式轮次的原始模式和最终模式均为 `PHASE-LOCKED`。

## 波形结果

每路以 1 kHz 正弦/余弦正交基拟合相位与幅度，并计算 CH2−CH1 的归一化相差。

| 状态 | CH2−CH1 相差 | CH1 拟合 Vpp | CH2 拟合 Vpp | 最大轨迹 Vpp |
| --- | ---: | ---: | ---: | ---: |
| `EQPHASE` 后，两路正常 | -0.27° | 0.4986 V | 0.5027 V | 0.72 V |
| CH2 `INVT ON` | 179.54° | 0.5007 V | 0.5025 V | 0.72 V |
| CH1 `INVT ON` | 179.90° | 0.5019 V | 0.5046 V | 0.72 V |

相位判据分别为等相位绝对差不超过 20°、反相绝对差不小于 150°；实测结果远离判据边界。

## Transport 审计与恢复

正式轮次执行：

- 查询：24 次；
- 写请求：44 次；
- 已发送：44 次；
- 已完成：44 次；
- 写结果未知：0 次。

结束后：

- CH1/CH2 输出均为 OFF；
- 两路恢复 Sine / 1 kHz / 4 Vpp / 0 V；
- 原 Invert、Harmonic 启用状态与 `PHASE-LOCKED` 模式恢复；
- RTM2032 两路通道、探头、时基与触发快照无漂移，且无过载。

## 覆盖边界

- `EQPHASE` 是不可查询的动作，只能通过同次双通道采集证明结果。
- `INVT` 已覆盖双通道协议和 A4 相位翻转；未把它与调制、扫频、突发或 Combine 组合。
- `INDEPENDENT` 只完成设置/回读 A3，不以短时相位漂移作为其语义证明。
- 实机证据只适用于当前 SDG2122X 固件。
