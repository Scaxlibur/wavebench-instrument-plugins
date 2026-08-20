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

未测试截图、Autoset、capture、错误队列、sequence 波形和其他未声明能力。

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

## 尚未通过的退出门

- 当前记录 `100000` 点，小于 `MAXPoint=5000000`，因此实机只执行了一次 `DATA?`。多块
  拼接继续只有离线 FakeTransport 证据。
- 为制造长记录，验收脚本在 Stop 状态下尝试了 CN11G 记录的
  `:ACQuire:MMANagement FMDepth`、短格式 `ACQ:MMAN FMD` 和 `:ACQuire:MDEPth 10M`。
  目标固件均保持 `AUTO / 100k`，没有应用设置。脚本没有继续尝试未文档化形式，并恢复了
  `AUTO / 100k`、原时基、水平延迟和运行态。
- USBTMC、其他 SDS800X HD 型号、sequence ON 实机门禁及真正的多块记录仍待补。
- 验收脚本在 Stop 状态下尝试文档化的 `:ACQuire:SEQuence ON`，目标固件回读仍为 OFF，
  因此未进入 sequence-ON driver 门禁。脚本恢复 OFF 和运行态，没有尝试未文档化形式。

## 最终状态

- DG4202 CH1 与测试前一致：ON、SIN、`1 kHz`、`5 Vpp`、`0 V`、FIX、sweep OFF。
- SDS804X HD：运行态、sequence OFF、内存管理 AUTO、深度 `100k`、`500 us/div`，waveform
  transfer 恢复为 `C1 / 0 / 1 / 0 / BYTE / LSB`。
- 真实 IP、序列号、原始波形和完整命令日志只保存在仓库外临时目录，没有进入 Git。
