# MSO8104 编程手册功能覆盖矩阵

[English](MSO8104_COVERAGE_MATRIX_EN.md)

实施顺序和共同安全规则见 [MSO8104 功能覆盖里程碑](MSO8104_COVERAGE_MILESTONES.md)。命令出现在本矩阵中不表示插件已经实现，也不表示目标固件已经验证。

## 范围与证据口径

审计输入为 RIGOL MSO8000 中文编程手册 `PGA26006-1110`。手册同时覆盖 MSO8064、MSO8104 与 MSO8204，并主要使用 MSO8204 举例；本插件首轮只声明 MSO8104。

当前开发限定为离线验证：

- **手册声明**：命令和返回域来自手册；
- **离线通过**：代码与 FakeTransport/故障注入测试存在；
- **RFC 后跳过**：WaveBench 核心缺少必要的安全接口或公共模型；
- **默认拒绝**：基础插件不开放该高风险命令域；
- **未实机验证**：没有型号、固件、transport、吞吐或测量准确度结论。

## 功能矩阵

| 功能域 | 手册命令面 | WaveBench 接口 | 当前状态 | 边界与建议 |
| --- | --- | --- | --- | --- |
| 身份 | `*IDN?` | `scope.idn` | 离线通过 | 严格接受 RIGOL/MSO8104；FakeTransport 使用虚构序列号，未实机验证 |
| 错误队列 | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC 后跳过 | 查询会消费队首；核心普通文本 query 允许重放 |
| 输入安全 | `:CHANnel<n>:COUPling?`、`:CHANnel<n>:IMPedance?` | `scope.channel_coupling` | 离线通过 | 联合映射 ACL/DCL/AC/DC；核心默认拒绝 50 Ω、GND 与未知组合 |
| 模拟通道状态 | display、scale、offset、bandwidth、probe | `scope.snapshot` 的一部分 | M7 评审 | 公共快照要求完整 health/timebase/probe/waveform/trigger；不填虚假默认值 |
| acquisition | type、averages、memory depth、sample rate、run/stop/single | capture 与 acquisition status | M4/M7 计划 | 深度最高 500 Mpts；设置深度会改变采样率 |
| 时基 | main offset/scale、MAIN/XY/ROLL | capture 参数、snapshot | M4/M7 计划 | 慢时基可能进入 ROLL 并禁用多项功能 |
| edge trigger | source、slope、level、status、sweep | capture、snapshot | M4/M7 计划 | 首轮沿用已配置 trigger；任意 setter 不开放 |
| 当前屏幕波形 | `WAVeform` NORM/BYTE/preamble/data | `scope.fetch_waveform` | 离线通过 | 固定 1000 点；目标通道须已显示；恢复六项传输状态，不隐式停止 acquisition |
| 深存储波形 | MAX/RAW、start/stop 分块 | fetch/capture | 离线通过 | 每块最多 250,000 点、每次调用总计最多 4,000,000 点；超大流式输出需核心 RFC |
| 单次与多通道 | `:SINGle`、trigger status、逐源 waveform | `scope.capture_waveform(s)` | 离线通过 | 一次 SINGLE 后轮询 STOP 并读多通道；DEF/MAX/DMAX；X 轴一致；不使用 `*OPC?` 冒充采集完成 |
| 截图 | `:DISPlay:DATA?`、`:SAVE:IMAGe:DATA?` | `scope.screenshot` | RFC 后跳过 | DISPLAY 路径未声明 block framing；SAVE DATA 路径不能证明 `include_menu=False`；见 RFC-0003 |
| 数字通道状态 | `:SYSTem:MODules?`、`:LA:*?` | `scope.digital_status` | RFC 后跳过 | 核心模型必填 activity、technology、hysteresis 等设备无法查询的字段；见 RFC-0004 |
| 数字波形 | D0～D15 waveform source/data | `scope.digital_waveform` | 手册证据不足后跳过 | 公共 bitset 模型可用，但手册未定义 BYTE/WORD 的 LOW/HIGH code，WORD 字节序也不明确 |
| 自动测量与统计 | `:MEASure:*` | measurement statistics | M7 评审 | 只读已配置项目；不自动创建或清空统计 |
| Math/FFT/Reference/Cursor | 对应命令族 | 对应 typed capability | M7 评审 | 只读取既有配置；公共模型不匹配时 RFC 后跳过 |
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

- `*IDN?` 的目标固件实际格式；
- USB、LAN 和 GPIB 资源的连接与终止符；
- 错误队列无错误哨兵；
- `*OPC?` 是否等待目标 single acquisition；
- screenshot framing；
- RAW chunk 上限、吞吐和 timeout；
- WORD 字节序与有效位宽；
- LA 模块、数字探头、选件和任何测量准确度。
