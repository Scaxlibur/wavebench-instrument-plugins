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
| 错误队列 | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC 后跳过 | 查询会消费队首；核心普通文本 query 允许重放 |
| 输入安全 | `:CHANnel<n>:COUPling?`、`:CHANnel<n>:IMPedance?` | `scope.channel_coupling`、`scope.channel_input_state_v2` | 实机通过 | legacy 接口继续返回 core 高阻安全 token；V2 分别返回 coupling、termination 与阻抗。CH1/CH2 的 V2 结果均为 `dc + high_z + 1 MΩ`；核心默认拒绝 50 Ω、GND 与未知组合 |
| 自动设置 | `:SYSTem:AUToscale?`、`:AUToscale` | `scope.autoscale` | 离线通过 | 预检系统使能；明确改变垂直、时基和触发；写入或 OPC 不确定时锁存，效果未实机验证 |
| 完整状态快照 | channel/timebase/probe/waveform/trigger 与部分 health | `scope.snapshot` | RFC 后跳过 | 公共快照强制要求设备无法查询的字段；`*STB?` 还会清零；见 RFC-0005 |
| 状态快照 V2 | `*IDN?`、13 种 `:SYSTem:OPTion:STATus? <type>` | `scope.snapshot_v2` | 实机通过（受限 identity/选件） | 固定 14 条纯文本 query；同次读取 identity 与手册列出的全部授权选件状态，空 options 仅在全部 13 项明确未安装时成立。health、channel、timebase、probe、waveform、trigger 的 55 个字段按稳定顺序 unavailable；不读状态寄存器、错误队列、trigger、波形或二进制 |
| acquisition 基础配置 | type、averages、memory depth、sample rate、run/stop/single | fetch/capture 的既有状态 | M4 离线通过 | capture 沿用既有配置；深度最高 500 Mpts；设置深度会改变采样率 |
| 采集状态（legacy） | averages 与 trigger status | `scope.acquisition_status` | RFC 后跳过 | legacy 模型要求 average-complete 与 segmented 状态，设备没有对应查询；trigger STOP 不替代平均完成；见 RFC-0006 |
| 采集状态 V2 | `:ACQuire:TYPE?`、`:ACQuire:SRATe?`、`:ACQuire:MDEPth?`，AVER 时 `:ACQuire:AVERages?` | `scope.acquisition_status_v2` | 实机通过（受限 NORM） | 固定 3 条纯读取 query；AVER 时第 4 条读取配置次数。当前回包为 `NORM + 500 kSa/s + 10 kpts`；average 在 NORM 下为 not applicable，run state 与 segmented 为 unavailable。不查询 trigger、OPC 或状态寄存器，不从 STOP 推导完成；AVER 语义和平均完成未验证 |
| 采集运行状态 | `:TRIGger:STATus?` | `scope.acquisition_run_state` | 实机通过（受限观察） | 单条文本 query；STOP→stopped、WAIT→waiting、RUN/AUTO→acquiring，TD→unknown。实机从 AUTO 经 STOP 进入 stopped，再经 NORMAL/RUN 观察到 WAIT，最终 STOP；不以状态查询证明 SINGLE 完成 |
| 采集控制 | `:RUN`、`:STOP`、`:SINGle`、`:TRIGger:SWEep?`、`:ACQuire:TYPE?` | `scope.acquisition_control` | 默认拒绝 | Core 把 start、stop 与完成式 SINGLE 绑为同一 capability。`start(normal)`→`stop` 已实机返回 active/stopped；无信号 SINGLE 的 Core cleanup/fresh verification 已实机通过。受限 CH1 信号的首条状态为 STOP，未满足现有非终态→STOP proof；`*OPC?` 成功后仍可读到 WAIT，不能作为完成证据。见 [RFC-0009](rfcs/0009-single-mode-readback-terminal-stop.md)：仅建议对明确 opt-in 设备采用 `SING` 模式读回后的首条 STOP；Core 未实现、未实机闭环前继续不声明 |
| 平均采集事务 | global acquisition type 与 averages | `scope.capture_average` | RFC 后跳过 | 公共配置要求 single count/逐通道 arithmetic；设备也没有平均完成位；见 RFC-0006 |
| 时基与 edge trigger | main offset/scale、MAIN/XY/ROLL、edge settings/status | capture 前提 | 部分离线通过 | capture 只读前提并沿用配置；任意 setter 不开放，完整 snapshot 见 RFC-0005 |
| 当前屏幕波形 | `WAVeform` NORM/BYTE/preamble/data | `scope.fetch_waveform` | 实机通过（受限 `DEF`） | `LF` trailing、`1,000` bytes 和一次 binary query 已实机通过，core 已完成恢复与新鲜验证。记录的 `1 kHz / 1 Vpp / 0 V` 信号源下，CH1 为 `1.05713 Vpp / 1000 Hz`，CH2 为 `1.0705 Vpp / 999.167 Hz` |
| 深存储波形 | MAX/RAW、start/stop 分块 | `scope.fetch_waveform` | 实机通过（受限 stopped MAX/DMAX） | 唯一 bounded profile 限制每响应 `250,000` bytes、每操作 `4,000,000` bytes、16 次 binary query。MAX/DMAX 均须先观察到 STOP，再读取 memory depth 并把 points 收紧为 memory depth、运行时总点数和 16 倍 chunk 的最小值；不发送 RUN/STOP/SINGLE。source 双路 OFF、CH1/CH2 高阻、当前 `10 kpts` memory depth、`20 kpts / 2.5 kpts chunk` 条件下，CH1/CH2 各自的 MAX/DMAX 均返回 `10,000` 样本并完成五字段 restore/fresh verify。运行态 MAX、其他深度、吞吐、timeout 和 capture 未验证 |
| 单次与多通道 | `:SINGle`、trigger status、逐源 waveform | `scope.capture_waveform(s)` | 默认拒绝 | 离线候选只接受已停止、MAIN 时基下的 `DEF` 与 `BYTE` transfer 基线；当前仍要求一次 SINGLE 后观察非终态→STOP，再由 core 恢复并新鲜验证 acquisition、trigger、MAIN 时基、四路 display/vertical 和 transfer 共 13 个字段；首个 STOP、`MAX/DMAX`、非 BYTE 基线、实机成功完成与 capture capability 均继续拒绝。RFC-0009 的 control proof 不放宽该 capture 条件 |
| 数学波形元数据 | `:MATH<n>:DISPlay?`、waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | 离线通过 | 仅已显示槽位与 MAIN 时基；恢复六项传输状态，不读取 data；实机恢复仍未验证 |
| 手动光标读数 | cursor mode/type/source/unit/value/delta queries | `scope.cursor_readout`、`scope.cursor_readout_v2` | 受限离线通过 | V2 使用全局寻址，读取手动 TIME/AMPL 的独立 A/B source、单位与 A/B/差值；不移动光标。当前实机为 VBA，调用在读取数值前拒绝；准确度未实机验证 |
| 截图 | `:DISPlay:DATA?`、`:SAVE:IMAGe:DATA?` | `scope.screenshot` | RFC 后跳过 | DISPLAY 路径未声明 block framing；SAVE DATA 路径不能证明 `include_menu=False`；见 RFC-0003 |
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
- 错误队列无错误哨兵；
- `*OPC?` 在两次 source 双路 OFF 的 SINGLE 探测中返回成功后仍可读到 WAIT；它不能作为目标采集完成证据；
- [RFC-0009](rfcs/0009-single-mode-readback-terminal-stop.md) 的 Core 实现，以及 `SING` 模式读回后首条 STOP、`WAIT → STOP`、失败恢复与 fresh verification 的低压实机闭环；失败恢复已在无信号条件下验证，但不构成成功采集证据；
- 除记录的 `DEF + LF`、`1 kHz / 1 Vpp / 0 V` 条件外的 X/Y 换算与测量准确度；
- 运行态 MAX，以及不同 memory depth 下 MAX/DMAX 的 binary 吞吐、分块和 timeout；
- screenshot framing；
- RAW chunk 上限、吞吐和 timeout；
- WORD 字节序与有效位宽；
- 快照 V2 中 identity/选件以外的 health、channel、timebase、probe、waveform 与 trigger 字段；
- 数字探头、电气阈值、逻辑活动、数字 waveform 编码和任何测量准确度。
