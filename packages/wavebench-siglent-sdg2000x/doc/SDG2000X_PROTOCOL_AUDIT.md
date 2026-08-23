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
| `C<n>:SYNC?` | 同步状态与源类型 | 后续专用同步模型 | 双通道 A3 通过，未开放 |
| `C<n>:ARWV?`、`C<n>:SRATE?`、`STL? BUILDIN` | 当前任意波选择、DDS/TARB 状态与内置目录 | `source.arbitrary_probe` 固定白名单 | 已开放，只读且不访问用户目录 |
| `C<n>:HARM?`、`C<n>:CMBN?`、`C<n>:NOISE_ADD?`、`COUP?` | 状态依赖的高级输出上下文 | 基础写与 Output 安全门禁 | 内部使用；无独立写 capability |
| `FCNT?`、`ROSC?`、`MODE?`、`VOLTPRT?`、`CASCADE?` | Counter、时钟、相位模式、保护和多机状态 | 后续独立全局 facet | A3 零写通过，未开放 |

其中 `<n>` 只能是 `1` 或 `2`。M2 读取顺序冻结为身份校验、`OUTP?`、`BSWV?`、`SWWV?`；整个操作不得发送写命令。

## 已开放的写事务

E05C 的 Output Command 定义 `C<n>:OUTP ON|OFF`。M3 将该命令映射为主仓库 `source.output`，不暴露通用原始 SCPI 入口。

E05C 的 Basic Wave Command 定义 `WVTP`、`FRQ`、`AMP` 与 `DUTY` 写入。当前分别映射为 `source.set_function`、`source.set_frequency`、`source.set_amplitude_vpp` 与 `source.set_square_duty_cycle`。函数限于 Sine、Square、Ramp、Pulse、Noise 与 DC；Noise/DC 只允许输出 OFF 配置。频率按型号与当前波形限制为 1 µHz 至对应上限；幅度限制为 2 mVpp 至 10 Vpp；占空比只适用于 FIX 模式方波。

事务边界如下：

- `set_output(channel, enabled, *, check_errors=True) -> SourceStatus` 与核心 `SourceDriver` 接口一致。
- 由于手册未定义错误队列，`check_errors` 必须显式为 `false`；其它值在任何 I/O 前拒绝。
- ON 之前必须完整读取 `SourceStatus`，并确认 FIX、Sweep OFF、Vpp 幅度和偏置均已知。Vpp 上限由核心 `SourceService` 检查。
- 幂等调用不写入。其它调用只发送一次目标命令，随后重新读取完整状态，并确认非输出字段不变。
- 任何写后失败都锁止本会话后续 ON，并执行一次 OFF 恢复与 `OUTP?` 回读。恢复失败时报告输出状态不确定；锁止状态下仍允许紧急 OFF。

三个已登记型号均按同一手册命令合同放行 `source.output`。fake transport 已覆盖三种身份；实机证据目前仅来自 `SDG2122X` 固件 `2.01.01.39R7T2`。完整证据见[输出控制实机验收](SDG2000X_OUTPUT_ACCEPTANCE.md)。

## 固件实测扩展

`SDG2122X` 固件 `2.01.01.39R7T2` 的 `OUTP?` 在 E05C 已记录字段之外返回 `POWERON_STATE,ON|OFF`。解析器只接受该封闭枚举，并继续要求 `LOAD` 与 `PLRT`。该字段不映射到核心 `SourceStatus`，也不据此扩张 capability。完整边界见[只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)。

## 主仓库接口映射

当前 descriptor 还声明 `source.snapshot_v2`、`source.basic_configure_v2` 与 `source.output_v2`。这三项只完成
A0 离线适配，不以既有 V1 实机记录替代 V2 的 A1–A3。状态和基础写返回主仓库公开的
`wavebench.instruments.SourceStatus`；任意波探测返回 `ArbitraryQueryProbeResult` 列表。状态字段映射如下：

### Source V2 A0 适配

Source V2 snapshot 只使用已经审计的 `*IDN?`、`OUTP?`、`BSWV?`、`SWWV?` 和高级状态查询；它不会发送
selector 或配置写入。两个 anchor phase 中，Output facet 复用同通道 Basic 快照，避免额外读取。A0 Sine
fixture 的完整计划为 38 次查询、0 次写入，descriptor 上限为 42。

V2 Basic MAIN 仅复用已验证的 `BSWV WVTP`、`BSWV FRQ`、`BSWV AMP` 和 `BSWV DUTY` 写入。每个请求只接受
一个字段；`BSWV OFST` 尚未具有独立写入证据，因此 `offset_v` 在 I/O 前拒绝。V2 Output MAIN 仅使用
`OUTP ON|OFF`。写后状态由核心发起新的 snapshot 回读，driver 不在 MAIN 阶段附带查询。

Noise 的 `STDEV` 不是最终 Vpp。当前插件不会用它构造 V2 输出开启依据，也不会将它换算为 Vpp。旧 V1
`set_function` 的 Noise/DC 路径因此保留原有输出 OFF 事务；可由 V2 profile 完整表达的周期波继续使用 V2。

Harmonic Command 仅在基础波形为 SINE 时可用。驱动因此采用状态依赖查询：非 SINE 快照不发送 `HARM?`；切回 SINE 时重新查询，以捕获可能重新生效的遗留谐波状态。该行为已由实机超时负向证据和故障测试确认。

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
- 尚未开放的写 capability：Sweep、Burst、trigger 和任意波写入。
- 调制、谐波、Pulse、Combine、Coupling、Sync、Counter、时钟与 Cascade 只有分域证据，不因开发验收而暴露 raw 写入口。
- raw SCPI：不提供绕过 capability、transport 守卫和参数校验的入口。

## 离线验收标准

- fake transport 覆盖 CH1 与 CH2，且完整状态读取的写命令列表始终为空。
- 数值单位必须显式解析；非有限值、未知单位、错误通道头、缺失必需字段和重复字段均抛出 `DataError`。
- descriptor 声明的 capability 必须通过主仓库 `validate_declared_capabilities`。
- fake transport 覆盖 CH1/CH2、ON/OFF、幂等、三个型号身份、回读不符、状态漂移、歧义写入、OFF 恢复、恢复失败和会话锁止。
- 核心 `SourceService` 安全测试要求 10 Vpp 边界允许、10.0001 Vpp 在零写入条件下拒绝。
- 版本 `0.8.0` 的 SDG 插件源码达到 620/620 statements、244/244 branches；348 项插件测试通过。新增 Source V2 代码以当前离线测试和覆盖率报告为准。
- wheel 隔离安装、entry point 发现、sdist 厂商资料排除和仓库全量 `895 passed, 2 skipped` 通过。
