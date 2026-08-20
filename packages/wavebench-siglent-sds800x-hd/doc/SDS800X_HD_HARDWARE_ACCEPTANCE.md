# SDS800X HD 实机验收记录

[English](SDS800X_HD_HARDWARE_ACCEPTANCE_EN.md)

## 验收范围

2026-08-20 使用当前外置插件和 WaveBench `0.8.22`，对一台 SDS804X HD 完成首轮
TCPIP/VXI-11 实机验收。测试连接由一台 DG4202 CH1 同时驱动示波器 CH1 和 CH2；公开
记录不包含仪器 IP、序列号、原始波形或完整 SCPI 日志。

本轮只验收已经声明的能力：

- `scope.idn`
- `scope.channel_coupling`
- Stop、sequence OFF 下的 `scope.fetch_waveform(..., points="dmax", check_errors=False)`
- `scope.capture_waveform` 和一次 acquisition 的 `scope.capture_waveforms`
- 已配置高级测量槽位的 `scope.measurement_statistics`

未测试截图、Autoset、独立采集控制、错误队列和 sequence 波形；`capture_waveform(s)` 已在
本轮完成独立的正向验收，另对 sequence ON 拒绝门禁做了负向验收。

## 仪器与初始状态

| 仪器 | 固件 | 初始状态 |
|---|---|---|
| SIGLENT SDS804X HD | `4.8.12.1.1.6.5` | Trigger `Trig'd`；sequence OFF；`500 us/div`；内存管理 AUTO；深度 `100k` |
| RIGOL DG4202 | `00.01.14` | CH1 ON；SIN；`1 kHz`；`5 Vpp`；`0 V` offset；FIX；sweep OFF；High-Z/INFINITY 负载语义 |

发生器状态在测试前已经满足波形验收要求，因此本轮没有向发生器发送设置或输出写命令。
示波器 CH1–CH4 coupling 均回读为 DC；用于波形验收的 CH1、CH2 为 `1×` 探头系数和
`1 V/div`。

## 身份与门禁结果

- `*IDN?` 四字段格式、厂商、`SDS804X HD` 型号、14 字符 ASCII 序列号和固件字段通过。
  序列号只在本地临时日志中出现，未写入仓库。
- 四通道 coupling 查询均返回 `DC`。
- acquisition 运行时直接调用 `fetch_waveform`，driver 在 `TRIGger:STATus?` 返回
  `Trig'd` 后拒绝。该会话没有 waveform 写命令或 binary query。
- 正式读取前由验收脚本发送文档化的 `:TRIGger:STOP`；driver 本身没有发送采集控制命令。
  读取结束后脚本发送 `:TRIGger:RUN`，仪器恢复到 `Arm`/`Ready`/`Trig'd` 运行状态。
- 使用真实 `WaveBenchConfig` 和 `ScopeService.fetch_waveform(1)` 的受管入口再次读取成功，
  返回核心 `WaveformData` / `WaveformHeader`、`100000` 点和相同采样间隔。该路径包含一次
  identity query、一次 preamble binary query 和一次 data binary query。

## Preamble 实机差异

首轮读取暴露了 CN11G 与目标固件的一个差异。SDS804X HD 的非 sequence preamble 返回：

```text
read_frames = 0
sum_frames = 1
segment = -1
```

初版 parser 错误要求 `segment >= 0`，因此第一次读取在数据传输前失败。`0.3.1` 将门禁
修正为已确认的非 sequence 签名，并继续接受手册使用的 `segment=1` 形式；其他帧组合仍
拒绝。修正后离线测试和实机读取均通过。

本次 WORD preamble 的关键字段为：

| 字段 | 实测值 |
|---|---:|
| Descriptor payload | `346 bytes` |
| `COMM_TYPE` / `COMM_ORDER` | WORD / LSB |
| Points | `100000` |
| Data bytes | `200000` |
| ADC bits | `16` |
| Sample interval | `50.000000584 ns` |
| Horizontal span | 约 `5 ms` |
| `MAXPoint?` | `5000000` |

## CH1 与 CH2 波形结果

两通道读取同一份已停止记录。每个通道返回 `100000` 个有限样本，header 点数一致，时间轴
严格递增。

| 指标 | CH1 | CH2 |
|---|---:|---:|
| FFT 主峰 | `999.999988 Hz` | `999.999988 Hz` |
| 平滑零交叉频率 | `1000.0191 Hz` | `1000.0170 Hz` |
| `1 kHz` 正弦拟合 Vpp | `5.0280 V` | `5.0100 V` |
| 原始 min/max Vpp | `5.1000 V` | `5.0292 V` |
| 平均值 | `-45.2 mV` | `-38.6 mV` |
| `1 kHz` 拟合相关系数 | `0.999932` | `0.999994` |

CH1/CH2 直接相关系数为 `0.999997`；拟合 Vpp 差约 `0.36%`。频率、幅值、时间轴和双通道
一致性均通过本轮门限。

未经平滑的简单零交叉算法会把零点附近的量化和噪声交叉误判成 MHz 级频率。本轮使用 FFT、
101 点平滑零交叉和固定 `1 kHz` 正弦最小二乘拟合交叉复核，不把原始零交叉计数作为验收
依据。

## Transfer 状态恢复

测试预置以下合法状态：

```text
SOURCE=C2, START=10, INTERVAL=2, POINT=1000, WIDTH=WORD, BYTEorder=MSB
```

随后执行两条路径：

1. 正常读取 CH1；
2. 完成 binary transfer 后，在本地 monkeypatch 的转换函数中注入 `RuntimeError`。

两条路径结束后六项状态均逐项恢复到预置值。验收脚本最后又恢复测试前的
`C1 / 0 / 1 / 0 / BYTE / LSB`，并回读确认。异常路径保留原始本地异常，没有被恢复动作
覆盖。

## 真实多块读取

补充验收确认，目标固件在 `AUTO` 触发模式下会静默忽略固定存储深度设置。切换到
`NORMAL` 后，文档化的 `:ACQuire:MMANagement FMDepth` 和 `:ACQuire:MDEPth 10M`
均能通过写后回读。验收脚本临时只保留 CH1，执行一次文档化的强制触发，随后停止采集。

停止记录的实测边界为：

| 项目 | 实测值 |
|---|---:|
| Record points | `10000000` |
| `MAXPoint?` | `5000000` |
| Chunk 1 | `START 0`，`5000000` 点，`10000000 bytes` |
| Chunk 2 | `START 5000000`，`5000000` 点，`10000000 bytes` |
| Result | `10000000` 个样点，header 与拼接长度一致 |

两次真实 `DATA?` 均通过 definite-length block 读取。第二块起点、每块字节数、总样点数和
最终 `WaveformData` 一致，因此多块拼接已不再只有 FakeTransport 证据。

## Sequence ON 拒绝门禁

`AUTO` 触发模式下，即使先停止采集，`:ACQuire:SEQuence ON` 仍会回读为 OFF。切换到
`NORMAL` 后，该命令能回读为 ON；启用 sequence 会重新进入 Arm 状态，因此验收脚本再次
发送 `:TRIGger:STOP`，建立 `Stop + sequence ON` 条件。

此时 `fetch_waveform` 依次完成 identity、trigger status 和 sequence state 查询，随后以
`SDS800X HD waveform reads do not support sequence acquisition` 拒绝。该调用没有发送任何
waveform transfer 写命令或 binary query。测试结束后 sequence、触发模式和运行状态均恢复。

## 测量统计

实机已有 P3 `PKPK / C1` 测量槽位。验收脚本临时将测量模式切到 `ADVanced` 并开启统计，
driver 以零写入读取到：当前值 `5.0375 V`、均值 `5.0370833 V`、最小值 `5.03542 V`、
最大值 `5.03958 V`、标准差 `0.001701 V` 和统计次数 `6`。

历史缓冲验收将最大统计次数临时设为 `16`，取得 `5` 个值；返回的 `Count=5` 与解析值数
一致。读取前已停止 acquisition，读取结束后恢复测量模式 `SIMPlc`、统计 OFF、最大次数 `0`
和原运行态。

## 单次与多通道采集

`scope.capture_waveform(1)` 实机执行一次 SINGLE acquisition，经 Arm 到 Stop 后读取
`100000` 点；原始 min/max Vpp 为 `5.0375 V`。该路径没有调用 `*OPC?`。

`scope.capture_waveforms([1, 2])` 只发送一次 SINGLE 和一次 RUN，随后从同一停止记录读取
CH1、CH2 各 `100000` 点。两通道原始 Vpp 为 `5.0354 V` 和 `5.0375 V`，相关系数为
`0.9999971`；channel start 和 waveform callback 顺序均为 CH1、CH2。完成后触发模式和运行态
恢复到测试前状态。

使用真实 descriptor 和 `ScopeService.capture_waveforms([1, 2], ...)` 的受管入口再次通过，
生成临时 metadata，记录 `triggered_single=true` 和完成通道 `[1, 2]`。临时波形包在验收结束
后删除，没有进入仓库。

## 剩余退出门

- USBTMC 和其他 SDS800X HD 型号仍待补；本轮按计划不扩展这些实机范围。
- sequence 波形解析仍未实现；当前证据只证明非 sequence 读取和 sequence ON 下的安全拒绝。

## 未公开能力的只读探测

- 截图查询返回 `43628` 字节，首 8 字节为 PNG signature，不以 `#` 开头。解析到 IEND 时为
  `43627` 字节，随后还有 1 个尾字节。该结果确认响应不是 IEEE definite block；探测未保存
  图片内容。当前核心 transport 和 screenshot 菜单参数均不足，因此 capability 保持关闭。
- `FUNCtion1?` 至 `FUNCtion4?` 均返回 OFF。未开启或修改数学函数；现有状态不足以构造核心
  `ScopeDerivedWaveformMetadata` 或 `ScopeFftStatus`，math/FFT capability 保持关闭。
- 未发送任何未文档化错误队列命令。`scope.errors` 保持未声明。

上述接口缺口按多个示波器插件的共同需求记录在 `R1 Draft`
[scope 通用扩展接口 RFC](../../../doc/rfcs/WaveBench_scope通用扩展接口RFC.md)，不在本 driver
中增加私有 transport 或厂商专用公共方法；核心预审不会自动改变主仓库。

## 最终状态

- DG4202 CH1 与测试前一致：ON、SIN、`1 kHz`、`5 Vpp`、`0 V`、FIX、sweep OFF。
- SDS804X HD：运行态、sequence OFF、内存管理 AUTO、深度 `100k`、`500 us/div`，waveform
  transfer 恢复为 `C1 / 0 / 1 / 0 / BYTE / LSB`。
- 真实 IP、序列号、原始波形和完整命令日志只保存在仓库外临时目录，没有进入 Git。
