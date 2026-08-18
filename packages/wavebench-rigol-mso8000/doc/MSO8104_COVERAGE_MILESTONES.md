# MSO8104 功能覆盖里程碑

[English](MSO8104_COVERAGE_MILESTONES_EN.md)

## 目标与证据边界

本文把 RIGOL MSO8000 编程手册中与 MSO8104 相关的命令面拆为 M0～M8。里程碑按风险排序，不按命令数量或完成率排序。

本轮开发只使用手册审计、FakeTransport、故障注入、构建和安装生命周期测试，不连接真实仪器。因此：

- 「离线通过」表示代码与 E1 测试存在；
- 「手册声明」只表示 E0 证据；
- 所有型号、固件、transport、吞吐、测量准确度和状态恢复结论均保持「未实机验证」；
- 不会为了完成里程碑而伪造 E2、E3 或 E4 证据。

当前目标仅为 `MSO8104`。distribution 使用系列名 `wavebench-rigol-mso8000`，canonical driver ID 使用 `rigol.mso8104`。MSO8064 与 MSO8204 不从共用手册自动获得兼容声明。

## 所有阶段共同规则

- 只使用 WaveBench Instrument API V2 公开的 descriptor、Protocol、公共模型和 transport。
- 核心没有所需接口时，提交 RFC 并跳过对应 capability；不使用 raw SCPI 或厂商私有逃生口绕过核心。
- descriptor 只声明代码与离线合同已经覆盖的 capability。
- 所有 transport I/O 由同一个可重入锁串行化。
- 所有数值输入与回包必须是有限数；整数使用精确词法解析，未知枚举 fail closed。
- 写前完成参数校验与可恢复状态快照；写后逐字段回读。首次写入、acquisition 或恢复结果不明时锁存对应写域，不盲目重试。
- `:SYSTem:ERRor?` 是消费型查询；在核心提供非重放文本查询前，不声明 `scope.errors`。
- 二进制 query 由核心 transport 解析 IEEE/TMC block；driver 只接收并校验 payload。
- vendor-local、真实资源、序列号、凭据、波形、截图和命令日志不得进入 wheel 或 sdist。

## 永久默认拒绝区

基础插件不公开以下命令或等价操作：

- raw SCPI；
- `*RST`、`:SYSTem:RESet`、`*SAV`、`*RCL`；
- 选件安装或卸载；
- LAN 参数修改与 `:LAN:APPLy`；
- 仪器或 U 盘文件创建、覆盖、删除与任意路径访问；
- 探头校准、消磁、自检和通用 50 Ω setter；
- 未进入独立事务设计的 AWG 输出、协议总线配置和任意 trigger setter。

## 里程碑状态

| 里程碑 | 状态 | 范围 |
| --- | --- | --- |
| M0 | 完成 | 手册审计、核心合同、证据规则、永久拒绝区和发行隔离 |
| M1 | 离线完成 | 最小身份插件与安装生命周期 |
| M2 | 离线完成 | 输入阻抗安全适配；消费型错误查询 RFC |
| M3 | 离线完成 | 当前屏幕 `NORMal + BYTE` 波形 |
| M4 | 离线完成 | 单次、多通道与有界 MAX/DMAX |
| M5 | RFC 后跳过 | PNG framing 与菜单可见性缺少可证明的核心合同 |
| M6 | RFC/证据缺口后跳过 | 数字状态模型不完整；数字 payload 编码未定义 |
| M7 | 未开始 | 核心已有的受控写与高级只读能力；缺口 RFC |
| M8 | 未开始 | 覆盖文档、全量离线验证和发行包审计 |

## M0：合同与发行边界

冻结内容：

- `driver_id="rigol.mso8104"`、`kind="scope"`、`models=("MSO8104",)`；
- 首选 `backends=("pyvisa",)`；手册声明 USB-TMC、LAN/LXI 与 USB-GPIB，离线 descriptor 可识别 `usb`、`tcpip`、`gpib` 资源前缀，但不声明实机可用性；
- `scope_coupling_policy="switchable-termination"`；
- `OMEG + AC/DC` 归一化为 `ACL/DCL`，`FIFT + AC/DC` 归一化为 `AC/DC`，`GND` 与未知组合默认拒绝采集；
- `DEF → NORMal`；`MAX` 保留设备状态相关语义；`DMAX → stopped RAW`，并受总点数与内存硬上限约束；
- driver 不重复实现 IEEE/TMC block framing；
- 深存储流式输出、非重放文本查询和独立输入阻抗接口作为核心 RFC 主题。

退出证据：公开中英文矩阵、里程碑、MIT LICENSE 与 vendor-local 排除规则进入版本控制。

## M1：身份与包装

公开 `scope.idn`。descriptor 导入零 I/O，factory 恰好打开一次核心 transport，`idn()` 严格验证 RIGOL/MSO8104，`close()` 幂等。

退出门：FakeTransport、descriptor、wheel/sdist、package check、一次性虚拟环境安装/卸载全部离线通过。

离线证据：`0.1.0` 的 package tests、Ruff、源码 package check、wheel/sdist 内容和一次性虚拟环境安装/发现/卸载通过。没有发送真实 `*IDN?`。

## M2：输入阻抗安全适配

公开 `scope.channel_coupling`。该方法联合查询 `:CHANnel<n>:COUPling?` 和 `:CHANnel<n>:IMPedance?`，返回 WaveBench 高阻保护所需的归一化 token。

`scope.errors` 暂不公开：当前 `InstrumentTransport.query()` 允许重放，无法安全表达消费型错误队列。对应核心 RFC 合并前，调用波形 Service 时必须显式配置 `scope.check_errors=false`。

离线证据：`0.2.0` 覆盖 4 个模拟通道的严格参数校验、耦合与端接枚举、六种已知组合、未知回包、关闭状态和核心高阻保护；没有发送真实通道查询。

## M3：当前屏幕波形

公开 `scope.fetch_waveform` 的 `DEF` 路径：目标通道必须已显示，使用 `NORMal + BYTE`，保存并恢复波形传输设置，不隐式 STOP、SINGLE 或 AUTOSCALE。

退出门：严格 preamble、payload 长度、X/Y 轴、有限值、恢复失败锁存和并发不交织测试通过。

离线证据：`0.3.0` 覆盖通道显示预检、严格 10 字段 preamble、1000 字节 payload、X/Y 换算、六字段写后回读与恢复、二进制失败不重放、写入歧义与恢复失败锁存，以及双线程事务不交织。66 项包测试通过；没有发送真实波形查询。

## M4：单次、多通道与有界长记录

公开 `scope.capture_waveform` 与 `scope.capture_waveforms`。多通道必须先配置全部通道，只执行一次 `:SINGle` 与一次完成等待，再逐通道读取并校验 X 轴一致。

`MAX/DMAX` 具备停止状态前提、总点数硬上限、保守 chunk、总内存预算、失败不重放、部分结果回调和状态恢复责任。公共 `WaveformData` 不是流式模型，超大记录保持显式拒绝。

离线证据：`0.4.0` 在 `0.3.1` 的单次采集合同上补齐 MAX/DMAX。BYTE block 最大 250,000 点，每次调用全部通道总计最大 4,000,000 点；超限在 binary query 和数组分配前拒绝。106 项包测试覆盖长记录状态恢复、block 长度、失败不重放、总预算部分结果、MAX 状态相关语义、DMAX STOP 前提与严格整数 option；未验证实机点数、吞吐或 timeout。

## M5：截图

M5 评审结果为「RFC 后跳过」，descriptor 不声明 `scope.screenshot`。

手册称 `:DISPlay:DATA?` 返回 PNG 二进制数据，却没有声明 IEEE/TMC block framing，不能交给核心现有的 `query_bin_block()`。`:SAVE:IMAGe:DATA?` 虽明确返回 TMC block，但依赖 TYPE、INVERT 与 COLOR 状态，且手册没有菜单 inclusion 控制；插件无法诚实满足核心 `include_menu=False` 合同。仪器文件保存路径仍在永久默认拒绝区。

退出证据：[RFC-0003](rfcs/0003-scope-screenshot-framing-and-menu-contract.md) 记录原始二进制单次查询与菜单可见性模型缺口。核心补齐合同前，不猜测 framing、不忽略参数，也不创建仪器文件。没有读取真实截图。

## M6：数字通道

M6 评审结果为两项 capability 均跳过。

`scope.digital_status` 的公共模型要求 activity、technology、threshold coupling、hysteresis 与 label enable 等非空字段。MSO8000 只提供模块、显示、POD 共用阈值、全局 size/deskew、位置和标签查询，不能用默认值补齐其余字段。[RFC-0004](rfcs/0004-portable-scope-digital-status.md) 提议可移植的可选状态模型。

`scope.digital_waveform` 已有合适的 `uint16` bitset 模型，也要求调用方明确确认 acquisition 已停止；缺口在厂商合同。手册允许 D0～D15 作为 waveform source，却没有定义 BYTE/WORD payload 到 LOW/HIGH 的确切 code，WORD 字节序也不明确。插件不把模拟波形换算公式套到数字数据，也不让 FakeTransport fixture 反向充当设备协议证据。

退出证据：descriptor 保持不声明 `scope.digital_status` 与 `scope.digital_waveform`。数字状态等待核心模型，数字波形等待 RIGOL 官方编码证据或后续获批的最小实机原始帧验收；本轮不连接实机。

## M7：受控写与高级能力

逐项评审 WaveBench 已有的 `scope.autoscale`、`scope.snapshot`、`scope.acquisition_status`、平均采集、测量统计、Math/FFT、Reference、Cursor 与 History capability。

公共模型缺少字段、设备查询具有消费性、命令语义无法恢复或核心没有 capability 时，结果为「RFC 后跳过」，不得以默认值补齐模型。DVM、counter、AWG/source、协议解码、mask、search 与 record/playback 不通过基础 scope driver 的私有 API 暴露。

## M8：离线发行审计

完成条件：

- capability、README、覆盖矩阵和测试声明一致；
- package tests、Ruff、根测试、package check 与真实 wheel/sdist 通过；
- 一次性虚拟环境完成安装、发现、调用无 I/O descriptor、卸载和 fallback 验证；
- wheel 只有一个 `wavebench.instruments` entry point 和一个有效 WaveBench dependency；
- vendor-local 与任何实验室数据不进入制品；
- 所有实机相关结论明确标记为「未验证」。
