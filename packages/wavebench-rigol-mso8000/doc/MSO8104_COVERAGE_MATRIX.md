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
| acquisition 基础配置 | type、averages、memory depth、sample rate、run/stop/single | fetch/capture 的既有状态 | M4 离线通过 | capture 沿用既有配置；深度最高 500 Mpts；设置深度会改变采样率 |
| acquisition 状态 | averages 与 trigger status | `scope.acquisition_status` | RFC 后跳过 | 没有 average-complete 或 segmented 状态；trigger STOP 不替代平均完成；见 RFC-0006 |
| 平均采集事务 | global acquisition type 与 averages | `scope.capture_average` | RFC 后跳过 | 公共配置要求 single count/逐通道 arithmetic；设备也没有平均完成位；见 RFC-0006 |
| 时基与 edge trigger | main offset/scale、MAIN/XY/ROLL、edge settings/status | capture 前提 | 部分离线通过 | capture 只读前提并沿用配置；任意 setter 不开放，完整 snapshot 见 RFC-0005 |
| 当前屏幕波形 | `WAVeform` NORM/BYTE/preamble/data | `scope.fetch_waveform` | 实机通过（受限 `DEF`） | 当前 core 工作树的 bounded profile 只开放 `DEF`；`LF` trailing、`1,000` bytes 和一次 binary query 已实机通过，core 已完成恢复与新鲜验证。记录的 `1 kHz / 1 Vpp / 0 V` 信号源下，CH1 为 `1.05713 Vpp / 1000 Hz`，CH2 为 `1.0705 Vpp / 999.167 Hz` |
| 深存储波形 | MAX/RAW、start/stop 分块 | fetch/capture | 默认拒绝 | MAX/DMAX 尚未通过有界 profile 与实机验收；每块和总点数离线边界保留 |
| 单次与多通道 | `:SINGle`、trigger status、逐源 waveform | `scope.capture_waveform(s)` | 默认拒绝 | capture 还缺 acquisition、trigger、timebase 与通道状态的完整恢复证据；不以 SINGLE 或 `*OPC?` 冒充完整验收 |
| 数学波形元数据 | `:MATH<n>:DISPlay?`、waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | 离线通过 | 仅已显示槽位与 MAIN 时基；恢复六项传输状态，不读取 data；实机恢复仍未验证 |
| 手动光标读数 | cursor mode/type/source/unit/value/delta queries | `scope.cursor_readout`、`scope.cursor_readout_v2` | 受限离线通过 | V2 使用全局寻址，读取手动 TIME/AMPL 的独立 A/B source、单位与 A/B/差值；不移动光标。当前实机为 VBA，调用在读取数值前拒绝；准确度未实机验证 |
| 截图 | `:DISPlay:DATA?`、`:SAVE:IMAGe:DATA?` | `scope.screenshot` | RFC 后跳过 | DISPLAY 路径未声明 block framing；SAVE DATA 路径不能证明 `include_menu=False`；见 RFC-0003 |
| 数字通道状态 | `:SYSTem:MODules?`、`:LA:*?` | `scope.digital_status` | RFC 后跳过 | 核心模型必填 activity、technology、hysteresis 等设备无法查询的字段；见 RFC-0004 |
| 数字波形 | D0～D15 waveform source/data | `scope.digital_waveform` | 手册证据不足后跳过 | 公共 bitset 模型可用，但手册未定义 BYTE/WORD 的 LOW/HIGH code，WORD 字节序也不明确 |
| 自动测量与统计 | item/source statistic queries | `scope.measurement_statistics` | RFC 后跳过 | 核心按 slot 寻址；设备不能反查 slot 且无统计 buffer；见 RFC-0007 |
| FFT 状态 | FFT source/window/unit/frequency settings | `scope.fft_status` | RFC 后跳过 | 设备没有公共模型必填的 average-complete、RBW 与 FFT sample rate；见 RFC-0007 |
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
- `*OPC?` 是否等待目标 single acquisition；
- 除记录的 `DEF + LF`、`1 kHz / 1 Vpp / 0 V` 条件外的 X/Y 换算与测量准确度；
- MAX/DMAX 的 binary 吞吐、分块和 timeout；
- screenshot framing；
- RAW chunk 上限、吞吐和 timeout；
- WORD 字节序与有效位宽；
- LA 模块、数字探头、选件和任何测量准确度。
