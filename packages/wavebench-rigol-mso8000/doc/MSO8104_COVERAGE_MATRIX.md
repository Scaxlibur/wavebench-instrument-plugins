# MSO8104 编程手册功能覆盖矩阵

[English](MSO8104_COVERAGE_MATRIX_EN.md)

实施顺序和共同安全规则见 [MSO8104 功能覆盖里程碑](MSO8104_COVERAGE_MILESTONES.md)。命令出现在本矩阵中不表示插件已经实现，也不表示目标固件已经验证。

## 范围与证据口径

审计输入为 RIGOL MSO8000 中文编程手册 `PGA26006-1110`。手册同时覆盖 MSO8064、MSO8104 与 MSO8204，并主要使用 MSO8204 举例；本插件首轮只声明 MSO8104。

当前证据同时包含离线验证和受控实机验收：

- **手册声明**：命令和返回域来自手册；
- **离线通过**：代码与 FakeTransport/故障注入测试存在；
- **RFC 后跳过**：WaveBench 核心缺少必要的安全接口或公共模型；
- **默认拒绝**：基础插件不开放该高风险命令域；
- **实机通过**：只表示记录的型号、固件、transport 和限定步骤通过，不外推到其他固件、资源、负载或能力；
- **未实机验证**：当前没有对应受控实机结论。

## 功能矩阵

| 功能域 | 手册命令面 | WaveBench 接口 | 当前状态 | 边界与建议 |
| --- | --- | --- | --- | --- |
| 身份 | `*IDN?` | `scope.idn` | 实机通过 | MSO8104 固件 `00.02.02` 经 LAN/PyVISA 严格识别；不外推到其他型号或固件 |
| 错误队列 | `:SYSTem:ERRor[:NEXT]?` | `scope.error_drain_v1` | 实机通过（受限空队列） | 每条消费型读取显式为 `NO_REPLAY`，严格解析 `<integer>,"<message>"`，仅 `0,"No error"` 终止。公开 bounded capture 的前后各完成一次空 drain 并返回 1000 样本；非零记录和 overflow 仅有离线故障注入证据。legacy `scope.errors` 仍不声明 |
| 输入安全 | `:CHANnel<n>:COUPling?`、`:CHANnel<n>:IMPedance?` | `scope.channel_coupling`、`scope.channel_input_state_v2` | 实机通过 | legacy 接口继续返回 core 高阻安全 token；V2 分别返回 coupling、termination 与阻抗。CH1/CH2 的 V2 结果均为 `dc + high_z + 1 MΩ`；核心默认拒绝 50 Ω、GND 与未知组合 |
| 自动设置 | `:SYSTem:AUToscale?`、`:AUToscale` | `scope.autoscale` | 实机通过（固定 `3 s` settle） | 预检系统使能；明确改变垂直、时基和触发且不承诺恢复。对 MSO8104，`wait_opc=true` 不查询 `*OPC?`，写入一次后固定等待 `3 s` 并视为操作完成；写入或等待异常锁存。受控 CH1 `1 Vpp / 1 kHz` probe 随后公开 bounded fetch 返回 1000 样本且幅度有效，最终 source 双路 OFF、scope STOP、CH1/CH2 high_z。该策略不证明内部算法、可见效果或恢复；`wait_opc=false` 无实机完成验收 |
| 完整状态快照 | channel/timebase/probe/waveform/trigger 与部分 health | `scope.snapshot` | RFC 后跳过 | 公共快照强制要求设备无法查询的字段；`*STB?` 还会清零；见 RFC-0005 |
| 状态快照 V2 | `*IDN?`、13 种 `:SYSTem:OPTion:STATus? <type>` | `scope.snapshot_v2` | 实机通过（受限 identity/选件） | 固定 14 条纯文本 query；同次读取 identity 与手册列出的全部授权选件状态，空 options 仅在全部 13 项明确未安装时成立。health、channel、timebase、probe、waveform、trigger 的 55 个字段按稳定顺序 unavailable；不读状态寄存器、错误队列、trigger、波形或二进制 |
| acquisition 基础配置 | type、averages、memory depth、sample rate、run/stop/single | fetch/capture 的既有状态 | M4 离线通过 | capture 沿用既有配置；深度最高 500 Mpts；设置深度会改变采样率 |
| 采集状态（legacy） | averages 与 trigger status | `scope.acquisition_status` | RFC 后跳过 | legacy 模型要求 average-complete 与 segmented 状态，设备没有对应查询；trigger STOP 不替代平均完成；见 RFC-0006 |
| 采集状态 V2 | `:ACQuire:TYPE?`、`:ACQuire:SRATe?`、`:ACQuire:MDEPth?`，AVER 时 `:ACQuire:AVERages?` | `scope.acquisition_status_v2` | 实机通过（受限 NORM） | 固定 3 条纯读取 query；AVER 时第 4 条读取配置次数。当前回包为 `NORM + 500 kSa/s + 10 kpts`；average 在 NORM 下为 not applicable，run state 与 segmented 为 unavailable。受控设置探测对 `AVERages`、`AVER` 及 PEAK/NORM 对照均回读 `NORM`，所以 AVER 分支没有可达性证据；不从 STOP、OPC 或已配置次数推导完成 |
| 采集运行状态 | `:TRIGger:STATus?` | `scope.acquisition_run_state` | 实机通过（受限观察） | 单条文本 query；STOP→stopped、WAIT→waiting、RUN/AUTO→acquiring，TD→unknown。实机从 AUTO 经 STOP 进入 stopped，再经 NORMAL/RUN 观察到 WAIT，最终 STOP；不以状态查询证明 SINGLE 完成 |
| 采集控制 | `:RUN`、`:STOP`、`:SINGle`、`:TRIGger:SWEep?`、`:ACQuire:TYPE?` | `scope.acquisition_control` | 实机通过（受限） | 已声明 `start(normal)`、`stop` 与完成式 SINGLE。SINGLE 后先读回 `SING`；首条 `STOP` 使用受限终态 proof，`WAIT/TD → STOP` 使用状态迁移 proof。`*OPC?` 不参与 completion，只用于 capture 恢复写批次同步；证据仅限记录的 LAN/PyVISA 与低压步骤 |
| 平均采集事务 | global acquisition type 与 averages | `scope.capture_average_v2` | 实机前提失败后跳过 | 当前 Core 已有 V2 合同，但已停止、高阻、1 Vpp 方波的受控 probe 对 `:ACQuire:TYPE AVERages`、`AVER` 及 PEAK/NORM 对照写入同步后均回读 `NORM`，错误队列为 `0,"No error"`。设备当前不能远程进入平均模式；手册另无平均完成位，STOP、OPC 和 preamble count 都不能替代完成证明；见 RFC-0006 |
| 时基与 edge trigger | main offset/scale、MAIN/XY/ROLL、edge settings/status | capture 前提 | 部分离线通过 | capture 只读前提并沿用配置；任意 setter 不开放，完整 snapshot 见 RFC-0005 |
| 当前屏幕波形 | `WAVeform` NORM/BYTE/preamble/data | `scope.fetch_waveform` | 实机通过（受限 `DEF`） | `LF` trailing、`1,000` bytes 和一次 binary query 已实机通过，core 已完成恢复与新鲜验证。记录的 `1 kHz / 1 Vpp / 0 V` 信号源下，CH1 为 `1.05713 Vpp / 1000 Hz`，CH2 为 `1.0705 Vpp / 999.167 Hz` |
| 深存储波形 | MAX/RAW、start/stop 分块 | `scope.fetch_waveform` | 实机通过（受限 stopped MAX/DMAX） | 唯一 bounded profile 限制每响应 `250,000` bytes、每操作 `4,000,000` bytes、16 次 binary query。MAX/DMAX 均须先观察到 STOP，再读取 memory depth 并把 points 收紧为 memory depth、运行时总点数和 16 倍 chunk 的最小值；不发送 RUN/STOP/SINGLE。source 双路 OFF、CH1/CH2 高阻、当前 `10 kpts` memory depth、`20 kpts / 2.5 kpts chunk` 条件下，CH1/CH2 各自的 MAX/DMAX 均返回 `10,000` 样本并完成五字段 restore/fresh verify。运行态 MAX、其他深度、吞吐和 timeout 未验证 |
| 单次与多通道 | `:SINGle`、trigger status、逐源 waveform | `scope.capture_waveform`、`scope.capture_waveforms` | 实机通过（受限 bounded `DEF + BYTE`） | 仅接受已停止、MAIN 时基的 `DEF + BYTE` 基线；capture 必须观察 `WAIT/TD → STOP`，不接受首条 STOP。单通道和双通道各验证每通道 `1,000` 样本；双通道只发送一次 SINGLE、读取两次二进制数据。Core 恢复并新鲜验证 acquisition、trigger、MAIN 时基、四路 display/vertical 与 transfer 共 13 个字段；其他点数、时基、通道组合和 transport 未验证 |
| 数学波形元数据 | `:MATH<n>:DISPlay?`、waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | 实机通过（受限 MATH1） | 已显示 MATH1、MAIN、source 双路 OFF、scope STOP／高阻下，公开调用返回 1000 点、有限轴、8 位 BYTE 元数据，并完成六项 transfer 状态恢复／最终复核；不读取 data、不证明数学内容、其他 operator／槽位轴语义或 FFT 精度 |
| 手动光标读数 | cursor mode/type/source/unit/value/delta queries | `scope.cursor_readout`、`scope.cursor_readout_v2` | 受限离线通过 | V2 使用全局寻址，读取手动 TIME/AMPL 的独立 A/B source、单位与 A/B/差值；不移动光标。当前实机为 VBA，调用在读取数值前拒绝；准确度未实机验证 |
| 截图 | `:SAVE:IMAGe:TYPE?`、`:SAVE:IMAGe:DATA?` | `scope.screenshot_profile`、`scope.screenshot_v2` | 实机通过（受限 BMP24→PNG） | 仅 `png/device/device`；先只读确认 PNG，再以一次 `DEFINITE_BLOCK` 读取。profile 采用单响应／单操作 `8,388,608` bytes、精确 `LF` trailing、零 resynchronization、零状态变更与恢复；不使用 `:DISPlay:DATA?`，不写 TYPE／INVert／COLor／菜单，不创建设备文件。记录固件实际回传无压缩 BMP24，driver 严格验证后在内存中转换为 PNG。公开调用返回 `1024 × 600`、`47,584` bytes 的 PNG，前后错误队列为空且 session healthy；视觉／像素准确度、其他屏幕状态和最大 payload 未验证；见 RFC-0003 |
| 数字通道状态（legacy） | `:SYSTem:MODules?`、`:LA:*?` | `scope.digital_status` | RFC 后跳过 | legacy 模型必填 activity、technology、hysteresis 等设备无法查询的字段；见 RFC-0004 |
| 数字通道状态 V2 | `:SYSTem:MODules?`、`:LA:DIGital:DISPlay?`、`:LA:DIGital:LABel?`、`:LA:POD<n>:THReshold?`、`:LA:TCALibrate?`、`:LA:SIZE?` | `scope.digital_status_v2` | 实机通过（受限 D0/D8 静态状态） | 每次先读 LA 模块；模块缺席时只返回 `shared.module_present=false`，不发 `:LA:*?`。模块存在时固定 6 条文本 query；D0/D8 均返回 displayed、label、对应 POD 范围与 `1.4 V` 阈值、`0 s` timing calibration、`MEDIUM` size。position、label-enabled、activity、technology、hysteresis 均为 unavailable；不读取波形、不推断逻辑活动或数字编码 |
| 数字波形 | D0～D15 waveform source/data | `scope.digital_waveform` | 手册证据不足后跳过 | 公共 bitset 模型可用，但手册未定义 BYTE/WORD 的 LOW/HIGH code，WORD 字节序也不明确 |
| 自动测量与统计 | `:MEASure:STATistic:ITEM? <type>,<item>,<source...>` | `scope.measurement_statistics_v2` | 实机通过（受限 `VPP,CHAN1/CHAN2`） | 只接受显式 item/source；6 条纯读取查询返回 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT，`include_buffer=True` 拒绝。受控实机的 `VPP,CHAN1/CHAN2` 均返回完整数值并有 `CNT=1000`；不写入统计配置、清零或显示。legacy slot 接口继续不声明；其他 item/source、双源/数字源语义和统计准确度未验证 |
| FFT 状态 | `:MATH<n>:OPERator?` 与 `:MATH<n>:FFT:*?` | `scope.fft_status_v2` | 实机通过（受限 MATH1） | 先确认 operator 为 `FFT`，再读取 source、window、vertical unit、起始/终止频率，合计 6 条纯读取 query。前面板 MATH1 实测回包为 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`；前后 source 两路 OFF、`consistent`、`healthy`。average-complete、RBW 与 FFT sample rate 固定 unavailable，不从全局采样率、频率范围或点数推导；不构成 FFT 精度证据，legacy 接口继续不声明 |
| Reference 元数据 | source、vertical scale/offset、label | `scope.reference_metadata` | 手册证据不足后跳过 | waveform source 不接受 REF，无法查询轴、点数与 Y 分辨率 |
| History 时间戳 | record enable/start/play/current/frames | `scope.history_timestamps` | 手册证据不足后跳过 | 没有逐帧 relative/calendar timestamp；帧号不冒充时间戳 |
| DVM/counter | DVM 与 counter 命令族 | 当前无合适 scope capability | RFC 后跳过 | 需要新的类型化公共模型与 Service |
| AWG | `:SOURce*` | scope descriptor 不应私自混入 source API | RFC 后跳过 | 需要解决同一物理资源的多 kind/共享 lease |
| 协议、mask、search、record | 大量选件命令族 | 当前无对应基础接口 | RFC 后跳过 | 选件、状态恢复和结果模型需独立设计 |
| reset、网络、选件安装、文件系统、校准 | 系统与存储命令 | 无 | 默认拒绝 | 不进入普通实验流程 |

## 波形换算合同

首轮 BYTE 波形使用手册定义的 10 字段 preamble：

```text
format,type,points,count,xincrement,xorigin,xreference,yincrement,yorigin,yreference
```

driver 按以下公式生成公共 `WaveformData`：

```text
voltage = (raw - y_origin - y_reference) * y_increment
x_start = x_origin - x_reference * x_increment
x_stop  = x_start + (points - 1) * x_increment
```

payload 必须与点数精确一致；所有轴参数与换算结果必须为有限数。核心 transport 已负责 IEEE/TMC block framing，插件不重复解析 `#N<length>` 头。

## 未实机验证项

- USB 和 GPIB 资源的连接与终止符；
- 错误队列的非零记录、队列顺序和 overflow；
- `*OPC?` 在两次 source 双路 OFF 的 SINGLE 探测中返回成功后仍可读到 WAIT；它不能作为目标采集完成证据；
- 运行态 MAX、其他 memory depth/点数下的 MAX/DMAX 吞吐、分块和 timeout；
- 除记录的 `DEF + LF`、`1 kHz / 1 Vpp / 0 V` 条件外的 X/Y 换算与测量准确度；
- 除受控 `DEF + BYTE` 条件外的 capture 点数、时基、通道组合、transport 和波形准确度；
- 截图视觉／像素准确度、其他屏幕状态、最大 payload，以及 BMP24 以外的设备返回格式；
- RAW chunk 上限、吞吐和 timeout；
- WORD 字节序与有效位宽；
- 快照 V2 中 identity/选件以外的 health、channel、timebase、probe、waveform 与 trigger 字段；
- 数字探头、电气阈值、逻辑活动、数字 waveform 编码和任何测量准确度。
