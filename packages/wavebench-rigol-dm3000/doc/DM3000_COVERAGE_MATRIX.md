# DM3000 编程手册功能覆盖矩阵

[English](DM3000_COVERAGE_MATRIX_EN.md)

本页将 DM3000 编程手册的功能域映射到外置 `wavebench-rigol-dm3000` 插件当前公开的
WaveBench capability 和 SCPI 表面。当前包版本、依赖和入口点以 [包元数据](../pyproject.toml)
为准，型号、transport、配置字段和 capability 以
[production descriptor](../src/wavebench_rigol_dm3000/descriptor.py) 为准，精确命令、解析和
事务行为以 [driver](../src/wavebench_rigol_dm3000/driver.py) 为准。

[功能覆盖里程碑](DM3000_COVERAGE_MILESTONES.md)记录诊断探针、实机协议验收、开发顺序和
退出门。该页面用于追溯，不会独立增加当前 capability。手册或本矩阵出现一条命令，也不表示
production descriptor 已经公开对应能力。

## 范围

审计输入为文档编号 `PGC01010-1110` 的 DM3000 系列编程手册。手册封面列出
DM3061/2/3/4 与 DM3051/2/3/4，没有单独列出 DM3058，因此手册不能作为 DM3058
兼容性的唯一依据。本地转录只用于内部审计，位于 Git 忽略且不进入 wheel／sdist 的
`doc/vendor-local/`。

本矩阵按功能域说明当前覆盖，不用转录标题或 set/query 变体计算完成率。外置插件是经配置的
TCPIP／PyVISA 窄驱动，不是通用 DM3000 SCPI shell。短 alias `dm3000` / `dm3058`
仍指向 Core 内建 fallback；其 serial 支持不属于此外置包的 transport 覆盖。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开覆盖 | 当前边界 |
|---|---|---|---|
| 身份 | `*IDN?` | `dmm.idn` | 返回原始字符串；不把型号、序列号或固件解析为公开结构化字段。 |
| 整机复位 | `*RST` | 未公开 | 会改变测量、触发、运算和全局状态，默认拒绝。 |
| 命令集切换 | `CMDSET RIGOL/AGILENT/FULUKE`、`CMDSET?` | 未公开 | 会改变整机命令语法；插件固定使用 RIGOL 命令集。手册还存在 `FULUKE`／`FLUKE` 拼写歧义。 |
| 当前测量功能 | `:FUNCtion?` | `dmm.function_status` | 只接受明确支持的长／短符号；未知回包抛出 `DataError`，`RATIO` 不在当前映射中。 |
| 基础功能选择 | DCV、ACV、DCI、ACI、RES、FRES、FREQ、PERIOD、CONT、DIODE、CAP | `dmm.set_function` | 写入后用 `:FUNCtion?` 回读；不设置量程、分辨率、触发或等待稳定。 |
| 直流电压比率 | `:FUNCtion:VOLTage:DC:RATIO`、`:MEASure:VOLTage:DC:RATIO?` | 未公开 | 需要双输入和独立结果语义，不能塞入普通单值映射。 |
| 11 类标量读数 | 各功能的 `:MEASure:<function>?` | `dmm.read` | 只发送目标 query，不先切换功能；非有限数会被拒绝，有限回包不代表测量准确度。 |
| 自动／手动测量 | `:MEASure AUTO|MANU`、`:MEASure?` | 未公开 | 会改变连续测量行为；本手册中的 `:MEASure?` 表示完成状态，不是读数。 |
| 量程 | 各功能的 `:RANGe?` 和 `:MEASure:<function> <range>` | `dmm.measurement_profile` 只读离散 `range_code`；`dmm.set_voltage_range` 只覆盖当前 DCV／ACV 和代码 `0..4` | 写量程会切到手动模式，但设备没有对应模式 query。写入失败后即使量程恢复，也会锁停当前实例。 |
| 输入阻抗、AC filter 与副屏频率 | DCV `:IMPedance`、ACV `:FILTer`、ACV／ACI `:FREQ:*` | profile 只读 DCV 阻抗；`dmm.set_dcv_impedance` 设置 `10M/10G` | setter 不切换功能或量程；`10G` 只允许 range code `0..2`。AC filter／frequency 字段未公开。 |
| 显示位数与测量精度 | `:DIGit*`、`:RESolution:*` | 未公开 | 显示位数不等于采集分辨率；型号与固件语义不足，不能从手册外推。 |
| 系统与接口只读状态 | beeper、language、format、brightness、option serial、DHCP、GPIB、RS-232 | `dmm.system_interface_status` | 全有或全无的脱敏只读快照；不读取 MAC、IP、hostname、clock、raw IDN 或原始响应，也不发送配置写入。 |
| 上电、默认值与接口配置 | power-on/default、LAN/GPIB/RS-232 写入 | 未公开 | 会改变持久状态或断开当前 session，默认拒绝。 |
| 触发系统 | source、auto interval/hold、single count、external、VMC | `dmm.trigger_status` | 只读现有状态；不执行 trigger，也不改变 source 或产生 VMC 输出。 |
| 运算与统计 | mode、count、min/max/average、dB/dBm reference | `dmm.calculation_status`、`dmm.calculation_statistics` | 统计读取要求调用方明确确认，并再次核对当前运算模式；不会隐式启用、清空或触发。NULL／dB／dBm／limit setter 未公开。 |
| Datalog | status、configure、run/stop、binary fetch | 未公开 | 当前没有可靠状态和二进制格式合同；启动、停止和配置还会改变采集状态。 |
| 巡检板与工程 | `:SCAN:*` | 未公开 | 依赖选件，并包含工程保存／加载／删除和多通道运行副作用。 |
| Agilent／Fluke 兼容命令集 | 兼容 SCPI 与短命令 | 未公开 | 需要全局切换命令集，不能作为当前 RIGOL driver 的免费 alias。 |

## 当前直接使用的 SCPI 表面

以下是当前外置插件源码可能发送的仪器命令。它不是原始通信日志，也不表示每条命令都单独
完成了实机验收。

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

:MEASure:VOLTage:DC:RANGe?
:MEASure:VOLTage:AC:RANGe?
:MEASure:CURRent:DC:RANGe?
:MEASure:CURRent:AC:RANGe?
:MEASure:RESistance:RANGe?
:MEASure:FRESistance:RANGe?
:MEASure:FREQuency:RANGe?
:MEASure:PERiod:RANGe?
:MEASure:CAPacitance:RANGe?
:MEASure:VOLTage:DC:IMPedance?
:MEASure:VOLTage:DC <0..4>
:MEASure:VOLTage:AC <0..4>
:MEASure:VOLTage:DC:IMPedance <10M|10G>

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

:TRIGger:SOURce?
:TRIGger:AUTO:INTerval?
:TRIGger:AUTO:HOLD?
:TRIGger:AUTO:HOLD:SENSitivity?
:TRIGger:SINGle?
:TRIGger:EXT?
:TRIGger:VMComplete:POLar?
:TRIGger:VMComplete:PULSewidth?

:CALCulate:FUNCtion?
:CALCulate:STATistic:COUNt?
:CALCulate:STATistic:MIN?
:CALCulate:STATistic:MAX?
:CALCulate:STATistic:AVERage?
:CALCulate:DB:REFerence?
:CALCulate:DBM:REFerence?

:SYSTem:BEEPer:STATe?
:SYSTem:LANGuage?
:SYSTem:FORMat:DECimal?
:SYSTem:FORMat:SEParate?
:SYSTem:DISPlay:BRIGht?
:SYSTem:SCANserial?
:SYSTem:LANserial?
:UTILity:INTerface:LAN:DHCP?
:UTILity:INTerface:GPIB:ADDRess?
:UTILity:INTerface:RS232:BAUD?
:UTILity:INTerface:RS232:PARity?
```

实现不会发送 `*RST`、`CMDSET`、resolution、trigger／calculation 写入、Datalog、scan、
interface 或 error-queue 命令，也没有通用 raw-SCPI 入口。`dmm.set_function` 的完整事务是
一条功能选择写入和一条 `:FUNCtion?` 回读；`dmm.read` 只发送一条测量 query。

## 测量功能映射

| Public function | 功能选择 | 读数 query | 单位 |
|---|---|---|---|
| `dcv` / `vdc` | `:FUNCtion:VOLTage:DC` | `:MEASure:VOLTage:DC?` | V |
| `acv` / `vac` | `:FUNCtion:VOLTage:AC` | `:MEASure:VOLTage:AC?` | V |
| `dci` / `idc` | `:FUNCtion:CURRent:DC` | `:MEASure:CURRent:DC?` | A |
| `aci` / `iac` | `:FUNCtion:CURRent:AC` | `:MEASure:CURRent:AC?` | A |
| `res` / `ohm` / `2wr` | `:FUNCtion:RESistance` | `:MEASure:RESistance?` | ohm |
| `fres` / `4wr` | `:FUNCtion:FRESistance` | `:MEASure:FRESistance?` | ohm |
| `freq` | `:FUNCtion:FREQuency` | `:MEASure:FREQuency?` | Hz |
| `period` | `:FUNCtion:PERiod` | `:MEASure:PERiod?` | s |
| `continuity` / `cont` | `:FUNCtion:CONTinuity` | `:MEASure:CONTinuity?` | ohm |
| `diode` | `:FUNCtion:DIODe` | `:MEASure:DIODe?` | V |
| `cap` | `:FUNCtion:CAPacitance` | `:MEASure:CAPacitance?` | F |
| ratio | 未公开 | 未公开 | 未定义 |

## 行为与安全边界

- descriptor 在打开 transport 前拒绝非 `pyvisa`、非 `TCPIP`、serial、ASRL、USB 和 GPIB 配置。
- `dmm.read` 不隐式切换功能；调用方需要先确认或设置当前功能。
- 配置写入使用回读和恢复；首写结果不明、回读失败或恢复无法确认时，当前实例会锁停后续配置写入。
- descriptor 校验和有限数解析不证明接线正确、测量准确度或整个 DM3000 系列兼容。

## 相关来源

- [Production descriptor](../src/wavebench_rigol_dm3000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dm3000/driver.py)
- [功能覆盖里程碑与实机证据](DM3000_COVERAGE_MILESTONES.md)
