# DP800 编程手册功能覆盖矩阵

[English](DP800_COVERAGE_MATRIX_EN.md)

本页将 DP800 编程手册的功能域映射到外置 `wavebench-rigol-dp800` 插件当前公开的
WaveBench capability 和 SCPI 表面。当前包版本、依赖和入口点以[包元数据](../pyproject.toml)
为准，型号、通道、配置字段和 capability 以
[production descriptor](../src/wavebench_rigol_dp800/descriptor.py) 为准，精确命令、解析和
事务行为以 [driver](../src/wavebench_rigol_dp800/driver.py) 为准。

[指令覆盖开发里程碑](DP800_COVERAGE_MILESTONES.md)记录开发顺序、实机验收和退出门。
该页面用于追溯，不会独立增加当前 capability。手册或本矩阵出现一条命令，也不表示
production descriptor 已经公开对应能力。

## 范围

审计输入为文档编号 `PGH03008-1110` 的 RIGOL DP800 系列编程手册。手册覆盖多个型号、
A／非 A 变体、通道数、量程和选件，因此型号参数不能外推给 DP832A，DP832A 证据也不能
外推给整个系列。本地转录只用于内部审计，位于 Git 忽略且不进入 wheel／sdist 的
`doc/vendor-local/`。

本矩阵按 22 个手册功能域说明当前覆盖，不用 set/query 变体、短写或 alias 计算完成率。
外置插件是受安全策略约束的窄电源驱动，不是通用 DP800 SCPI shell。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开覆盖 | 当前边界 |
|---|---|---|---|
| 身份与错误队列 | `*IDN?`、`:SYSTem:ERRor?`、`:SYSTem:VERSion?` | `power.idn`；配置写入可按设置读取错误队列 | `errors()` 会消费队列；没有结构化型号／固件或非消费型 health。 |
| IEEE 488.2 状态、复位与触发 | `*CLS`、状态寄存器、`*OPC?`、`*RST`、`*TRG`、`*TST?` | 除 `*IDN?` 外未公开 | reset、trigger 和清状态具有全局或输出副作用，默认拒绝。 |
| 基础设定值 | `:APPLy` / `:APPLy?` | `power.status`；`power.set_voltage_current_limit` | 写前保存电压／电流，单次写入后回读；失败时恢复。结果不明或恢复无法确认会锁停配置写入。 |
| 实时测量 | `:MEASure:ALL?` 及标量 query | `power.measurement`；`power.status` 复用同一快照 | 使用单次 `:MEAS:ALL? CH<n>`；不公开独立标量 query，也不声明测量准确度。 |
| 输出状态与 CV／CC 模式 | `:OUTPut[:STATe]?`、`:OUTPut:CVCC?` / `:OUTPut:MODE?` | `power.status` | 未知 output／regulation 枚举会失败，不向未确认型号外推。 |
| 显式输出开关 | `:OUTPut[:STATe] [CH<n>,]ON|OFF` | `power.output` | 直接影响被测电路。驱动写一次并回读；失败时强制 OFF，不盲目重试 ON。 |
| OVP／OCP | state、threshold、trip、clear | `power.protection` 读取并配置 state／threshold／trip | 配置按安全顺序逐项写入和回读；恢复时不会清除新 trip。Clear 命令未公开。 |
| `SOURce` 设定与保护 alias | level、step、triggered level、protection、range | 没有独立 API；立即设定值和保护使用 `APPLy`／`OUTPut` 路径 | 不公开 step、triggered level、DP811 range 或 protection clear；alias 不重复计算覆盖。 |
| Range、Sense 与 Track | `:OUTPut:RANGe/SENSe/TRACk` | 未公开 | 型号／通道相关；Range 改变安全范围，Sense 依赖远端接线，Track 联动通道。 |
| Timer 与 Delay | `:TIMEr:*`、`:OUTPut:TIMEr*`、`:DELAY:*` | 未公开 | 可按时间或条件改变真实输出；当前单点快照不足以恢复，启动默认拒绝。 |
| Monitor | `:MONItor:*` | 未公开 | 条件与动作可能关闭输出或报警，并可能依赖选件。 |
| Trigger 与 `INITiate` | `:TRIGger:*`、`:INITiate`、`*TRG` | 未公开 | 可改变触发电平、切换输出、驱动数字端口或耦合通道，默认拒绝。 |
| 当前通道选择 | `:INSTrument:NSELect/SELect` | 刻意不使用 | 当前 API 在每条命令显式传递 `CH<n>`，避免引入隐藏的全局 current-channel 状态。 |
| Recorder 与 Analyzer | `:RECorder:*`、`:ANALyzer:*` | 未公开 | 依赖选件和文件生命周期，且启停、选择文件和运行分析会改变状态。 |
| 内部状态、preset 与外部文件 | `:MEMory:*`、`:PRESet:*`、`:RECAll:*`、`:STORe:*`、`:MMEMory:*`、`*SAV/*RCL` | 未公开 | 保存、覆盖、删除、调用和加载均有持久副作用，默认拒绝。 |
| 显示与前面板 | `:DISPlay:*`、brightness、contrast、lock/local/remote | 未公开 | 会改变全局 UI 或妨碍人工接管；普通测量流程不写前面板。 |
| 系统诊断与状态 | self-test、SCPI version、`:STATus:QUEStionable:*` | 未公开 | 部分事件 query 会清位，自检运行条件和时延尚无公开合同。 |
| 通信与全局设置 | LAN、serial、GPIB、language、power-on、OTP、channel sync | 未公开 | 网络写入可能断开 session，其余操作改变持久或全局状态，默认拒绝。 |
| 许可证与选件安装 | `:LIC:SET` | 未公开 | 属于设备维护并改变持久状态，默认拒绝。 |

## 当前直接使用的 SCPI 表面

以下命令按手册长写形式归一化；实现使用兼容短写。这不是原始通信日志，也不表示每条命令
都单独完成了准确度或全型号验收。

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

`power.status` 依次读取 `APPLy?`、`MEASure:ALL?`、output state 和 regulation mode；
`power.protection` 依次读取六个保护字段。中途查询失败时，不返回不完整的公共模型。

## 行为与安全边界

- Core 负责 voltage／current safety limit、OVP／OCP 关系、输出开启前检查、run plan 和
  实验级恢复；这些规则不计作 DP800 SCPI 覆盖。
- 当前命令始终显式指定通道，不修改隐藏的 current-channel 状态。
- 多写事务失败时尝试恢复原快照；首次写入结果不明、trip 改变或恢复无法确认时，当前实例
  会锁停后续配置写入。
- settle delay、有限数解析和 descriptor 校验不证明输出已经稳定、接线正确、测量准确或
  整个 DP800 系列兼容。

## 相关来源

- [Production descriptor](../src/wavebench_rigol_dp800/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dp800/driver.py)
- [开发里程碑与实机证据](DP800_COVERAGE_MILESTONES.md)
