# DM3000 编程手册功能覆盖矩阵

[English](DM3000_COVERAGE_MATRIX_EN.md)

实机协议验收命令清单、通过/失败证据和后续实施顺序见
[DM3000 功能覆盖里程碑](DM3000_COVERAGE_MILESTONES.md)。诊断探针用于筛选后续功能，
不等同于当前插件已经公开相应 capability。

## 目的、范围与统计口径

本矩阵将本地保存的 RIGOL DM3000 中文编程手册与外置
`wavebench-rigol-dm3000` 插件的公开 capability、实际 SCPI、离线测试和已记录的
DM3058 LAN 实机证据逐项对照。它回答“手册提供了什么”“插件实际公开了什么”和
“每项结论有什么级别的证据”，不把手册中存在一条命令、Python 方法存在或一次相邻功能
验收自动等同于完整功能覆盖。

审计输入为文档编号 `PGC01010-1110` 的 DM3000 系列编程手册。当前 Markdown 转录为
4,017 行，位于本包被 Git 忽略的 `doc/vendor-local/`；该目录不进入提交、wheel 或
sdist。手册封面列出 DM3061/2/3/4 与 DM3051/2/3/4，没有单独点名实机 DM3058。
因此，本矩阵把手册作为 DM3000 系列协议资料，而 DM3058 兼容性只按当前代码、真实固件
回包和已记录的实机证据认定，不能把整本手册无条件外推到 DM3058。

手册第 2 章将 RIGOL 命令分为常用、功能、测量、精度、系统、应用/接口、触发、运算、
数据采集和巡检十个域；第 3 章另列 Agilent 与 Fluke 兼容命令集。转录中存在缺失标题、
命令名断裂和明显复制错误，例如 RS-232 parity 小节重复了 baud 命令。因此，本矩阵按
可审计的功能域和公开 capability 报告状态，不用标题数量计算伪精确的完成百分比。

当前外置插件版本为 `0.1.0`，只声明四项 capability：`dmm.idn`、`dmm.read`、
`dmm.function_status` 和 `dmm.set_function`。它是经配置的 TCPIP/PyVISA LAN 窄驱动，
不是通用 DM3000 SCPI shell，也不公开 error-queue、reset、range、trigger、datalog、
scan 或接口配置入口。短 alias `dm3000` / `dm3058` 仍指向 WaveBench 内建 fallback；
其 serial 支持不能计作此外置包的 transport 覆盖。

覆盖标签：

- **外置实机通过**：当前外置插件、离线实现和受控 DM3058 LAN 实机证据均存在。
- **已实现 / 离线验证**：代码和针对性 FakeTransport 测试存在，但没有该细项的外置实机结论。
- **已实现 / 离线部分验证**：代码路径存在，但测试只精确断言了该命令族的一部分。
- **未覆盖**：手册有命令，但当前公开插件没有相应 capability 或方法。
- **默认拒绝**：命令会切换协议、重置仪器、改变连接、写持久状态或启动复杂采集，不应由普通工作流暴露。
- **资料不确定**：转录或手册本身存在明显歧义，不能在无额外资料和实机证据时实现。

## 功能覆盖矩阵

| 功能域 | 手册命令面 | 当前公开覆盖 | 证据状态 | 主要缺口与安全边界 | 建议 |
|---|---|---|---|---|---|
| 身份查询 | `*IDN?` | `dmm.idn` 直接查询并返回原始字符串 | **外置实机通过**：迁移验收和重装后 smoke 均有 DM3058 IDN 证据；精确单查询有离线测试 | 不解析型号、序列号或固件为结构化字段；公开文档不保存真实值 | 保持窄查询；如需结构化 identity，先定义脱敏 artifact |
| 整机复位 | `*RST` | 未公开 | **默认拒绝** | 恢复出厂默认值，会改变整机测量、触发、运算和接口相关状态 | 不纳入普通 DMM workflow；仅考虑独立维护命令与人工确认 |
| 命令集切换 | `CMDSET RIGOL/AGILENT/FULUKE`、`CMDSET?` | 未公开 | **默认拒绝 / 资料不确定** | 会切换整台仪器的命令语法；手册还同时出现 `FULUKE` 与 `FLUKE` 拼写 | 插件固定使用 RIGOL 命令集；不得用 raw SCPI 绕过 |
| 当前测量功能 | `:FUNCtion?` | `dmm.function_status`；规范化长返回符号及实机观察到的 `RES`、`2WR`、`4WR`、`FREQ`、`PERI`、`CONT`、`CAP` 等短符号 | **外置实机通过**；短符号解析有选择性离线测试 | 当前 parser 不接受手册中的 `RATIO`；未知回包明确抛 `DataError` | 扩展新模式前先取得真实回包，并增加逐项 parser 测试 |
| 基础功能选择 | `:FUNCtion:VOLTage:DC/AC`、`CURRent:DC/AC`、`RESistance`、`FRESistance`、`FREQuency`、`PERiod`、`CONTinuity`、`DIODe`、`CAPacitance` | `dmm.set_function` 支持上述 11 类，写入后用 `:FUNCtion?` 回读 | **外置实机通过**：DCV↔ACV；另有 2026-07-26 受控诊断证据证明 DCV→FREQ/PERIOD→DCV 可恢复且读数有限。其余映射为**离线部分验证** | 不设置量程、分辨率、触发或等待稳定；电流/电阻/通断/二极管/电容仍无安全实机矩阵 | **P1**：为 11 类 selector 增加参数化精确命令测试；实机扩展必须逐类可恢复验收 |
| 直流电压比率功能 | `:FUNCtion:VOLTage:DC:RATIO`、`:MEASure:VOLTage:DC:RATIO?` | 未公开，`RATIO` 状态也未被 parser 接受 | **未覆盖** | 需要两路输入，结果无普通单位；不能塞入现有单值功能映射而不定义输入和返回语义 | 单独设计 ratio capability 后再考虑 |
| 11 类标量读数 | `:MEASure:VOLTage:DC/AC?`、`CURRent:DC/AC?`、`RESistance?`、`FRESistance?`、`FREQuency?`、`PERiod?`、`CONTinuity?`、`DIODe?`、`CAPacitance?` | `dmm.read` 返回公共 `DmmReading(function, value, unit, raw)` | **DCV 外置实机通过（20/20 有限值）**；2026-07-26 另确认 ACV、FREQ、PERIOD 在正确模式下返回有限值；11 条精确 query 和单位映射均有参数化离线测试 | `read(function=...)` 只发送查询，不先切换功能；电流/电阻/通断/二极管/电容仍未实机验收。当前 parser 也未显式拒绝 `NaN`/`inf` | 文档化“先确认/设置功能”的前置条件；**P1** 增加有限值校验与模式一致性策略 |
| 自动/手动测量方式 | `:MEASure AUTO|MANU`、`:MEASure?` | 未公开 | **未覆盖** | 会改变连续测量行为；`MEASure?` 在本手册中表示完成状态，不是读数 | 仅在明确 acquisition state model 后实现 |
| 量程与自动量程 | 各功能的 `:MEASure:<function> <range>`、`:RANGe?` | 未公开 | **未覆盖 API；受控探针通过**：DM3058 的 DCV/ACV 量程查询、不同安全档位写入、回读和恢复通过；FREQ/PERIOD 量程查询通过 | 写量程会切换为手动；不同功能档位编号、上限和默认值不同，且不能从一次实机探针推导通用 API | **M2/M3**：先做当前功能 profile；setter 使用逐功能档位表、回读、恢复和失败锁存 |
| 输入阻抗、交流滤波和副屏频率 | DCV `:IMPedance`、ACV `:FILTer`、ACV/ACI `:FREQ:*` | 未公开 | **未覆盖 API**；DM3058 的 DCV 10 MΩ/10 GΩ 不同值切换和恢复通过；本轮 ACV filter/frequency 查询无响应 | 输入阻抗和滤波会改变测量结果；display/hide 改前面板状态，且 ACI 小节命名存在 `hide/state` 不一致 | M2 先暴露 DCV 只读阻抗；M3 再考虑独立、可恢复 setter |
| 显示位数 | 各功能 `:DIGit?` / `:DIGit INC|DEC|5|6|7` | 未公开 | **未覆盖；当前 DM3058 无响应**：DCV/ACV/FREQ/PERIOD 的 query 均未得到完整响应 | 改显示位数不等于改变采样精度，不能与 resolution 混为同一 capability | 除非有不同固件证据和明确价值，否则保持未实现 |
| 测量精度 | `:RESolution:*` 八个功能族 | 未公开 | **未覆盖；当前 DM3058 无响应**：本轮 DCV/ACV query 未得到完整响应 | 手册用离散 0/1/2 表示 4½/5½/6½ 位；型号能力可能不同 | 不从手册外推 DM3058；等待不同固件或型号证据 |
| 系统诊断查询 | `:SYSTem:SCANSerial?`、`MACAddr?`、`LANSerial?`、`OPENtimes?` | 未公开 | **未覆盖 API；查询探针部分通过**：选件/接口标识可解析；MAC 只做格式校验；`OPENtimes?` 数值语义异常，未通过 | 可能用于 option/接口门控，但 MAC 属于敏感设备标识，不应进入默认 artifact | 如有明确门控需求，设计脱敏、query-only 的 identity extension |
| 蜂鸣器、语言、时钟和显示 | `:SYSTem:BEEPer*`、`LANGuage`、`CLOCk:*`、`DISPlay:*`、`FORMat:*` | 未公开 | **未覆盖 API**；DM3058 蜂鸣器状态/语言/格式/亮度查询通过，蜂鸣器状态和亮度受控恢复通过；时钟和对比度查询无响应 | 改小数点/分隔符可能破坏解析；全局前面板写入仍不属于普通测量 API | M5 仅考虑只读、脱敏状态；格式/语言/时钟写入继续拒绝 |
| 上电与系统默认 | `:SYSTem:CONFigure:POWeron`、`:SYSTem:CONFigure:DEFault` | 未公开 | **默认拒绝** | 会改变持久或整机状态 | 仅限人工维护流程 |
| LAN/GPIB/RS-232 设置 | `:UTILity:INTerface:LAN:*`、`GPIB:ADDRess`、`RS232:BAUD/PARity` | 未公开 | **写入默认拒绝；查询探针部分通过**：LAN DHCP/IP/mask/gateway/DNS、GPIB address、RS-232 baud/parity 可读；hostname/domain 无响应 | 修改接口会断开会话；parity 小节在转录中错误重复 baud 命令。外置包本身仅允许 TCPIP/PyVISA | M5 可做脱敏 query-only 状态；网络和串口参数永不经普通测量工作流写入 |
| 触发系统 | `:TRIGger:SOURce`、auto interval/hold、single count/triggered、external、VMC polarity/pulsewidth | 未公开 | **未覆盖 API；查询探针通过**：八项状态可解析；hold/sensitivity/single/ext/VMC pulsewidth 的不同值写入和恢复通过。`AUTO:INTerval` setter 被设备忽略，未通过 | 会改变采样时序或产生 VMC 输出；没有执行 trigger action 或改变 source | **M4**：先定义 query-only trigger profile；setter 逐项评审，禁用 auto interval setter |
| 数学函数与统计 | `:CALCulate:FUNCtion`、min/max/average/count | 未公开 | **未覆盖 API；受控探针通过**：AVERAGE/MIN/MAX/TOTAL 模式、对应有限查询和恢复到 NONE 通过 | 统计 query 依赖已激活的运算和当前测量序列；一次探针不等于公开 setter | **M4**：先读已有状态/统计，不得隐式启用、清空或触发 |
| NULL、dB、dBm 与 limit | `:CALCulate:NULL:OFFSet`、`DB[:REFerence]`、`DBM[:REFerence]`、`LIMit:*` | 未公开 | **未覆盖** | setter 改变后续读数语义；参考值和单位依赖当前测量功能 | 只作为独立、可快照与恢复的 calculation profile |
| Datalog 配置与状态 | `:DATAlog?`、`CONFigure:*`、`RUN`、`STOP` | 未公开 | **默认拒绝写入；当前 DM3058 查询无响应** | 本轮状态和配置查询均未得到完整响应；启动/停止和配置还有明显状态副作用 | **M7 阻塞**：等待支持设备和可靠只读状态，再讨论有上限、超时、停止和恢复的采集 |
| Datalog 二进制读取 | `:DATAlog:FETCHdata <packet>` | 未公开 | **未覆盖 / 资料不确定** | 每包 512 个 32-bit 数据，手册要求厂商驱动/DLL 转换且需结合配置判断有效点数；不是普通 ASCII query | 在确认端序、数据格式和无 DLL 解码方法前不实现 |
| 巡检板与工程 | `:SCAN:*`，包括 task/project/run/fetch/save/load/delete/cardID | 未公开 | **默认拒绝；当前设备明确无巡检板且查询无响应** | 创建、保存、加载、删除工程有持久副作用，run/stop 控制多通道采集 | **M7 阻塞**：等待带选件设备，再以 `SCANSerial?`/`cardID?` 门控独立 capability |
| Agilent 兼容命令集 | `CALCulate`、`CONFigure`、`SENSe`、`TRIGger`、`DATA`、`MEMory` 等兼容 SCPI | 未公开 | **默认拒绝** | 需先全局切换 `CMDSET AGILENT`；不同语法不能与当前 RIGOL driver 混用 | 不作为“免费别名”计入覆盖；若支持应是独立 driver/profile |
| Fluke 兼容命令集 | `VDC`、`VAC`、`ADC`、`AAC`、`OHMS`、`MEAS?` 等 | 未公开 | **默认拒绝** | 同样需要切换整机命令集；短命令语义和返回格式不同 | 不混入当前 capability |

## 当前直接使用的 SCPI 表面

以下是当前外置插件源码实际可能发送的全部仪器命令，按实现拼写列出。它不是原始通信
日志，也不表示每条命令都完成了实机验收。

```text
*IDN?
:FUNCtion?

:MEASure:VOLTage:DC?
:MEASure:VOLTage:AC?
:MEASure:CURRent:DC?
:MEASure:CURRent:AC?
:MEASure:RESistance?
:MEASure:FRESistance?
:MEASure:FREQuency?
:MEASure:PERiod?
:MEASure:CONTinuity?
:MEASure:DIODe?
:MEASure:CAPacitance?

:FUNCtion:VOLTage:DC
:FUNCtion:VOLTage:AC
:FUNCtion:CURRent:DC
:FUNCtion:CURRent:AC
:FUNCtion:RESistance
:FUNCtion:FRESistance
:FUNCtion:FREQuency
:FUNCtion:PERiod
:FUNCtion:CONTinuity
:FUNCtion:DIODe
:FUNCtion:CAPacitance
```

实现不会发送 `*RST`、`CMDSET`、range、resolution、trigger、calculate、datalog、scan、
interface 或 error-queue 命令，也没有通用 raw-SCPI 入口。`dmm.set_function` 的完整事务
是“一条功能选择写入 + 一条 `:FUNCtion?` 回读”；`dmm.read` 则只有一条测量 query。

## 逐测量类型证据

| 公共 function | 功能选择 | 读数 query | 单位 | 离线证据 | 外置实机证据 |
|---|---|---|---|---|---|
| `dcv` / `vdc` | `:FUNCtion:VOLTage:DC` | `:MEASure:VOLTage:DC?` | V | query 与单位精确测试；selector 映射存在 | **20/20 有限值读取通过**；参与可恢复跨电压切换 |
| `acv` / `vac` | `:FUNCtion:VOLTage:AC` | `:MEASure:VOLTage:AC?` | V | query/单位及 ACV selector 精确测试 | 可恢复功能切换、有限读数、量程切换和恢复通过；不代表准确度验收 |
| `dci` / `idc` | `:FUNCtion:CURRent:DC` | `:MEASure:CURRent:DC?` | A | query 与单位精确测试；selector 映射存在 | 无 |
| `aci` / `iac` | `:FUNCtion:CURRent:AC` | `:MEASure:CURRent:AC?` | A | query 与单位精确测试；selector 映射存在 | 无 |
| `res` / `ohm` / `2wr` | `:FUNCtion:RESistance` | `:MEASure:RESistance?` | ohm | query 与单位精确测试；长/短状态解析有测试 | 无 |
| `fres` / `4wr` | `:FUNCtion:FRESistance` | `:MEASure:FRESistance?` | ohm | query 与单位精确测试；短状态解析有测试 | 无 |
| `freq` | `:FUNCtion:FREQuency` | `:MEASure:FREQuency?` | Hz | query 与单位精确测试；短状态解析有测试 | 可恢复功能切换、有限读数和输入电压量程查询通过；不代表准确度验收 |
| `period` | `:FUNCtion:PERiod` | `:MEASure:PERiod?` | s | query 与单位精确测试；短状态解析有测试 | 可恢复功能切换、有限读数和输入电压量程查询通过；不代表准确度验收 |
| `continuity` / `cont` | `:FUNCtion:CONTinuity` | `:MEASure:CONTinuity?` | ohm | query 与单位精确测试；短状态解析有测试 | 无 |
| `diode` | `:FUNCtion:DIODe` | `:MEASure:DIODe?` | V | query 与单位精确测试；selector 映射存在 | 无 |
| `cap` | `:FUNCtion:CAPacitance` | `:MEASure:CAPacitance?` | F | query 与单位精确测试；短状态解析有测试 | 无 |
| ratio | 未公开 | 未公开 | 未定义 | 无 | 无 |

## WaveBench 提供、但不计入手册命令覆盖的保障

- descriptor 在 transport 打开前限制为 `pyvisa` + `TCPIP`，并拒绝 serial、ASRL、USB
  和 GPIB；这是插件边界，不是某条 DM3000 SCPI 的实现。
- capability preflight、会话生命周期、读取前等待、run-plan artifact 和 `expect` 数值判断
  由 WaveBench 核心负责，不能计作手册命令覆盖。
- descriptor capability 校验只证明声明的方法存在且可调用，不证明 SCPI 语义、仪器回包、
  接线正确或数值准确。
- `set_function` 的回读能证明仪器报告了目标模式，但不证明输入端子、量程、分辨率、滤波、
  触发和被测信号都适合下一次测量。

## 推荐路线

详细阶段、命令和发布门槛见[功能覆盖里程碑](DM3000_COVERAGE_MILESTONES.md)。总体顺序为：

1. **P1：收紧现有四项能力。** 为 11 类 selector 增加参数化精确命令测试；拒绝非有限读数；
   明确 `dmm.read` 不隐式切换功能，并考虑可选的“目标功能必须与状态一致”前置检查。
2. **P1：增加当前测量 profile 的 query-only 快照。** 优先覆盖 function、range、resolution，
   再按功能补 impedance/filter；未知或不适用字段必须显式为 unavailable。
3. **P2：受控量程/精度设置。** 每个 setter 都需要功能门控、参数表、写后回读、失败语义和
   可恢复的事务，不用通用整数 range API 掩盖各功能差异。
4. **P2：已有统计与触发状态只读。** 只读取已配置的 calculate/trigger 状态，不隐式启用、
   清空、触发或重置仪器。
5. **P3：Datalog。** 先解决二进制格式、端序、有效点数、大小上限、超时、stop/finally 和
   artifact；巡检板应是 option-gated 的独立能力。
6. **默认不做：命令集切换、reset/default、网络/串口设置和 scan project 持久写入。**
   这些操作需要与普通测量流程不同的权限和人工确认。

## 证据边界

- **手册侧**：本地 `vendor-local` 转录仅用于内部审计，本文不复制整本手册，也不将其打入
  发行包。转录歧义不会被当作可靠协议事实。
- **实现侧**：外置插件的 `driver.py`、`descriptor.py`、FakeTransport 测试以及
  WaveBench 公共 DMM service/run-plan 契约。
- **外置实机侧**：2026-07-24 的受管安装/路由/DCV 记录，以及 2026-07-26 的查询和
  可恢复写入协议验收。后者覆盖 ACV/FREQ/PERIOD 有限读数、DCV/ACV 量程、DCV 阻抗、
  trigger query、已有统计、部分系统/接口 query；完整清单见里程碑。没有保存真实地址、
  序列号或具体读数。
- **未验收侧**：测量准确度、DCI/ACI/电阻/通断/二极管/电容、digits/resolution、
  Datalog、scan 和兼容命令集仍不得宣称通过；诊断探针也不等于公开 capability。

只有当前外置代码、针对性离线测试、真实仪器命令接受/回读，以及必要时的原状态恢复都存在，
某一项才可提升为“外置实机通过”。
