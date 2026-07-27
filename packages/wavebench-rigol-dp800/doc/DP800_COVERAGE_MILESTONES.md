# DP800 指令覆盖开发里程碑

[English](DP800_COVERAGE_MILESTONES_EN.md)

本文把 [DP800 编程手册功能覆盖矩阵](DP800_COVERAGE_MATRIX.md) 转成可实施、可验证、
可逐步交付的开发计划。目标不是追求一个脱离风险的“命令覆盖率”，而是让每一批公开指令
都具备明确的数据模型、设备适用条件、失败语义和实机恢复证据。

当前外置插件版本为 `0.3.0`，已经公开六项 capability：`power.idn`、`power.status`、
`power.measurement`、`power.set_voltage_current_limit`、`power.output` 和
`power.protection`。2026-07-24 的 DP832A LAN 验收已经证明这些路径在受控条件下可用；
2026-07-27 又完成 M2 正常路径和受控故障/恢复实机验收。事务、恢复和状态不明锁存路径
同时具备离线故障注入覆盖。

手册覆盖多个 DP800 型号、A/非 A 型和选件组合。下文的型号门控是功能契约的一部分：
DP832A 的结果不能外推给 DP811、DP821、DP831 或整个系列，`*OPT?` 报告的选件也不能
替代实际接口、通道和负载接线检查。

## 验收口径

### 证据等级

- **静态完成**：手册命令、型号/选件条件、响应类型和副作用已记录。
- **离线完成**：公共 typed model、driver contract、descriptor capability、Service/CLI
  前置检查和精确 FakeTransport 命令序列测试均存在。
- **查询实机通过**：限定超时内返回完整响应；严格枚举、范围和有限数解析通过；命令记录
  证明零写入。查询不证明测量准确度。
- **受控写入实机通过**：写前保存所有受影响字段，写入不同且安全的目标值，回读确认，
  `finally` 恢复原值，再在独立会话逐字段确认恢复。只做同值写回不算通过。
- **准确度通过**：需要可追溯源、负载、接线和误差预算；与协议验收分开记录。

### 所有阶段共同规则

- 读数、设定值、阈值和功率必须为有限数，拒绝 `NaN` 和正负无穷。
- 通道、枚举、范围、单位和二进制块长度必须严格验证；未知值不能悄悄降级。
- 每条面向指定通道的公开 API 显式携带通道。current-channel profile 是显式例外：
  它不通过 `:INSTrument:SELect` 改变隐藏状态，并在结果中返回实际读取的通道；确实依赖
  current-channel 的 timer/delay 事务必须保存并恢复它。
- 仪器写操作、输出控制和触发不盲目重试。首次写超时、断连或响应不明时，当前驱动实例
  锁停后续配置写入，直到关闭并重新建立会话。
- 多写事务任一步失败都尝试恢复原快照；恢复失败必须返回失败并锁停，不能只报告最后一个
  可读状态。
- 输出 ON、timer/delay 启动、monitor 动作、recorder 写文件和 trigger 执行必须由用户
  显式请求；普通 snapshot 不隐式执行这些动作。
- 实机证据不保存真实地址、序列号、MAC、原始日志或负载数据；文档示例使用保留地址。

## 总体路线

| 里程碑 | 主要指令面 | 目标状态 |
|---|---|---|
| M0 | 手册 22 域、打包边界、现有 6 capabilities | **完成** |
| M1 | 现有状态、测量、保护查询 | **完成** |
| M2 | `APPLy`、输出开关、OVP/OCP 写入 | **完成** |
| M3 | 选件、SCPI 版本、自检、非消费型状态 | 零写入设备健康快照 |
| M4 | Range、Sense、Track、当前通道状态 | 型号/选件门控的通道 profile |
| M5 | `TIMEr` / `OUTPut:TIMEr` 查询 | 零写入 timer profile |
| M6 | 有限 timer 配置与执行 | 有界时序输出 |
| M7 | `DELAY` 查询 | 零写入 delay profile |
| M8 | 有限 delay 配置与执行 | 有界延时输出 |
| M9 | `MONItor` 查询与受控联锁 | 监测器 profile 和安全动作 |
| M10 | `RECorder` / `ANALyzer` | 有界 artifact 生命周期 |
| M11 | `TRIGger` 拓扑查询 | 选件门控、默认零执行 |
| M12 | 多型号回归和发布收口 | 稳定兼容矩阵 |

M1–M4 是当前优先级；M5 以后只有在前序事务语义稳定后才开始。M10/M11 不为追赶编号
而提前发送高副作用命令。

## M0：命令清点与发布边界 — 完成

### 已完成

- 中英文覆盖矩阵已按 22 个手册命令域对照插件 API、测试和 DP832A 证据。
- 当前直接使用的 SCPI、未覆盖域和默认拒绝面已经显式列出。
- 厂商手册只保存在 `doc/vendor-local/`，Git 忽略并由 Hatch sdist 配置显式排除。
- wheel/sdist 回归测试防止厂商资料进入发行包；公开矩阵仍进入 sdist。

### 当前基线指令

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

## M1：收紧现有只读能力 — 完成

### 覆盖指令

```text
*IDN?
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
```

`SYSTem:ERRor?` 保持显式、会消费队列的诊断操作，不放入普通 status snapshot。

### 开发内容

- `APPLy?` 和 `MEASure:ALL?` 的所有数值增加有限数检查，禁止 `NaN`/`inf`。
- `OUTPut[:STATe]?` 只接受 `ON/OFF`；模式只接受经实机确认的 `CV/CC/UR`；保护使能
  只接受 `ON/OFF`，trip 只接受 `YES/NO`。
- 基于 IDN/model profile 验证通道数量，不再只检查 `channel >= 1`。
- aggregate snapshot 保持全有或全无：中途查询失败不返回不完整 `PowerStatus` 或
  `PowerProtectionStatus`。
- IDN 仍可返回给交互用户，但默认报告和测试证据必须脱敏序列号。

### 完成门槛

- 每个异常枚举、非有限值、少字段/多字段、越界通道和中途失败都有精确离线测试。
- DP832A 三通道执行零写入查询，命令序列和解析通过；不要求测量准确值命中标称误差。

### 验收证据

- core `0.8.12` 与外置插件 `0.2.0` 已实现型号/通道门控、有限数、严格枚举和全有或全无快照。
- 离线故障注入覆盖 status 四个查询位置、protection 六个查询位置、六种枚举、少字段/多字段和非有限数。
- 手册定义的单通道无参数 `:APPL?` 两字段回包已离线覆盖，额定档位返回不可用；该路径尚未实机验收。
- 2026-07-27 DP832A 三通道完成 31 条查询、零写入验收；三个输出最终均为 OFF。
- 该证据仅覆盖 DP832A 协议回包，不外推 DP811/821/831，也不证明测量准确度。

## M2：事务化现有写入能力 — 完成

### 覆盖指令

```text
APPLy CH<n>,<voltage>,<current>
OUTPut[:STATe] CH<n>,ON|OFF
OUTPut:OVP:VALue CH<n>,<voltage>
OUTPut:OVP[:STATe] CH<n>,ON|OFF
OUTPut:OCP:VALue CH<n>,<current>
OUTPut:OCP[:STATe] CH<n>,ON|OFF
```

回读使用 M1 的 `APPLy?`、输出和保护查询；可选错误检查仍通过显式
`SYSTem:ERRor?` 完成。

### 开发内容

- 为同一 driver 实例的所有 transport I/O 使用统一可重入锁，防止读写事务交错。
- `APPLy` 写前保存原电压/电流，写后验证两者；失败恢复原值。首次写不明立即锁停。
- 输出开关写前保存原状态；启用输出前由 Service 复核 safety limit、保护阈值、目标设定和
  用户显式确认；驱动不盲目重发 ON。
- OVP/OCP 事务保存四个配置字段及两个 trip 字段。按不会暂时削弱保护的顺序写入，逐项
  回读；失败恢复全部可恢复字段。trip 本身不通过 CLEAR 伪造恢复。
- `check_errors_after_ops` 的配置和方法参数语义统一，避免 descriptor 传值却被忽略。

### 验收证据

- core `0.8.13` 与外置插件 `0.3.0` 已实现统一可重入锁、逐步回读、保守恢复、
  半 LSB 匹配和配置写锁存；Service 在输出 ON 前复核 safety limit、保护阈值和 trip。
- 离线测试覆盖首写结果不明、后续写失败、回读不一致、恢复失败、新 trip 不清除和并发 I/O 不交错。
- 2026-07-27 在 DP832A CH1 完成不同目标值的设定值/保护回读与恢复，以及空载 ON→OFF；
  随后由独立会话复核最终状态。
- 同日受控注入首次输出写结果不明、保护事务第二/第三写失败、`APPLy` 回读不一致和
  `APPLy` 恢复结果不明，五个场景均得到预期的错误传播、保守恢复/强制 OFF 与必要锁存，
  且每轮由独立会话复核最终状态。
- 该证据仅覆盖 DP832A 协议和恢复语义，不外推其他型号，不证明带载瞬态或测量准确度。

## M3：设备选件与非消费型健康快照

### 覆盖指令

```text
*OPT?
*STB?
*TST?
SYSTem:VERSion?
SYSTem:OTP?
SYSTem:SELF:TEST:BOARD? [TOP|BOTTOM]
SYSTem:SELF:TEST:FAN?
SYSTem:SELF:TEST:TEMP?
STATus:QUEStionable:CONDition?                         # 仅适用型号
STATus:QUEStionable:INSTrument:ISUMmary<n>:CONDition? # 多通道型号
```

### 边界

- capability 只返回结构化选件、SCPI 版本、自检和当前 condition；不保存序列号、MAC/IP。
- `*STB?` 和 `...:CONDition?` 不清事件位，可进入 snapshot。
- `*ESR?`、`:STATus:...:EVENt?` 会清事件位，不进入 snapshot；`*CLS` 继续禁止。
- `*TST?` 只在手册和实机确认它是读取开机自检结果、不会启动新的破坏性自检后开放。
- 单通道和多通道状态树不同，必须按 model profile 选择命令，不能全部盲发。

### 完成门槛

- 模型/选件枚举、bit mask 和温度有限数严格解析；未知选件保留为 unknown token，不误报支持。
- DP832A 全快照零写入通过，并证明未读取消费型事件寄存器。

## M4：通道功能 profile（Range、Sense、Track）

### 覆盖指令

```text
INSTrument[:SELect]?
INSTrument:NSELect?
OUTPut:RANGe?                     # 仅 DP811A/DP811
OUTPut:SENSe? CH<n>               # 支持通道或返回 NONE
OUTPut:TRACk[:STATe]? CH<n>       # 支持通道或返回 NONE
SYSTem:TRACKMode?
SYSTem:ONOFFSync?
```

### 开发内容与边界

- 新 profile 只查询当前选择通道、Range/Sense/Track/同步状态，不改变 current-channel。
- `NONE` 表示该通道不支持，不包装成 `OFF`。
- DP811 Range、DP821 Sense、DP831/DP832 Track 分别使用型号和通道表门控。
- 本阶段不公开 Range/Sense/Track 写入：Range 会改变安全范围，Sense 需要远端取样接线，
  Track 和 ON/OFF sync 会联动多个通道。

### 完成门槛

- 每个支持/不支持型号和通道均有离线矩阵测试。
- DP832A 三通道零写入 profile 通过；Track/Sense 的实机返回与手册适用表一致。

## M5：Timer 零写入 profile

### 覆盖指令

```text
INSTrument[:SELect]?
TIMEr:CYCLEs?
TIMEr:ENDState?
TIMEr:GROUPs?
TIMEr:PARAmeter? <first>[,<count>]
TIMEr[:STATe]?
TIMEr:TEMPlet:FALLRate?
TIMEr:TEMPlet:INTErval?
TIMEr:TEMPlet:INVErt?
TIMEr:TEMPlet:MAXValue?
TIMEr:TEMPlet:MINValue?
TIMEr:TEMPlet:OBJect?
TIMEr:TEMPlet:PERIod?
TIMEr:TEMPlet:POINTs?
TIMEr:TEMPlet:RISERate?
TIMEr:TEMPlet:SELect?
TIMEr:TEMPlet:SYMMetry?
TIMEr:TEMPlet:WIDTh?
OUTPut:TIMEr? {P8V|P30V|N30V}              # 手册仅列这些量程名；需先验证型号适用性
OUTPut:TIMEr:STATe? {P8V|P30V|N30V}
```

### 设计约束

- 通用 `TIMEr:*?` 读取的是 current-channel，只返回该当前通道的完整快照，不为读取其他
  通道发送 `INSTrument:SELect` 写命令。
- 手册的 `OUTPut:TIMEr?` 语法只列 `P8V/P30V/N30V`，但同一手册把 DP832(A) 通道映射为
  `P30V/P30V2/P5V`。在实机只读诊断确认前，不把 `OUTPut:TIMEr?` 当作 DP832A 正式路径，
  也不猜测未记录的 `P30V2/P5V` 语法；正式 DP832A profile 先使用 current-channel 的
  `TIMEr:*?`。
- `TIMEr:PARAmeter?` 的 definite-length block 必须验证 `#<digits><length>`、组数、字段数、
  有限电压/电流、正时间和最大点数；`OUTPut:TIMEr?` 若在适用型号获准探测，则按普通
  分号分隔字符串解析。两种表面不能混为同一响应格式。
- 不发送任何 template 构建、参数写入或 timer ON/OFF。

### 完成门槛

- 解析正常、截断、超长、重复序号和越界组数均有离线测试。
- DP832A 在 timer OFF 状态完成零写入 snapshot；没有改变输出和 current-channel。

## M6：有限 Timer 配置与执行

### 覆盖指令

```text
INSTrument[:SELect] CH<n> / ?
TIMEr:GROUPs <count>
TIMEr:CYCLEs N,<count>
TIMEr:ENDState OFF
TIMEr:PARAmeter <index>,<voltage>,<current>,<seconds>
TIMEr[:STATe] ON|OFF / ?
OUTPut[:STATe] CH<n>,ON|OFF / ?
```

`OUTPut:TIMEr` / `OUTPut:TIMEr:STATe` 仅在 M5 先证明具体型号接受手册列出的量程名后，
才能作为该型号的等价补充路径；DP832A 首版不发送这两条命令。

### 安全契约

- 首版只允许有限循环 `N`，禁止 `I`；终止状态强制 `OFF`，不接受 `LAST`。
- 每步电压、电流、功率和总时长经过核心 safety limit；点数和总运行时间有硬上限。
- 只接受 timer、delay 和目标通道输出最初都为 OFF 的会话；不接管正在运行的用户序列。
- 保存原 current-channel、目标通道 `APPLy?` 设定值、完整有效 timer 表、循环数、终止状态
  和输出状态。若原参数组数超过受支持的有界备份上限，则在首次写入前拒绝；配置阶段保持输出 OFF。
- 启动前再次确认 delay 已关闭；timer 与 delay 不能同时打开。
- 启动顺序固定为：配置并回读 Timer → 启动 Timer 并确认状态 → 完成安全复核与用户明确
  确认后才开启目标通道输出。运行设 watchdog；取消/超时/异常均在 `finally` 中先关闭
  目标输出并回读 OFF，再关闭 Timer 并确认停止，最后恢复原参数、设定值和 current-channel。
- 首写不明、停止未确认或恢复失败锁停整个实例，并要求人工确认输出。
- instrument template 写命令暂不公开；模板在主机端展开成已验证的显式参数表。

### 实机验收

- 先空载、低电压/低限流、两点、单循环；示波器或 DMM 独立确认输出时序。
- 验收后独立会话确认 timer OFF、三个通道输出目标态和原参数恢复。

## M7：Delay 零写入 profile

### 覆盖指令

```text
INSTrument[:SELect]?
DELAY:CYCLEs?
DELAY:ENDState?
DELAY:GROUPs?
DELAY:PARAmeter? <first>[,<count>]
DELAY[:STATe]?
DELAY:STATe:GEN?
DELAY:STOP?
DELAY:TIME:GEN?
```

### 边界与完成门槛

- 与 M5 一样，只读取 current-channel，不隐式切换通道。
- 参数 block 严格验证序号、ON/OFF、时间和长度；停止条件严格解析 `NONE`、电压/电流/
  功率比较符和有限阈值。
- DP832A 在 delay OFF 状态完成零写入 snapshot；不发送生成或启动命令。

## M8：有限 Delay 配置与执行

### 覆盖指令

```text
INSTrument[:SELect] CH<n> / ?
DELAY:GROUPs <count>
DELAY:CYCLEs N,<count>
DELAY:ENDState OFF
DELAY:PARAmeter <index>,ON|OFF,<seconds>
DELAY:STOP {NONE|<V|>V|<C|>C|<P|>P}[,<value>]
DELAY[:STATe] ON|OFF / ?
```

`DELAY:STATe:GEN` 和 `DELAY:TIME:GEN` 首版由主机端展开，不直接公开写入。

### 安全契约

- 只允许有限循环和 `ENDState OFF`；参数表必须以 OFF 开始并以 OFF 结束。
- 若使用停止条件，阈值必须落在当前通道额定值和核心 safety limit 内。
- 只接受 timer、delay 和目标通道输出最初都为 OFF 的会话；保存并恢复 current-channel、
  完整有效 delay 表、停止条件、输出和所有生成参数。若原参数组数超过受支持的有界备份
  上限，则在首次写入前拒绝；取消/超时走 finally-stop。恢复失败与停止未确认均锁停。
- 实机从空载、两步 OFF→ON→OFF、单循环开始，并用独立仪器确认时序。

## M9：Monitor profile 与受控联锁

### M9A 零写入 profile

```text
MONItor:CURRent:CONDition?
MONItor:CURRent[:VALue]?
MONItor:POWER:CONDition?
MONItor:POWER[:VALue]?
MONItor[:STATe]?
MONItor:STOPway?
MONItor:VOLTage:CONDition?
MONItor:VOLTage[:VALue]?
```

- 监测器按 `*OPT?` 和型号门控；只读取 current-channel，并将逻辑关系和停止方式解析成
  typed model。
- 零写入实机验收必须证明没有改变输出、告警或蜂鸣器。

### M9B 受控联锁

```text
MONItor:VOLTage:CONDition <condition>,<logic>
MONItor:VOLTage[:VALue] <value>
MONItor:CURRent:CONDition <condition>,<logic>
MONItor:CURRent[:VALue] <value>
MONItor:POWER:CONDition <condition>
MONItor:POWER[:VALue] <value>
MONItor:STOPway {OUTOFF|WARN|BEEPER},ON|OFF
MONItor[:STATe] ON|OFF
```

- 首版只允许可证明更安全的 `OUTOFF`，WARN/BEEPER 不作为安全关闭替代。
- 写前保存全部条件、阈值、三种独立停止方式和 monitor 状态；阈值关系与当前设定/保护值预检。
- 必须先在输出 OFF 下配置并回读，再由用户显式启用；禁用和恢复放入 `finally`。
- 实机验收需要可控负载或模拟条件，证明触发后输出确实关闭；仅收到命令响应不算通过。

## M10：Recorder 与 Analyzer 的 artifact 生命周期

### M10A 零写入状态

```text
RECorder:DESTination?
RECorder:PERIod?
RECorder[:STATe]?
MEMory[:STATe]:VALid? ROF,<slot>
ANALyzer:FILE?
ANALyzer:OBJect?
ANALyzer:STARTTime?
ANALyzer:ENDTime?
ANALyzer:CURRTime?
ANALyzer:RESult?
ANALyzer:VALue? <time>
```

- `ANALyzer:*?` 仅在已经打开有效文件时调用；无文件是明确前置失败，不伪装为空结果。
- 文件路径在公开 artifact 中脱敏；响应大小和时间索引有上限。

### M10B 有界录制与分析

```text
RECorder:PERIod <seconds>
RECorder:MEMory <slot>,<filename>
RECorder[:STATe] ON|OFF
ANALyzer:MEMory <slot>
ANALyzer:OBJect V|C|P
ANALyzer:STARTTime <seconds>
ANALyzer:ENDTime <seconds>
ANALyzer:ANALyze
ANALyzer:RESult?
```

- 只接受 recorder 原本为 OFF 的会话，不接管或停止正在进行的用户录制。
- 只允许专用、空闲且通过 `MEMory:STATe:VALid? ROF,<slot>` 确认状态、又经用户明确允许
  覆盖的内部槽；首版不写外部 `MMEMory` 路径。
- 录制时长、周期和估算点数有上限；停止录制会写文件，必须显式告知。
- 保存原 recorder/analyzer 状态；超时或取消必须停止 recorder，且结束后 recorder 保持
  OFF。分析只针对本次创建并验证的文件，不任意打开用户文件；生成的内部 artifact 及
  覆盖行为写入结果元数据。
- 文件删除、任意路径、覆盖未知槽和 `MMEMory:*` 继续默认拒绝。

## M11：Trigger 拓扑只读审计

只有 `*OPT?` 确认 Trigger 选件、物理 D0–D3 接口和电平已核对后，才执行以下查询：

```text
TRIGger[:SEQuence]:SOURce?
TRIGger[:SEQuence]:DELay?
TRIGger:IN:CHTYpe?
TRIGger:IN[:ENABle]? D0|D1|D2|D3
TRIGger:IN:RESPonse? D0|D1|D2|D3
TRIGger:IN:SENSitivity? D0|D1|D2|D3
TRIGger:IN:SOURce? D0|D1|D2|D3
TRIGger:IN:TYPE? D0|D1|D2|D3
TRIGger:OUT[:ENABle]? D0|D1|D2|D3
TRIGger:OUT:CONDition? D0|D1|D2|D3
TRIGger:OUT:DUTY? D0|D1|D2|D3
TRIGger:OUT:PERIod? D0|D1|D2|D3
TRIGger:OUT:POLArity? D0|D1|D2|D3
TRIGger:OUT:SIGNal? D0|D1|D2|D3
TRIGger:OUT:SOURce? D0|D1|D2|D3
```

本阶段明确不发送 `:INITiate`、`:TRIGger:IN:IMMEdiate`、`*TRG`，不设置 triggered
voltage/current，也不启用任何输入/输出线。查询通过后仍只得到拓扑快照，不代表触发执行
能力通过。真正的触发执行需要独立硬件治具、电平认证、输出恢复和新里程碑授权。

## M12：多型号回归与发布收口

- 建立型号/通道/选件矩阵，至少区分 DP811、DP821、DP831、DP832 及 A/非 A 变体。
- 每个 capability 明确支持、返回 unavailable 或拒绝，不能向不支持型号盲发命令。
- 运行完整核心与插件测试、Ruff、package check、wheel/sdist 内容检查和生命周期 dry-run。
- 更新中英文覆盖矩阵、里程碑和 changelog；真实地址、序列号、快照和原始日志不进入提交。
- 版本、提交、push、tag 和发布仍由用户分别授权。

## 长期默认拒绝或另案授权的指令

以下指令不属于普通实验 capability；“手册存在”不是实现理由：

- 复位/调用/预设：`*RST`、`*RCL`、`:PRESet[:APPLy]`、`:RECAll:*`、
  `:MEMory:*:LOAD`。
- 持久存储和删除：`*SAV`、`:STORe:*`、`:MEMory:*:STORe/DELete/LOCK`、
  `:MMEMory:STORe/LOAD/DELete/MDIRectory`。
- 网络与接口写入：`:SYSTem:COMMunicate:LAN:*`、GPIB/RS232 配置；避免实验会话自行断网。
- 许可证：`:LIC:SET`。
- 清除保护：`:OUTPut:OVP:CLEAR`、`:OUTPut:OCP:CLEAR` 和会重新打开输出的
  `:SOURce:*:PROTection:CLEar`；只允许独立、人工确认故障已排除的恢复流程。
- 消费型状态操作：`*CLS`、`*ESR?`、`:STATus:*:EVENt?`；如未来需要，必须作为明确
  “读取并清除”的诊断 API。
- 前面板和全局行为写入：display/text、language、beeper immediate、lock/remote、power-on、
  ON/OFF sync 和跟踪模式；除非有独立需求和恢复契约。
- 无限 timer/delay 循环、终止状态 `LAST`、任意文件路径和未经确认的存储槽覆盖。

## 每个里程碑的发布门槛

任何新 capability 只有同时具备以下证据，才能在矩阵中标为“实机通过”：

1. 公共 typed model 与序列化格式；
2. driver protocol、capability 映射和 descriptor 声明；
3. Service/CLI 在打开 transport 前完成缺失 capability 和高风险参数检查；
4. 精确 FakeTransport 查询/写入序列、异常回包、超时、回读不一致和恢复失败测试；
5. 当前版本 wheel 生命周期和 sdist 隐私边界测试；
6. 真实仪器命令接受与解析证据；
7. 所有写入的不同值回读、恢复和独立会话终态证据；
8. 涉及输出时的独立测量证据，以及准确度结论所需的专门治具。

诊断探针、同值写回、一次成功响应或核心安全检查本身，都不能替代上述门槛。
