# DP800 编程手册功能覆盖矩阵

[English](DP800_COVERAGE_MATRIX_EN.md)

## 目的、范围与统计口径

本矩阵将本地保存的 RIGOL DP800 中文编程手册与外置
`wavebench-rigol-dp800` 插件的公开 capability、实际 SCPI、离线测试和已记录的
DP832A LAN 验收证据逐项对照。它回答“手册提供了什么”“插件实际公开了什么”和
“每项结论有什么级别的证据”，不把手册中存在一条命令、Python 方法存在或同一命令域
的相邻功能通过，自动等同于完整功能覆盖。

审计输入为 RIGOL DP800 系列编程手册，文档编号 `PGH03008-1110`，版本日期
`2015-12`。当前 Markdown 转录为 17,525 行，位于本包被 Git 忽略的
`doc/vendor-local/`；该目录不进入提交、wheel 或 sdist。手册覆盖 DP800 系列多个型号、
A/非 A 型、不同通道数、量程和选件，因此本矩阵不把某一型号的范围或选件能力外推给
DP832A，也不把 DP832A 验收外推给整个系列。

按手册“命令系统”目录，本矩阵审计 22 个域：21 个具名厂商/状态子系统
（`ANALyzer`、`APPLy`、`DELAY`、`DISPlay`、`INITiate`、`INSTrument`、`LIC`、
`MEASure`、`MEMory`、`MMEMory`、`MONItor`、`OUTPut`、`PRESet`、`RECAll`、
`RECorder`、`SOURce`、`STATus`、`STORe`、`SYSTem`、`TIMEr`、`TRIGger`）以及
IEEE 488.2 公用命令。set/query 形式、可选关键字、短写和同义命令不作为独立“完成率”
分母，因此本文不报告伪精确的百分比。

当前外置插件版本为 `0.2.0`，声明六项 capability：`power.idn`、`power.status`、
`power.measurement`、`power.set_voltage_current_limit`、`power.output` 和
`power.protection`。它是受安全策略约束的窄电源驱动，不是通用 DP800 SCPI shell。

覆盖标签：

- **外置实机通过**：当前外置插件、针对性离线测试和受控 DP832A 实机证据均存在。
- **已实现 / 离线验证**：代码和精确 FakeTransport 测试存在，但没有该细项的外置实机结论。
- **部分覆盖**：命令域中只有一个窄子集进入公开 API。
- **未覆盖**：手册有命令，但当前插件没有相应 capability 或方法。
- **默认拒绝**：命令会直接改变输出、触发动作、清除保护、重置/恢复仪器、修改连接或写持久数据，不应由普通工作流暴露。

逐阶段的公开 capability、精确指令、安全契约和实机验收门槛见
[DP800 指令覆盖开发里程碑](DP800_COVERAGE_MILESTONES.md)。

## 功能覆盖矩阵

| 功能域 | 手册命令面 | 当前公开覆盖 | 证据状态 | 主要缺口与安全边界 | 建议 |
|---|---|---|---|---|---|
| 身份与错误队列 | `*IDN?`、`:SYSTem:ERRor?`、`:SYSTem:VERSion?` | `power.idn`；写操作后可消费错误队列 | **外置实机通过**；精确查询有离线测试 | `errors()` 会读取并消费队列；没有结构化型号/固件或非消费型 health | 保持错误队列语义显式；公开证据继续脱敏 |
| IEEE 488.2 状态、同步、复位与触发 | `*CLS`、`*ESE/*ESR?`、`*OPC?`、`*RST`、`*SRE/*STB?`、`*TRG`、`*TST?`、`*WAI` | 除 `*IDN?` 外未公开 | **默认拒绝 / 未覆盖** | `*RST` 改变整机；`*TRG` 可触发输出；`*CLS` 和事件查询会清状态；等待/同步语义未建模 | 只考虑窄的只读 condition/health；复位和触发保持独立人工流程 |
| 基础设定值 | `:APPLy` / `:APPLy?` | `power.status` 读取通道额定值、电压和电流设定；`power.set_voltage_current_limit` 用单条 `:APPL` 写入并回读 | **外置实机通过**：DP832A 三通道读取及 CH1 保守写入/恢复 | 读取已拒绝非有限数、未知型号和越界通道；手册定义的单通道无参数 `:APPL?` 两字段回包已离线覆盖，但尚未实机验收，且不猜测额定档位；写路径仍没有失败回滚或歧义锁存 | **P1**：M2 增加显式事务/锁存语义；其他型号逐台验收 |
| 实时测量 | `:MEASure:ALL?`、`:MEASure:VOLTage?`、`:MEASure:CURRent?`、`:MEASure:POWEr?` | `power.measurement` 使用 `:MEAS:ALL? CH<n>` 返回电压、电流、功率；`power.status` 复用同一快照 | **外置实机通过**：DP832A 三通道；有限数与字段数离线门禁通过 | 未公开三个独立标量 query；不宣称测量准确度 | 保持单次 ALL 快照；准确度另行验收 |
| 输出状态与 CV/CC 模式 | `:OUTPut[:STATe]?`、`:OUTPut:CVCC?` / `:OUTPut:MODE?` | `power.status` 查询输出开关和 CV/CC 模式 | **外置实机通过**：DP832A 三通道；严格 `ON/OFF`、`CV/CC/UR` 离线门禁通过 | 其他型号的实际模式回包尚未验收 | 未知枚举继续 fail closed；按型号补实机证据 |
| 显式输出开关 | `:OUTPut[:STATe] [CH<n>,]ON|OFF` | `power.output` 单条写入、回读状态并检查错误队列 | **外置实机通过**：CH1 空载 ON/OFF，最终三通道 OFF | 直接影响被测电路；写超时后状态可能不明，驱动没有 lockout；不能隐式重试 | 保持独立显式 capability；增加首写不明与回读不一致的失败语义 |
| OVP/OCP 状态与阈值 | `:OUTPut:OVP/OCP[:STATe]`、`:VALue`、`:QUES?`/`:ALAR?` | `power.protection` 查询使能、阈值和 trip；可按请求顺序写阈值/使能并回读 | **外置实机通过**：DP832A 三通道读取及 CH1 OVP/OCP 写回/恢复；阈值有限数、使能 `ON/OFF`、trip `YES/NO` 已严格验证 | 一次调用可发四条写命令，后续失败会留下部分应用；未验证 ALAR 别名；阈值关系主要由核心检查 | **P1**：M2 定义逐字段快照、恢复和首写不明锁存 |
| 清除 OVP/OCP | `:OUTPut:OVP:CLEAR`、`:OUTPut:OCP:CLEAR`；`SOURce:*:PROTection:CLEar` 还可能重新打开输出 | 未公开 | **默认拒绝** | 清除 trip 是破坏性动作；`SOURce` clear 的输出副作用尤其危险 | 仅在用户确认故障已排除、输出目标态明确的独立恢复流程中考虑 |
| `SOURce` 电压/电流与保护别名 | `:SOURce<n>:VOLTage/CURRent`、step、triggered level、protection、range | 未作为独立 API；基础立即值和保护由 `APPLy`/`OUTPut` 路径覆盖 | **部分覆盖** | 不覆盖步进、触发设定、DP811 档位或 clear；同义命令不能重复计作覆盖 | 继续使用当前显式通道命令；只有需要独立 V/I 事务时才扩展 |
| 档位、Sense 与跟踪 | `:OUTPut:RANGe`、`:OUTPut:SENSe`、`:OUTPut:TRACk` | 未公开 | **未覆盖** | 型号/通道相关；档位改变安全范围，Sense 依赖远端接线，跟踪会联动通道 | **P2**：先做 option/model-gated 只读 profile；写入需多通道快照与接线确认 |
| 定时输出 | `:TIMEr:*`、`:OUTPut:TIMEr*` | 未公开 | **未覆盖 / 默认拒绝启动** | 参数表、模板和启停会在时间序列中改变实际输出；当前单点状态无法恢复 | **P2**：先定义有界只读 timer profile；执行需独立计划、超时、停止和恢复 |
| 延时输出 | `:DELAY:*` | 未公开 | **未覆盖 / 默认拒绝启动** | 可按条件和时间改变输出，支持循环及终止状态 | 与 timer 分开建模；没有完整参数快照和 finally 停止前不执行 |
| 监测器 | `:MONItor:*` | 未公开 | **未覆盖** | 条件、阈值和停止方式可关闭输出、报警或鸣响；非 A 型可能需选件 | **P2**：先做 option-gated 只读状态；控制写入必须和输出恢复联动 |
| 触发输入、输出与电源触发 | `:TRIGger:*`、`:INITiate`、`*TRG`、`INSTrument:COUPle:TRIGger` | 未公开 | **默认拒绝** | 可改变触发电压/电流、切换输出、驱动数字口或耦合多通道 | 需要独立触发拓扑、端口电气约束、原状态快照和人工确认 |
| 通道选择 | `:INSTrument:NSELect` / `:SELect` | 未使用；当前 API 在每条命令显式传 `CH<n>` | **刻意不覆盖** | 修改“当前通道”会引入隐藏全局状态；当前显式通道更可审计 | 保持显式通道，不为缩短 SCPI 引入可变 current-channel 状态 |
| 录制器 | `:RECorder:*` | 未公开 | **未覆盖 / 默认拒绝启停** | 停止录制会写内部/外部文件；周期、目的地和存储生命周期未建模 | **P3**：如有需求，先做只读 destination/period/state，再设计有界 artifact 导出 |
| 分析器 | `:ANALyzer:*` | 未公开 | **未覆盖** | 依赖有效录制文件和选件；选择文件、时间窗、对象并执行分析 | 在 recorder 文件生命周期明确后，才考虑 query-only result/value |
| 内部状态与用户预设 | `:MEMory:*`、`:PRESet:*`、`:RECAll:LOCal`、`:STORe:LOCal`、`*SAV/*RCL` | 未公开 | **默认拒绝** | 会保存、覆盖、锁定、删除或调用持久状态，可能改变所有通道输出 | 保持主机侧快照与恢复；不使用仪器槽位替代实验事务 |
| 外部存储文件 | `:MMEMory:*`、`:RECAll:EXTErnal`、`:STORe:EXTErnal` | 未公开 | **默认拒绝** | 路径、创建、删除、覆盖和加载均有持久副作用，且依赖外部介质 | 除非有路径沙箱和明确文件权限，否则不纳入普通插件 |
| 显示与前面板 | `:DISPlay:*`、`:SYSTem:BRIGhtness/CONTrast/RGBBrightness/SAVer`、lock/local/remote | 未公开 | **未覆盖 / 写入默认拒绝** | 修改全局前面板状态；remote/lock 可能影响人工接管 | 仅在有诊断价值时考虑只读状态；不让测量流程修改 UI |
| 系统诊断与状态寄存器 | `:SYSTem:SELF:TEST:*`、`:SYSTem:VERSion?`、`:STATus:QUEStionable:*` | 未公开 | **未覆盖** | 部分事件查询会清事件位；self-test 的运行条件和时延未定义 | 可先设计非消费型 condition/version snapshot，并明确事件读取副作用 |
| 网络、串口、GPIB 与全局系统设置 | `:SYSTem:COMMunicate:*`、language、power-on、OTP、ON/OFF sync、track mode | 未公开 | **默认拒绝** | 改 LAN/IP/DHCP 可断开会话；其余会改变持久或全局行为 | 网络和接口永不经普通实验工作流写入；只读状态也应脱敏 |
| 许可证与选件安装 | `:LIC:SET` | 未公开 | **默认拒绝** | 写入许可证/选件状态，属于设备维护而非实验控制 | 不纳入 WaveBench 普通 capability |

## 当前直接使用的 SCPI 表面

以下按手册长写形式归一化；实现实际使用兼容短写，例如 `APPL`、`MEAS`、`OUTP`、
`SYST:ERR?`。这不是原始通信日志，也不代表每条都独立完成准确度或全型号验收。

```text
*IDN?
SYSTem:ERRor?

APPLy? CH<n>
MEASure:ALL[:DC]? CH<n>
OUTPut[:STATe]? CH<n>
OUTPut:MODE? CH<n>
OUTPut:OVP[:STATe]? CH<n>
OUTPut:OVP:VALue? CH<n>
OUTPut:OVP:QUES? CH<n>
OUTPut:OCP[:STATe]? CH<n>
OUTPut:OCP:VALue? CH<n>
OUTPut:OCP:QUES? CH<n>

APPLy CH<n>,<voltage>,<current>
OUTPut[:STATe] CH<n>,ON|OFF
OUTPut:OVP:VALue CH<n>,<voltage>
OUTPut:OVP[:STATe] CH<n>,ON|OFF
OUTPut:OCP:VALue CH<n>,<current>
OUTPut:OCP[:STATe] CH<n>,ON|OFF
```

`power.status` 不是单查询：它依次读取 `APPLy?`、`MEASure:ALL?`、输出状态和输出模式。
`power.protection` 也会依次读取六个保护字段。当前实现若中途查询失败，不返回部分模型。

## WaveBench 提供、但不计入手册覆盖的保障

- 核心的 `max_power_voltage_v`、`max_power_current_limit_a`、保护阈值关系、输出开启前检查、
  run plan 和实验级恢复属于 WaveBench policy/service，不是 DP800 某条 SCPI 的实现。
- 2026-07-24 验收在写入前保存三通道快照，并在独立会话逐字段确认恢复、输出 OFF 和错误
  队列为空；这是受控验收流程的证据，不等于驱动对每次失败都能原子回滚。
- descriptor capability 校验只证明声明的方法存在，不证明命令语义、仪器回包、负载接线、
  测量准确度或所有 DP800 型号兼容。
- settle delay 由核心配置并在写后执行；它不能证明输出已经稳定或达到精度指标。

## 推荐路线

1. **P1：收紧现有六项能力。** 拒绝非有限数值，严格验证枚举和通道；统一错误检查配置；
   为多写保护事务和输出/设定值首写不明定义恢复与实例锁存。
2. **P1：只读通道 profile。** 在型号/选件门控下补充 range、Sense、track、timer/monitor
   状态；继续显式传通道，不引入隐式 current-channel。
3. **P2：timer、delay、monitor。** 先 query-only，再以有界步骤、超时、finally 停止、完整
   快照和多通道恢复实现执行能力。
4. **P3：recorder/analyzer。** 先明确内部/外部文件生命周期、大小上限和 artifact 语义，
   再考虑录制与只读分析结果。
5. **默认不做：网络/接口写入、license、reset/preset、内部状态槽、文件删除/加载和裸触发。**
   它们需要与普通实验流程不同的权限模型和人工确认。

## 证据边界

- **手册侧**：本地 `vendor-local` 中文 DP800 手册仅用于内部审计；本文不复制整本手册，
  也不将其打入发行包。
- **实现侧**：外置插件的 `driver.py`、`descriptor.py`、FakeTransport、lifecycle 和 wheel
  测试，以及 WaveBench 公共 PowerService 契约。
- **实机侧**：2026-07-24 的受管 DP832A LAN 验收，覆盖真实 wheel 安装/路由、三通道只读
  状态和保护、CH1 保守设定值、OVP/OCP、空载输出 ON/OFF、完整恢复与错误队列检查。
- **未验收侧**：其他 DP800 型号、带载瞬态、测量准确度、档位/Sense/跟踪、timer/delay、
  monitor、trigger、recorder/analyzer、存储和系统配置均不得宣称通过。

只有当前外置代码、针对性离线测试、真实仪器命令接受/回读，以及写操作所需的恢复证据都
存在，某一项才可提升为“外置实机通过”。
