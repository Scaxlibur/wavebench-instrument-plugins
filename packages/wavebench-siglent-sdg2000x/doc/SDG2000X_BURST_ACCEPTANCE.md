# SDG2000X Burst 协议与波形验收

[English](SDG2000X_BURST_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成 Burst 输出 OFF 协议轮询和有限周期 A4 波形验收。5、10、20 个周期的内部触发波包分别测得 5、10、20 个载波周期；2 ms 重复周期测得 1.998 ms；两次手动触发均得到 10-cycle 波包。

载波为 Sine、10 kHz、2 Vpp、0 V 偏置。最大有效波包实测 2.16 Vpp，低于 9 V 停止阈值和 10 Vpp 硬上限。正式轮次的 109 次写入全部完成，未知结果为 0。

`TIME,INF` 虽然能回读，但 INT 与 MAN 两种进入序列都没有形成可重复的连续 10 kHz 载波；5 个刷新记录只测得约 0.24 Vpp 噪声底。因此本轮明确不接受 Infinity 的物理行为，不以协议回读替代 A4。

现有核心 `SourceBurstProfile` 在 GATED、INFINITY、MANUAL、EXTERNAL 及 `enabled=False` 状态下仍要求有限 `cycles`、内部周期、Gate 极性和触发斜率等完整值；这些字段在 SDG 当前模式中并非同时适用。插件没有填入伪默认值，也没有声明有损 Burst capability。通用改进方向见 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.7.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH2 → 示波器 CH2，高阻输入。
- 载波：Sine、10 kHz、2 Vpp、0 V 偏置。

每次配置前先关闭输出；Harmonic、Modulation、Sweep、Combine、Noise Add 与 Coupling 均确认关闭。公共 `source.output` 继续按设计拒绝 Burst ON，物理轮次只由受管验收脚本直接控制输出。

## 协议结果

| 字段或模式 | 当前固件结果 | 验收层级 |
| --- | --- | --- |
| `TIME` | 1、5、10、20 与 INF 均回读 | A3 |
| `STPS` | 0°、90°、359° 均回读 | A3 |
| `DLAY` | 0、100 µs 均回读 | A3；无独立触发参考，不声明绝对延迟 A4 |
| `TRMD` | RISE、FALL、OFF 均回读 | A3；Trigger Out 未接线 |
| `EDGE` | EXT 下 RISE/FALL 均回读 | A3；外部触发输入未接线 |
| `EDGE` | MAN 下不回读 | 不声明支持 |
| `GATE_NCYC,GATE` | POS/NEG 极性均回读 | A3；Gate 输入未接线 |
| `MTRIG` | 两次动作均测得有限波包 | A4 / T1 |
| `TIME,INF` | 可回读；触发源字段随写入顺序不稳定 | 只接受协议存在性 |

从隐藏 `TIME,INF/TRSR,MAN` 状态回到有限内部触发时，必须先写有限 `TIME`，再写 `TRSR,INT`；反向顺序会被固件忽略。该状态依赖证明复合配置不能作为可重试的无序字段集合处理。

## 有限周期波形结果

波包持续时间由解析信号包络取得；载波周期数由活跃段 FFT 主频与持续时间联合计算，避免突发边沿毛刺污染原始过零计数。

| 配置 | 中位持续时间 | 中位载波周期数 | 活跃段主频 | 实测 Vpp |
| --- | ---: | ---: | ---: | ---: |
| 5 cycles / INT | 0.543 ms | 5.0 | 9.20 kHz | 2.08–2.16 V |
| 10 cycles / INT | 1.043 ms | 10.0 | 9.59 kHz | 2.16 V |
| 20 cycles / INT | 2.043 ms | 20.0 | 9.79 kHz | 2.16 V |
| 10 cycles / MAN | 1.039 ms | 10.0 | — | 最大 2.16 V |

5 cycles、2 ms 内部重复周期的单个记录包含 3 个波包，中位起点间隔为 1.998 ms。手动触发连续执行两次，两次均得到独立 10-cycle 波包。

## Infinity 负向结果

进入 INF 前分别在有限状态确认 `TRSR,INT` 与 `TRSR,MAN`；进入 INF 后，目标触发源不再稳定回读。两种序列各采集 5 个刷新记录：

- 有效连续载波记录：0；
- 最大实测：0.24 Vpp；
- 最大 10 kHz 定频分量：约 0.0011 V（INT）和 0.0014 V（MAN）。

该结果只说明当前固件与当前命令序列没有形成预期连续载波，不推断其它型号行为，也不把噪声底当作 Infinity 输出通过。

## Transport 审计与恢复

正式轮次执行：

- 查询：96 次；
- 写请求：109 次；
- 已发送：109 次；
- 已完成：109 次；
- 写结果未知：0 次。

结束后：

- CH1/CH2 均为 OFF；
- Burst 与 Sweep 均为 OFF；
- CH2 恢复 Sine / 1 kHz / 4 Vpp / 0 V；
- RTM2032 通道、探头、时基与触发快照无漂移，且无过载；
- 独立新会话再次确认两路 OFF；该会话只有 13 次查询、0 次写入。

## 覆盖边界

- EXT、Gate 与 Trigger Out 没有物理接线，只完成 A3 回读。
- `DLAY` 和 `STPS` 没有独立触发参考，只完成 A3。
- Infinity 的物理判据未通过，不开放相关产品能力。
- Burst 关闭态隐藏全部配置；结束时归一化到明确安全基线，不声称恢复未知隐藏字段。
- 数据只适用于当前 SDG2122X 固件，不外推到 SDG2042X/SDG2082X。
