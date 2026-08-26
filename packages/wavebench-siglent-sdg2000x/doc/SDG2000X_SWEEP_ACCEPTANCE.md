# SDG2000X 扫频协议与波形验收

[English](SDG2000X_SWEEP_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成 Sweep 输出 OFF 协议轮询与 A4 波形验收。LINE、LOG、STEP 和 UP、DOWN、UP_DOWN 均获得实机回读；内部触发的 6 组组合均在 RTM2032 上测得 1–10 kHz 的频率跨度，手动触发也测得单次扫频。

载波为 Sine、2 Vpp、0 V 偏置。最大实测 2.24 Vpp，低于 9 V 停止阈值和 10 Vpp 硬上限。正式轮次的 87 次写入全部完成，未知结果为 0。

现有核心 `SourceSweepProfile` 要求 `steps`、起止保持时间、返回时间、触发斜率和 Marker 等完整字段；当前固件没有回读其中多项，关闭态也只返回 `STATE,OFF`。插件没有填入伪默认值，也没有声明有损 Sweep capability。通用改进方向见 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.7.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH2 → 示波器 CH2，高阻输入。
- 扫频范围：1–10 kHz；时间：0.6 s。
- 载波：Sine、2 Vpp、0 V 偏置。

每组配置前先关闭输出。Harmonic、Modulation、Burst、Combine、Noise Add 与 Coupling 均确认关闭；开启 Sweep 后仅由受管验收脚本直接控制输出。公共 `source.output` 继续按设计拒绝 Sweep ON 状态，不能把本次验收当作已开放产品写能力。

## 协议结果

| 字段或组合 | 当前固件结果 | 验收层级 |
| --- | --- | --- |
| `SWMD` | LINE、LOG、STEP 均回读 | A3 |
| `DIR` | UP、DOWN、UP_DOWN 均回读 | A3 |
| `TRSR` | INT、MAN、EXT 均回读 | A3 |
| `TRMD` | ON/OFF 均回读 | A3；专用触发输出未接线 |
| `EDGE` | EXT 下 RISE/FALL 均回读 | A3；未做外部触发物理验收 |
| `EDGE` | MAN 下不回读 | 不声明支持 |
| `MARK_STATE` / `MARK_FREQ` | Marker ON 不回读 | 不声明支持 |
| `STARTTIME` / `ENDTIME` / `BACKTIME` | 写后不回读 | 不声明支持 |
| `MTRIG` | 单次动作命令已发送且测得扫频 | A4 / T1 |

不回读的字段没有被解释为零或 OFF。EXT Edge 与 Trigger Out 只证明配置响应，不证明端口电气行为。

## 波形结果

每组连续取得 18 个有效波形快照，并对每个快照独立估频。回卷附近的低幅无效快照允许重新采集，但任何实测达到 9 Vpp 都会立即终止。

| 模式 | 方向 | 实测频率范围 | 实测 Vpp |
| --- | --- | ---: | ---: |
| LINE | UP | 1.04–9.43 kHz | 2.16 V |
| LINE | DOWN | 1.87–9.43 kHz | 2.16–2.24 V |
| LOG | UP | 1.07–8.93 kHz | 2.16–2.24 V |
| LOG | DOWN | 1.15–9.62 kHz | 2.16–2.24 V |
| STEP | UP | 0.999–10.00 kHz | 2.16 V |
| LINE | UP_DOWN | 1.23–9.80 kHz | 2.16 V |
| LINE / MAN | UP | 0.997–8.55 kHz | 2.16–2.24 V |

LINE 的频率中位数约为 5.2–6.0 kHz，LOG 约为 2.8–3.6 kHz，符合线性与对数驻留分布不同的预期。STEP/UP 的中位数接近 1 kHz，说明该模式在端点驻留行为上与连续扫频不同；本轮只证明阶跃跨度，不推断未回读的步数。

手动触发轮次在发送一次 `MTRIG` 后测得 0.997–8.55 kHz，随后回到起点等待。该证据属于软件触发 T1，不是外部物理触发 T2。

## Transport 审计与恢复

正式轮次执行：

- 查询：72 次；
- 写请求：87 次；
- 已发送：87 次；
- 已完成：87 次；
- 写结果未知：0 次。

结束后：

- CH1/CH2 均为 OFF；
- 两路 Sweep 均为 OFF；
- CH2 恢复 Sine / 1 kHz / 4 Vpp / 0 V；
- RTM2032 通道、探头、时基与触发快照无漂移，且无过载；
- 独立新会话再次确认两路 OFF；该会话只有 13 次查询、0 次写入。

## 覆盖边界

- EXT 触发输入和专用 Trigger Out 没有接线，不能声明 A5/T2。
- Marker、保持时间和返回时间在当前固件不回读，因此没有伪造核心字段。
- Sweep 关闭态的隐藏参数不可无损快照；验收结束时归一化到明确安全基线，不声称恢复未知隐藏配置。
- 数据只适用于当前 SDG2122X 固件，不外推到 SDG2042X/SDG2082X。
