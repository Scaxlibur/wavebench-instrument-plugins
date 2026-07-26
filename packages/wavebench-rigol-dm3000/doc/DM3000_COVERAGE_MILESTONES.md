# DM3000 功能覆盖里程碑

[English](DM3000_COVERAGE_MILESTONES_EN.md)

本文把 DM3000 编程手册中的命令面拆成可实施、可验收的里程碑，并记录
2026-07-26 在一台 DM3058 上完成的 LAN 协议验收。它是
[功能覆盖矩阵](DM3000_COVERAGE_MATRIX.md)的执行计划，不是通用 raw-SCPI 白名单。

手册封面列出 DM3061/2/3/4 与 DM3051/2/3/4，没有单独列出 DM3058。因此下述实机结论
只证明当前 DM3058 固件接受了相应命令，不能自动外推到整个 DM3000 系列。验收记录不保存
真实地址、序列号或具体测量值。

## 验收口径

协议验收与测量准确度验收分开：

- **查询通过**：命令在限定时间内返回，响应能按已定义的类型或枚举解析；测量值还必须为
  有限数，不能是 `NaN` 或无穷大。
- **有响应、语义待确认**：响应可读取，但数值或字段语义明显可疑，不能提升为正式支持。
- **受控写入通过**：先读取原值，写入一个不同且安全的目标值，回读确认目标值，再在
  `finally` 路径恢复原值并再次回读确认。只做“同值写回”不算通过。
- **无响应**：独立会话内查询超时或没有完整响应。该结果不证明所有同系列型号都不支持，
  但当前 DM3058 不得宣称通过。
- **跳过**：前置条件不存在或风险不可接受，例如未安装巡检板，或当前外部接线不允许进入
  电流、电阻、通断、二极管、电容模式。

每条失败查询后都关闭会话再继续；没有发送 `*CLS` 或读取错误队列。首次写入若出现超时或
状态不明，后续写入必须锁停。本轮没有发生写入超时，所有已执行的受控变更均恢复成功。

本轮只证明命令、解析和恢复契约，不证明量程准确度、输入阻抗准确度、频率准确度或校准
状态。最终状态核验为 DCV、原 DCV/ACV 量程、10 MΩ 输入、AUTO 触发和运算关闭。

## 实机协议验收摘要

### 已接受的查询

以下查询在当前 DM3058 上得到可解析响应。只有当前插件公开的七项 capability 才属于正式
API；其余命令是为里程碑筛选而执行的受控诊断探针。

| 域 | 已接受命令 | 备注 |
|---|---|---|
| 身份与命令集 | `*IDN?`、`CMDSET?` | IDN 脱敏；命令集返回 RIGOL。没有执行命令集切换 |
| 当前功能与完成状态 | `:FUNCtion?`、`:MEASure?` | 当前功能和测量完成状态均可解析 |
| DCV | `:MEASure:VOLTage:DC?`、`:MEASure:VOLTage:DC:RANGe?`、`:MEASure:VOLTage:DC:IMPedance?` | 读数有限；量程和阻抗可解析 |
| ACV | `:MEASure:VOLTage:AC?`、`:MEASure:VOLTage:AC:RANGe?` | 在显式选择 ACV 后验证，读数有限 |
| 频率 | `:MEASure:FREQuency?`、`:MEASure:FREQuency:RANGe?` | 在显式选择频率功能后验证，读数有限 |
| 周期 | `:MEASure:PERiod?`、`:MEASure:PERiod:RANGe?` | 在显式选择周期功能后验证，读数有限 |
| 系统状态 | `:SYSTem:BEEPer:STATe?`、`:SYSTem:LANGuage?`、`:SYSTem:FORMat:DECimal?`、`:SYSTem:FORMat:SEParate?`、`:SYSTem:DISPlay:BRIGht?` | 查询可解析；格式写入仍默认拒绝 |
| 选件与标识 | `:SYSTem:SCANserial?`、`:SYSTem:MACaddr?`、`:SYSTem:LANserial?` | 巡检板和接口模块均报告未安装；MAC 仅做格式校验，不落盘 |
| 接口状态 | `:UTILity:INTerface:LAN:DHCP?`、`IP?`、`MASK?`、`GATEway?`、`DNS?`、`:UTILity:INTerface:GPIB:ADDRess?`、`:UTILity:INTerface:RS232:BAUD?`、`:UTILity:INTerface:RS232:PARity?` | 只读；没有修改任何连接参数。`PARity?` 是针对手册复制错误的诊断拼写 |
| 触发状态 | `:TRIGger:SOURce?`、`:TRIGger:AUTO:INTerval?`、`:TRIGger:AUTO:HOLD?`、`:TRIGger:AUTO:HOLD:SENSitivity?`、`:TRIGger:SINGle?`、`:TRIGger:EXT?`、`:TRIGger:VMComplete:POLar?`、`:TRIGger:VMComplete:PULSewidth?` | 带 `ms` 的返回已按单位解析 |
| 运算状态 | `:CALCulate:FUNCtion?`、`:CALCulate:STATistic:COUNt?`、`:CALCulate:DB:REFerence?`、`:CALCulate:DBM:REFerence?` | count 可能以科学计数法返回，应按有限非负数解析 |
| 已启用统计 | `:CALCulate:STATistic:AVERage?`、`:CALCulate:STATistic:MIN?`、`:CALCulate:STATistic:MAX?` | 仅在受控启用对应运算后查询，返回有限数 |

`:SYSTem:OPENtimes?` 有整数响应，但数值异常大，当前只记为“有响应、语义待确认”，不得作为
可信开机次数公开。

### 已通过的受控写入与恢复

| 功能 | 写入面 | 验收结果 |
|---|---|---|
| 电压端功能选择 | `:FUNCtion:VOLTage:AC`、`:FUNCtion:FREQuency`、`:FUNCtion:PERiod`、恢复 `:FUNCtion:VOLTage:DC` | 目标功能回读、对应有限读数和恢复均通过 |
| DCV 输入阻抗 | `:MEASure:VOLTage:DC:IMPedance 10M/10G` | 不同值切换、回读和恢复通过；10 GΩ 仅在低 DCV 量程使用 |
| DCV 量程 | `:MEASure:VOLTage:DC <range>` | 安全相邻量程切换、有限读数和恢复通过 |
| ACV 量程 | `:MEASure:VOLTage:AC <range>` | 安全相邻量程切换、有限读数和恢复通过 |
| 蜂鸣器状态 | `:SYSTem:BEEPer:STATe ON/OFF` | 状态切换和恢复通过；没有发送蜂鸣器测试命令 |
| 显示亮度 | `:SYSTem:DISPlay:BRIGht <value>` | 单步变化、回读和恢复通过 |
| 触发参数 | `:TRIGger:AUTO:HOLD`、`...:SENSitivity`、`:TRIGger:SINGle`、`:TRIGger:EXT`、`:TRIGger:VMComplete:PULSewidth` | 均完成不同值写入、回读和恢复；没有执行手动触发或改变触发源 |
| 运算模式 | `:CALCulate:FUNCtion AVERAGE/MIN/MAX/TOTAL`，恢复 `NONE` | 模式回读、对应有限统计查询和恢复通过 |

`:TRIGger:AUTO:INTerval 200` 没有改变设备状态，回读仍为 `400ms`；恢复路径正常。因此该
查询可用，但 setter 在当前 DM3058 上记为**未通过**，不得进入受支持写入 API。

### 当前无响应或不应实现

| 域 | 当前结果 |
|---|---|
| 显示位数与精度 | DCV/ACV/FREQ/PERIOD 的 `:DIGit?` 以及 DCV/ACV `:RESolution:*?` 无响应 |
| ACV 扩展 | `:FILTer?`、`:FREQuency?`、`:FREQuency:STATe?` 无响应；独立 FREQ 功能仍可用 |
| 时钟和对比度 | `:SYSTem:CLOCK:STATe?`、`DATE?`、`TIME?`、`:SYSTem:DISPlaycontrast?` 无响应 |
| LAN 文本字段 | `:UTILity:INTerface:LAN:HOST?`、`DOMain?` 无响应 |
| 运算扩展 | `:CALCulate:NULL:OFFSet?`、`:CALCulate:LIMit:LOWer?`、`UPPer?` 无响应 |
| Datalog | `:DATAlog?` 及本轮尝试的全部 `:DATAlog:CONFigure:*?` 无响应 |
| 巡检 | `:SCAN:CURRent:CYCLE?`、`:SCAN:CURRent:PROJname?` 无响应；设备还明确报告未安装巡检板 |
| 高风险维护 | `*RST`、`CMDSET <set>`、网络/GPIB/RS-232 写入、默认/上电配置、日期时间写入继续默认拒绝 |
| 接线相关功能 | DCI、ACI、二/四线电阻、通断、二极管、电容和 ratio 未执行实机切换；需要先移除外部电压或建立专用安全治具 |

## 覆盖里程碑

### M0：命令清点与证据边界 — 完成

- 中英文覆盖矩阵已经对照常用、功能、测量、精度、系统、接口、触发、运算、Datalog、
  巡检及兼容命令集。
- 厂商手册只保存在 `doc/vendor-local/`，并由 wheel 与 sdist 显式排除。
- DM3058 实机证据和手册型号边界分开记录。

### M1：原有四项 capability 收紧 — 完成

原有能力为 `dmm.idn`、`dmm.read`、`dmm.function_status`、`dmm.set_function`。

- 已实机确认 IDN、当前功能、DCV/ACV/FREQ/PERIOD 有限读数和电压端功能恢复。
- `dmm.read` 已显式拒绝 `NaN`/`inf`，11 类 selector 均有精确离线测试。
- 11 类功能均按开放探针标准完成实机切换、有限读数和逐次恢复；不代表测量准确度验收。
- 可选的“目标 function 必须与当前功能一致”前置检查未纳入本轮范围。

### M2：只读测量 profile — 完成

新增 `dmm.measurement_profile`，只查询当前功能适用且已验收的字段：

- 共通：`:FUNCtion?`；
- DCV：离散量程码和输入阻抗；
- ACV/DCI/ACI/RES/FRES/FREQ/PERIOD/CAP：离散量程码；
- CONT/DIODE：不发送未验收的量程 query，返回 unavailable。

该路径不切换功能、不读取测量值、不读取 `:MEASure?` 或错误队列，也不把离散档位码
伪装成 SI 量程上限。无响应的 digits/resolution/filter 字段未加入模型。

### M3：受控电压端配置 — 完成

已分别公开 DCV/ACV 量程和 DCV 输入阻抗，而不是一个通用整数 setter：

- 写前读取当前功能和目标字段；
- 每种功能使用自己的档位表；
- 写后回读；失败时恢复；恢复失败锁存该实例的配置写路径；
- 不隐式修改触发、运算、显示、格式或接口状态。
- 手册确认 `range_code=0` 是最小量程而非自动量程；由于 `:MEASure AUTO|MANU` 没有
  对应 query，profile 的 `auto_range` 返回 unavailable。
- DCV/ACV 档位限制为 `0..4`；DCV `10G` 阻抗仅允许档位 `0..2`。
- 范围写入会强制手动测量。失败后即使原档位恢复，也无法证明原测量方式恢复，因此锁停
  当前实例的后续配置写入。

2026-07-26 在当前 DM3058 上完成 0.3.0 受控实机验收：DCV 与 ACV 均完成档位码
`0 -> 1 -> 0` 的写入、回读和恢复；DCV 输入阻抗完成 `10M -> 10G -> 10M` 的写入、
回读和恢复；`10G` 下请求 DCV 档位码 `3` 在首个配置写入前被拒绝，仪器状态保持不变。
最终状态核验为 DCV、档位码 `0`、`10M`。该证据只证明协议、约束和恢复行为，不证明
量程或输入阻抗准确度。

### M4：只读触发与已有统计 — 已实现；状态查询实机通过

- `dmm.trigger_status` 可覆盖本轮已接受的八个触发查询。
- `dmm.calculation_status` 可覆盖当前运算模式、count、dB/dBm reference。
- `dmm.calculation_statistics` 只在调用者确认对应运算已启用时读取 min/max/average；不得
  隐式启用、清空或触发测量。
- 受控 trigger/calculation setter 可后续单独评审；`AUTO:INTerval` setter 当前禁用。

0.4.0 在当前 DM3058 上完成零写入状态查询验收：`trigger_status` 依次返回
`AUTO`、400 ms、OFF、1、1、RISE、POS、7 ms；`calculation_status` 返回 NONE、count 0、
dB reference 0、dBm reference 600 Ω。当前没有 matching active calculation，因此没有执行
`calculation_statistics`；该路径仅由精确 FakeTransport 测试验证其“显式确认 + 当前模式复核”
门槛，绝不启用、清空或触发 calculation。

### M5：系统与接口只读状态 — 已实现；外置实机通过

0.5.0 以 `dmm.system_interface_status` 实现全有或全无的 11 字段脱敏快照；只发送已获
DM3058 零写入响应证据的 query。默认 artifact 不保存 IDN、MAC、IP、主机名、域名、时钟、
原始回包或资源地址。网络、GPIB、RS-232、格式、语言、日期时间、默认配置和上电配置的
写入继续禁止。RS-232 parity 小节在手册转录中误重复 baud 命令，当前实现只按 DM3058
实机经验接受 `none8bits/odd7bits/even7bits`。

0.5.0 源码在当前 DM3058 上完成完整快照验收：11/11 query 均返回可解析值，命令记录为
11 次 query、0 次 write。验收没有发送 IDN、MAC、IP、mask、gateway、DNS、hostname、
domain、clock、`*CLS` 或错误队列命令；只报告协议响应和脱敏状态，不保存真实地址、序列号
或原始回包。

### M6：其他电气测量模式 — 开放探针协议完成；准确度/治具验收待定

M1 已通过现有 `dmm.set_function` + `dmm.read` 完成 DCI、ACI、二/四线电阻、通断、二极管
和电容的开放探针协议验收：目标功能切换回读成功、读数回包完整可解析且有限、每次均恢复
DCV。按本里程碑的开放探针口径，M6 不再新增重复 capability 或重复协议实现。

该结论不证明测量准确度、端子接线、保险丝、量程、激励电流/电压或专用负载正确。
`RATIO` 仍未实现，因为它需要双输入与独立结果语义。正式准确度验收仍必须在确认端子、
信号源断开/接入策略、保险丝、量程和专用治具后逐类进行；不能用一次有限回包替代。

### M7：Datalog 与巡检 — 当前阻塞

- 当前 DM3058 的 Datalog 查询无响应，不能开始二进制包解码实现。
- 巡检板报告未安装，`SCAN` 查询也无响应。
- 在有支持设备、格式/端序资料、大小上限、停止/恢复契约前，不公开 capability。

因此 M7 的完成结论是“已审计并保持阻塞”，不是“设备或驱动失败”。当前硬件没有足够
响应证据支撑 query-only 状态模型，更没有授权实现 RUN/STOP、工程保存/加载/删除或二进制
抓取。不得为了到达里程碑编号而发送高副作用命令或把无响应包装成可选字段。

## 发布门槛

任何新 capability 只有同时具备公共 typed model、driver contract、descriptor 声明、
FakeTransport 精确命令测试、Service/CLI 前置检查、真实命令响应证据，以及写入项的恢复证据，
才能标记为实机通过。诊断探针本身不计作插件公开覆盖。
