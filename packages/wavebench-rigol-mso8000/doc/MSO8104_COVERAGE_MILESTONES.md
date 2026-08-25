# MSO8104 功能覆盖里程碑

[English](MSO8104_COVERAGE_MILESTONES_EN.md)

## 目标与证据边界

本文把 RIGOL MSO8000 编程手册中与 MSO8104 相关的命令面拆为 M0～M8。里程碑按风险排序，不按命令数量或完成率排序。

初始开发只使用手册审计、FakeTransport、故障注入、构建和安装生命周期测试。后续受控实机验收只使用明确的高阻输入、`1 kHz / 1 Vpp / 0 V` 信号和独立 source OFF 复核。因此：

- 「离线通过」表示代码与 E1 测试存在；
- 「手册声明」只表示 E0 证据；
- 实机结论只适用于明确记录的型号、固件、transport 和步骤，不外推；
- 不会为了完成里程碑而伪造 E2、E3 或 E4 证据。

当前目标仅为 `MSO8104`。distribution 使用系列名 `wavebench-rigol-mso8000`，canonical driver ID 使用 `rigol.mso8104`。MSO8064 与 MSO8204 不从共用手册自动获得兼容声明。

## 所有阶段共同规则

- 只使用 WaveBench Instrument API V2 公开的 descriptor、Protocol、公共模型和 transport。
- 核心没有所需接口时，提交 RFC 并跳过对应 capability；不使用 raw SCPI 或厂商私有逃生口绕过核心。
- descriptor 只声明代码与离线合同已经覆盖的 capability。
- 所有 transport I/O 由同一个可重入锁串行化。
- 所有数值输入与回包必须是有限数；整数使用精确词法解析，未知枚举 fail closed。
- 写前完成参数校验与可恢复状态快照；写后逐字段回读。首次写入、acquisition 或恢复结果不明时锁存对应写域，不盲目重试。
- `:SYSTem:ERRor?` 是消费型查询；只通过 Core 的 `scope.error_drain_v1` 和显式 `ReplayPolicy.NO_REPLAY` 读取，不声明 legacy `scope.errors`。
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
| M3 | 实机通过（受限 `DEF` 已知信号） | 当前屏幕 `NORMal + BYTE` 的 `DEF` 波形；使用 RFC-0008 的 bounded binary 合同 |
| M4 | 实机通过（受限 control/capture） | `scope.acquisition_control`、停止态 bounded MAX/DMAX fetch 与已停止、MAIN 时基的 `DEF + BYTE` 单／多通道 capture 已验证。SINGLE 模式读回、`WAIT/TD → STOP`、每通道 1000 样本、恢复 `*OPC? 0 → 1` 与 13 字段 fresh verification 均有受控实机证据；运行态 MAX 与其他组合仍缺证据 |
| M5 | RFC 后跳过 | PNG framing 与菜单可见性缺少可证明的核心合同 |
| M6 | 受控开发（数字状态 V2） | legacy 数字状态与数字 waveform 继续跳过；V2 只读静态状态有核心模型与实机证据 |
| M7 | 受控开发 | autoscale、Math metadata、受限 cursor，以及 portability V2 的输入、统计、FFT、采集状态、数字状态、快照只读子集；其余能力按 RFC/证据缺口跳过 |
| M8 | 离线完成 | 覆盖文档、全量离线验证和发行包审计 |

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

legacy `scope.errors` 不公开。当前 Core 通过 `query(..., replay=ReplayPolicy.NO_REPLAY)` 表达消费型文本查询；插件只在 `scope.error_drain_v1` 中使用该路径。公开有界 fetch/capture 可配置 `scope.check_errors=true`，旧 autoscale 等 legacy 路径仍必须使用 `scope.check_errors=false`。

离线证据：`0.2.0` 覆盖 4 个模拟通道的严格参数校验、耦合与端接枚举、六种已知组合、未知回包、关闭状态和核心高阻保护；没有发送真实通道查询。

开发补充：core 当前开发分支已提供 `scope.channel_input_state_v2`。插件新增无损 V2 映射，保留 AC/DC/GND、high_z/50_ohm 与 `1_000_000/50` Ω，不从 legacy token 反推。199 项包测试、Ruff 与 package check 通过；只读实机查询确认 CH1/CH2 都是 `dc + high_z + 1 MΩ`，查询前后 source 两路均 OFF、`consistent`、`healthy`。

错误队列开发补充：Core 当前开发分支通过 `query(..., replay=ReplayPolicy.NO_REPLAY)` 提供单发文本读取与 `scope.error_drain_v1` 合同。插件严格解析手册格式 `<integer>,"<message>"`，只接受实机观察到的 `0,"No error"` 终止；达到 `max_records` 后再读取一条 overflow 记录。357 项包测试、Ruff 和构建检查通过。公开 `1 Vpp / 0.25 Hz` SINGLE capture 在 `scope.check_errors=true` 下前后 drain 空队列、返回 1000 样本并恢复 13 个字段；非零记录、FIFO 顺序和 overflow 仍只有离线证据。

## M3：当前屏幕波形

离线实现过 `scope.fetch_waveform` 的 `DEF` 路径：目标通道必须已显示，使用 `NORMal + BYTE`，保存并恢复波形传输设置，不隐式 STOP、SINGLE 或 AUTOSCALE。

退出门：严格 preamble、payload 长度、X/Y 轴、有限值、恢复失败锁存和并发不交织测试通过。

离线证据：`0.3.0` 覆盖通道显示预检、严格 10 字段 preamble、1000 字节 payload、X/Y 换算、六字段写后回读与恢复、二进制失败不重放、写入歧义与恢复失败锁存，以及双线程事务不交织。66 项包测试通过。

开发补充：core 当前工作树已实现 RFC-0008 的标准 waveform bounded executor。插件为 fetch 声明 `LF` trailing、受限预算与五字段恢复；为 capture 声明已停止 MAIN `DEF + BYTE` 的 13 字段恢复 profile。确认 CH1/CH2 接线后，既有 `1 kHz / 1 Vpp / 0 V` `DEF` fetch 分别返回 1000 个样本；capture 另以低频方波和 `1 Vpp` 受限输出验证。该结果不外推为其他 point mode、通用测量准确度或未记录的 capture 条件。

M7 开发补充：core 当前开发分支另提供 `scope.cursor_readout_v2`。插件以全局寻址实现手动 `TIME/AMPL` 的独立 A/B source、秒/赫兹/角度/百分比或 source/百分比单位，以及 A、B、差值读数；不移动任何光标。追踪、XY、测量模式、NONE 和 LA 幅度在读取结果前拒绝。实机当前为 `VBA`，V2 因此前置条件拒绝，光标读数准确度仍未实机验证。

M7 开发补充：core 当前开发分支还提供 `scope.measurement_statistics_v2`。插件声明只读 `item_sources` profile，覆盖手册列出的统计 item；每次调用固定读取 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT，拒绝统计 buffer 和不符合 item/source 约束的请求。受控实机以 `VPP,CHAN1` 和 `VPP,CHAN2` 验证 6 个有限返回字段与 `CNT=1000`；不发送统计配置、清零或显示写入。其余 item/source、双 source/数字 source 语义和统计准确度仍未验证。221 项包测试、Ruff 和 wheel 生命周期测试通过。

M7 开发补充：core 当前开发分支还提供 `scope.fft_status_v2`。插件先以 `OPERator? == FFT` 证明目标 math slot 当前为 FFT，再读取 source、window、vertical unit、起始频率与终止频率；6 条 text query 以外不执行 I/O。average-complete、RBW 与 FFT sample rate 固定 unavailable，不由全局 acquisition 值推导。238 项包测试、Ruff 和 wheel 生命周期测试通过；前面板预配置的 MATH1 受控实机返回 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`，前后 source 两路 OFF、`consistent`、`healthy`。该结果不构成 FFT 精度证据。

M7 开发补充：core 当前开发分支还提供 `scope.acquisition_status_v2`。插件固定读取 acquisition type、sample rate 与 memory depth；仅在 `AVER` 模式下读取 configured average count。average 在非 AVER 模式为 not applicable；`average.complete`、run state 与 segmented 分区不报告，不能由 trigger STOP、OPC 或已配置次数推导。253 项包测试、Ruff 和 wheel 生命周期测试通过；受控实机当前返回 `NORM + 500 kSa/s + 10 kpts`，前后 source 两路 OFF、`consistent`、`healthy`。随后受控 `scope.capture_average_v2` probe 对 AVERages、AVER 和 PEAK/NORM 设置均回读 NORM，错误队列为 `0,"No error"`，所以平均模式当前没有远程可达性证据，所有 average capture capability 继续不声明。

M7 开发补充：core 当前开发分支还提供 `scope.digital_status_v2`。插件先读取 LA 模块位；LA 缺席时只报告 `shared.module_present=false`，不读取任何 `:LA:*?`。LA 存在时，D0～D15 以固定 POD1（D0～D7）或 POD2（D8～D15）范围读取 display、label、POD 阈值、全局 timing calibration 和 size，共 6 条文本 query。position、label-enabled、activity、technology 与 hysteresis 维持 unavailable，不读取 digital waveform。268 项包测试、Ruff 和 wheel 生命周期测试通过；受控实机 D0/D8 均返回 displayed、对应 label/POD、`1.4 V`、`0 s` 和 `MEDIUM`，前后 source 两路 OFF、`consistent`、`healthy`。数字探头、电气阈值、逻辑活动与编码语义仍未验证。

M7 开发补充：core 当前开发分支还提供 `scope.snapshot_v2`。插件只声明 identity/授权选件静态 profile：一次 `*IDN?` 加 13 种 `:SYSTem:OPTion:STATus? <type>`，共 14 条纯文本 query；identity 与 options 均必须来自同一调用，空 options 仅在 13 项均明确未安装时成立。health、channel、timebase、probe、waveform、trigger 的 55 个字段保持 unavailable，不读取 `*STB?`、`*ESR?`、错误队列、trigger、波形或二进制。282 项包测试、Ruff 和 wheel 生命周期测试通过；受控实机完成该 profile，前后 source 两路 OFF、`consistent`、`healthy`。未读取的六个分区及其准确度仍未验证。

## M4：单次、多通道与有界长记录

`scope.capture_waveform` 与 `scope.capture_waveforms` 已声明。多通道先配置全部通道，只执行一次 `:SINGle` 与一次完成等待，再逐通道读取并校验 X 轴一致。

`MAX/DMAX` 具备停止状态前提、总点数硬上限、保守 chunk、总内存预算、失败不重放、部分结果回调和状态恢复责任。公共 `WaveformData` 不是流式模型，超大记录保持显式拒绝。

离线证据：`0.4.0` 在 `0.3.1` 的单次采集合同上补齐 MAX/DMAX。BYTE block 最大 250,000 点，每次调用全部通道总计最大 4,000,000 点；超限在 binary query 和数组分配前拒绝。106 项包测试覆盖长记录状态恢复、block 长度、失败不重放、总预算部分结果、MAX 状态相关语义、DMAX STOP 前提与严格整数 option。

开发补充：core 当前开发分支提供 `scope.acquisition_run_state` 与 `scope.acquisition_control` 合同。插件声明两者；单条 `:TRIGger:STATus?` 仍将 STOP、WAIT、RUN/AUTO 分别映射为 stopped、waiting、acquiring，通常 TD 为 unknown。仅在 SINGLE 写入后已读回 `SING` 的事务中，TD 可作为非终态 arming 观察，后续必须到 STOP。受控实机已验证 `start(normal)`→`stop`，以及 `SING` 模式读回后的首条 STOP、`WAIT → STOP` 和 `TD → STOP`。`*OPC?` 不构成 completion proof。

开发补充：唯一 bounded fetch profile 现在允许每响应 `250,000` bytes、每操作 `4,000,000` bytes、最多 16 次 binary query。MAX/DMAX 都先要求 stopped，再读取 current memory depth，并把 points 限制为 memory depth、运行时总点数与 16 倍 chunk 的最小值。source 双路 OFF、CH1/CH2 高阻、scope stopped、当前 `10 kpts` memory depth、运行时 `20 kpts / 2.5 kpts chunk` 的独立实机步骤中，CH1/CH2 的 MAX 与 DMAX 均返回 `10,000` 样本，且 core 完成五字段 restore/fresh verify。该证据不包含运行态 MAX、其他 memory depth、吞吐或 timeout。

开发补充：capture 使用 core 的 bounded executor，公开声明 `scope.capture_waveform` 与 `scope.capture_waveforms`。它仅接受已停止、MAIN 时基的 `DEF + BYTE` baseline；capture 必须观察非终态到 STOP，首条 STOP 仍被拒绝。单通道与双通道受控实机均返回每通道 1000 个样本；双通道只执行一次 SINGLE、读取两段 binary payload。Core 恢复并新鲜验证 acquisition、trigger、MAIN 时基、四路 display/vertical、waveform source/mode/format/points/window、query-response-header 和 byte-order 共 13 个字段。恢复写后最多 8 次 `*OPC?` 轮询至 `1`，然后才做字段验证；这只同步恢复写，不证明采集完成或波形新鲜性。

## M5：截图

M5 评审结果为「RFC 后跳过」，descriptor 不声明 `scope.screenshot`。

手册称 `:DISPlay:DATA?` 返回 PNG 二进制数据，却没有声明 IEEE/TMC block framing，不能交给核心现有的 `query_bin_block()`。`:SAVE:IMAGe:DATA?` 虽明确返回 TMC block，但依赖 TYPE、INVERT 与 COLOR 状态，且手册没有菜单 inclusion 控制；插件无法诚实满足核心 `include_menu=False` 合同。仪器文件保存路径仍在永久默认拒绝区。

退出证据：[RFC-0003](rfcs/0003-scope-screenshot-framing-and-menu-contract.md) 记录原始二进制单次查询与菜单可见性模型缺口。核心补齐合同前，不猜测 framing、不忽略参数，也不创建仪器文件。没有读取真实截图。

## M6：数字通道

初始评审中，两项 legacy capability 均跳过。core R1 随后实现 [RFC-0004](rfcs/0004-portable-scope-digital-status.md) 的可移植 V2 模型，允许按逐通道、POD 与共享状态分别报告可证明字段。

legacy `scope.digital_status` 继续跳过：其公共模型要求 activity、technology、threshold coupling、hysteresis 与 label enable 等非空字段。MSO8000 只能证明模块、显示、POD 共用阈值、全局 size/timing calibration 和标签；`position` 查询格式又有歧义，不能用默认值补齐其余字段。

`scope.digital_status_v2` 受控声明：只接受 D0～D15，每次先查询 LA 模块位；模块缺席时只报告 `shared.module_present=false`，不发送 `:LA:*?`。模块存在时固定读取显示、标签、所属 POD 阈值、全局 timing calibration 与 size，并将 position、label-enabled、activity、technology 与 hysteresis 标为 unavailable。D0 与 D8 的受控只读实机查询已验证两组 POD 边界和静态回包；不构成逻辑活动、电气阈值或数字探头准确度结论。

`scope.digital_waveform` 已有合适的 `uint16` bitset 模型，也要求调用方明确确认 acquisition 已停止；缺口仍在厂商合同。手册允许 D0～D15 作为 waveform source，却没有定义 BYTE/WORD payload 到 LOW/HIGH 的确切 code，WORD 字节序也不明确。插件不把模拟波形换算公式套到数字数据，也不让 FakeTransport fixture 反向充当设备协议证据。

退出证据：descriptor 受控声明 `scope.digital_status_v2`，但继续不声明 legacy `scope.digital_status` 与 `scope.digital_waveform`。数字 waveform 等待 RIGOL 官方编码证据或后续获批的最小实机原始帧验收。

## M7：受控写与高级能力

逐项评审 WaveBench 已有的 `scope.autoscale`、`scope.snapshot`、`scope.acquisition_status`、平均采集、测量统计、Math/FFT、Reference、Cursor 与 History capability。

公共模型缺少字段、设备查询具有消费性、命令语义无法恢复或核心没有 capability 时，结果为「RFC 后跳过」，不得以默认值补齐模型。DVM、counter、AWG/source、协议解码、mask、search 与 record/playback 不通过基础 scope driver 的私有 API 暴露。

`0.5.0` 已公开 `scope.autoscale`。调用前查询 `:SYSTem:AUToscale?`，系统禁用 AUTO 时不发送写命令；当前必须设置 `check_errors=false`。该操作按核心合同明确改变垂直、时基和触发，不承诺恢复。`wait_opc=true` 将 `*OPC? = 0` 视为未完成并在配置超时内轮询，只有 `1` 成功；写入、异常回包或超时仅锁存 autoscale 写域，禁止盲目重试。CH1 `1 Vpp / 1 kHz` 的受控 probe 在 `15 s` 内未取得完成态，因而没有发起后续波形读取；`wait_opc=false` 和自动设置效果继续没有实机证据。

`0.6.0` 已公开 `scope.math_metadata`。核心将该操作定义为 `stateful_read`；MSO8104 没有独立的 Math metadata query，因此 driver 仅在目标 MATH 槽位已显示且时基为 MAIN 时，保存 waveform SOURCE、MODE、FORMAT、POINTS、START 与 STOP，先切换 NORM 再选择 MATH 源与 BYTE 格式，查询十字段 preamble 后恢复。该路径不发送 `:WAVeform:DATA?`。受控实机的 MATH1 调用在 source 双路 OFF、scope STOP／高阻下返回 1000 点、有限 X/Y 轴、`values_per_sample=None` 与 8 位 BYTE 元数据，并完成六字段最终恢复复核。数学内容、MATH2～MATH4、其他 operator 的轴语义与 FFT 精度仍未验证。

`0.7.0` 已公开受限 `scope.cursor_readout`。MSO8104 只有一套全局 cursor 状态，公共 `cursor_index` 因此只接受整数 `1`；调用方必须设置 `configured_cursor=true`。driver 只读取手动模式下 A/B 同源的 `TIME + SEC` 或 `AMPL + SOUR` 配置，分别返回 X 差/倒数或 Y 差，不移动任何光标。其余模式、双源和单位无法由当前单 source 模型无歧义表达，均在结果查询前拒绝。168 项包测试全部为离线证据，光标读数准确度未实机验证。

其余 M7 capability 的结论如下：

| capability | 结论 | 原因 |
| --- | --- | --- |
| `scope.digital_status_v2` | 实机通过（受限 D0/D8 静态状态） | LA 模块预检后，固定 6 条纯读取 query 返回 display、label、POD 阈值和共享 timing calibration/size；position、label-enabled、activity、technology、hysteresis 精确 unavailable，不读取数字 waveform |
| `scope.snapshot_v2` | 实机通过（受限 identity/选件） | `*IDN?` 加 13 种授权选件状态 query；identity/options 完整可读，其他 55 个字段精确 unavailable；不读消费型状态、trigger、波形或二进制 |
| `scope.snapshot` | RFC 后跳过 | 完整模型强制要求 MSO8000 无法查询的 health、probe 与 channel 字段；见 [RFC-0005](rfcs/0005-portable-scope-snapshot.md) |
| `scope.acquisition_status` | RFC 后跳过 | legacy 模型把平均完成与 segmented 状态绑定，设备没有对应查询；见 [RFC-0006](rfcs/0006-portable-scope-acquisition-contracts.md) |
| `scope.acquisition_status_v2` | 实机通过（受限 NORM） | type/sample rate/memory depth 纯读取；AVER 时才读取配置次数。当前验证 `NORM + 500 kSa/s + 10 kpts`；不报告 run state、segmented 或 average complete |
| `scope.acquisition_run_state` | 实机通过（受限观察） | 单条 trigger-status query；AUTO→acquiring、STOP→stopped、NORMAL/RUN→WAIT 已验证。SINGLE completion 不由该观察推导 |
| `scope.acquisition_control` | 实机通过（受限） | `start(normal)`、`stop` 与 post-arm `SING` 模式读回后的 terminal STOP 或 `WAIT/TD → STOP` 已验证；completion proof 不自动证明波形新鲜性 |
| `scope.capture_waveform`、`scope.capture_waveforms` | 实机通过（受限 bounded `DEF + BYTE`） | 已停止 MAIN baseline；单／双通道每通道 1000 样本，双通道一次 SINGLE，两种调用均完成 13 字段恢复/新鲜验证 |
| `scope.error_drain_v1` | 实机通过（受限空队列） | 每条 `:SYSTem:ERRor?` 显式 no-replay；`scope.check_errors=true` 的公开 capture 在主操作前后各 drain 一次空队列并完成 13 字段恢复；非零/FIFO/overflow 仍只有离线证据 |
| `scope.math_metadata` | 实机通过（受限 MATH1） | 已显示 MATH1、MAIN 下的 public 调用只读 preamble，不读 data，返回 1000 点／有限轴／8 位 BYTE 元数据，并恢复和最终复核六项 transfer 字段；数学内容、其他槽位／operator 轴语义和 FFT 精度未验证 |
| `scope.capture_average_v2` | 实机前提失败后跳过 | Core 已提供 V2 合同，但 AVERages/AVER 与 PEAK/NORM 对照写入同步后都回读 NORM，错误队列为 `0,"No error"`；设备当前无法远程进入平均模式，且没有平均完成位；见 [RFC-0006](rfcs/0006-portable-scope-acquisition-contracts.md) |
| `scope.measurement_statistics` | RFC 后跳过 | legacy 核心按 slot 寻址，设备按 item/source 查询且不能反查界面 slot；见 [RFC-0007](rfcs/0007-portable-scope-analysis-reads.md) |
| `scope.measurement_statistics_v2` | 受控开发 | 显式 item/source、6 条纯读取查询、无统计 buffer。`VPP,CHAN1/CHAN2` 已完成受控实机回包验证；其他 item/source 和统计准确度未验证 |
| `scope.fft_status` | RFC 后跳过 | legacy 模型强制要求 average-complete、RBW 与 FFT sample rate，设备没有这些 query；见 [RFC-0007](rfcs/0007-portable-scope-analysis-reads.md) |
| `scope.fft_status_v2` | 实机通过（受限 MATH1） | 先确认 `FFT` operator，再读取 source/window/unit/起止频率；MATH1 已验证 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`，三项无合同字段精确 unavailable，不构成 FFT 精度证据 |
| `scope.reference_metadata` | 厂商证据缺口后跳过 | Reference 命令只有 source、垂直显示和标签；waveform source 不接受 REF，无法得到轴、点数和分辨率 |
| `scope.history_timestamps` | 厂商证据缺口后跳过 | Record 命令只有 enable/start/play/current/frame count，没有逐帧相对或日历时间戳 |

M7 退出证据：当前 Core 开发分支的受控 descriptor 声明 bounded fetch/capture、math metadata、acquisition control、error drain、input、cursor、measurement-statistics、FFT、acquisition-status、acquisition-run-state、digital-status 和 snapshot V2 子集。覆盖矩阵记录其余结论；不使用默认值、私有 API 或设备文件补齐缺口。

## M8：离线发行审计

完成条件：

- capability、README、覆盖矩阵和测试声明一致；
- package tests、Ruff、根测试、package check 与真实 wheel/sdist 通过；
- 一次性虚拟环境完成安装、发现、调用无 I/O descriptor、卸载和 fallback 验证；
- wheel 只有一个 `wavebench.instruments` entry point 和一个有效 WaveBench dependency；
- vendor-local 与任何实验室数据不进入制品；
- 所有实机相关结论均标明受控条件与未覆盖边界。

离线证据：`0.7.0` 的 168 项包测试与 Ruff 通过；在 WaveBench core 位于同级目录的一次性仓库布局中，根测试为 715 项通过、2 项因缺少 SP3000A 私有实机证据而按预期跳过。WaveBench `0.8.22` 的源码目录与真实 wheel package check 均通过。wheel 仅包含一个 `wavebench.instruments` entry point、一个有效 WaveBench runtime dependency、MIT 许可证和插件代码；sdist 包含公开 README、矩阵、里程碑、RFC、测试与许可证。两种制品均不包含 vendor-local。一次性虚拟环境中的 wheel 安装、零 I/O descriptor 发现、卸载和 canonical ID fallback 通过；61 个受跟踪 Markdown 文件的本地链接有效。全程未连接真实仪器。

`0.9.0` 开发回归在当前 WaveBench `0.8.24` 工作树中包含有界 waveform、control/capture、math metadata、error drain、input、cursor、measurement-statistics、FFT status、acquisition status/run-state、digital status 和 snapshot V2 集成测试，合计 357 项包测试与 Ruff 通过；源码目录和真实 wheel 的生命周期测试也通过。由于所需 Core API 尚未单独发布，该结果不构成公开 wheel 发布。
