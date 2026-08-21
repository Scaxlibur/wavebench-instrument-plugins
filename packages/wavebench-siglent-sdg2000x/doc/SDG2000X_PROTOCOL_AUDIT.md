# SDG2000X 协议审计

[English](SDG2000X_PROTOCOL_AUDIT_EN.md)

## 审计基线

- 编程手册：SIGLENT《SDG Series Programming Guide》，修订号 `PG02_E05C`，共 201 页。
- 本地文件：`doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`。
- SHA-256：`a27c841ef10ebeba8c437be88933079b358d80d55d20b0d3bbf032cbc8b7125d`。
- 辅助资料：`SDG2000X_UserManual_CN03A` 与 `SDG2000X_DataSheet_CN02H`。
- 支持型号：`SDG2042X`、`SDG2082X`、`SDG2122X`，均为双通道。

厂商 PDF 只保存在被 Git 和 sdist 排除的 `vendor-local/` 中。公开文档仅记录实现所需的命令事实和审计结论。

## 通信边界

编程手册记录了 USB 与 LAN 远程控制。LAN 可使用 VXI-11、Socket 或 Telnet：Socket 端口为 `5025`，Telnet 端口为 `5024`。Socket 示例要求 SCPI 命令以换行符 `\n` 结束。

当前插件只声明 WaveBench 已有的 `pyvisa` backend，不自行建立 Socket 或 Telnet 连接。传输创建、timeout、审计日志和资源访问限制继续由主仓库 `DriverContext` 与 transport 层负责。

`COMM_HEADER` 在手册的兼容性表中标记为不支持 SDG2000X，因此驱动不得发送全局格式切换命令。解析器直接接受手册定义的短响应头，并对缺失、重复或未知关键字段采取 fail-closed 策略。

## 已确认的查询

| 命令 | 已确认响应 | WaveBench 映射 | 当前决策 |
| --- | --- | --- | --- |
| `*IDN?` | 厂商、型号、序列号、固件；或 `*IDN,SDG,...` 格式 | `source.idn` | 已开放 |
| `C<n>:OUTP?` | 输出状态、负载、极性；SDG2122X 实测额外包含 `POWERON_STATE` | `SourceStatus.output`；其余字段严格校验，留待独立 profile | M2 使用 |
| `C<n>:BSWV?` | 当前基本波类型及其适用参数，数值携带单位 | `SourceStatus` 的函数、频率、幅度、偏置、相位、占空比和 `apply_raw` | M2 使用 |
| `C<n>:SWWV?` | `STATE,OFF`，或启用时返回完整 Sweep 参数 | `SourceStatus.frequency_mode` 与 `sweep_enabled` | M2 使用 |
| `C<n>:MDWV?` | `STATE,OFF`，或启用时返回调制类型与完整参数 | 后续调制 profile | 已审计，未开放 |
| `C<n>:BTWV?` | `STATE,OFF`，或启用时返回 Burst 与载波参数 | 后续 Burst profile | 已审计，未开放 |
| `C<n>:SYNC?` | 同步状态与源类型 | 后续专用同步模型 | 已审计，未开放 |

其中 `<n>` 只能是 `1` 或 `2`。M2 读取顺序冻结为身份校验、`OUTP?`、`BSWV?`、`SWWV?`；整个操作不得发送写命令。

## 固件实测扩展

`SDG2122X` 固件 `2.01.01.39R7T2` 的 `OUTP?` 在 E05C 已记录字段之外返回 `POWERON_STATE,ON|OFF`。解析器只接受该封闭枚举，并继续要求 `LOAD` 与 `PLRT`。该字段不映射到核心 `SourceStatus`，也不据此扩张 capability。完整边界见[只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)。

## 主仓库接口映射

M2 只声明 `source.status`，并返回主仓库公开的 `wavebench.instruments.SourceStatus`。字段映射如下：

| `SourceStatus` 字段 | SDG2000X 来源 |
| --- | --- |
| `channel` | 已验证的请求通道 |
| `output` | `OUTP?` 的 `ON` 或 `OFF` |
| `function` | `BSWV?` 的 `WVTP`，归一化为核心短枚举 |
| `frequency_hz` | 适用时读取 `FRQ`，统一换算为 Hz |
| `amplitude` | 适用时读取 `AMP` |
| `amplitude_unit` | `AMP` 按手册语义归一化为 `VPP` |
| `offset_v` | 适用时读取 `OFST`，统一换算为 V |
| `phase_deg` | 适用时读取 `PHSE` |
| `frequency_mode` | Sweep 开启时为 `SWE`，否则为 `FIX` |
| `sweep_enabled` | `SWWV?` 的 `STATE` |
| `apply_raw` | 原始、去除首尾空白的 `BSWV?` 响应 |
| `square_duty_cycle_percent` | 方波时读取 `DUTY`，否则为 `None` |

## 暂不开放

- `source.errors`：E05C 命令表未定义错误队列查询、空队列响应或消费语义。
- `source.channel_profile`：主仓库模型要求同步极性、marker 状态和 pulse hold 等完整字段；当前命令集没有无歧义的一对一映射。
- 所有写 capability：本阶段不发送输出、固定波、Sweep、Burst、trigger 或任意波写命令。
- raw SCPI：不提供绕过 capability、transport 守卫和参数校验的入口。

## 离线验收标准

- fake transport 覆盖 CH1 与 CH2，且完整状态读取的写命令列表始终为空。
- 数值单位必须显式解析；非有限值、未知单位、错误通道头、缺失必需字段和重复字段均抛出 `DataError`。
- descriptor 声明的 capability 必须通过主仓库 `validate_declared_capabilities`。
- wheel 隔离安装、entry point 发现、sdist 厂商资料排除和仓库全量测试必须通过。
