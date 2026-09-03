# DG4000 编程手册功能覆盖矩阵

[English](DG4000_COVERAGE_MATRIX_EN.md)

本页将 DG4000 编程手册的功能域映射到外置 `wavebench-rigol-dg4000` 插件当前公开的
WaveBench capability 和 SCPI 表面。当前包版本与入口点以 [包元数据](../pyproject.toml)为准，
型号、capability 和操作方向以 [production descriptor](../src/wavebench_rigol_dg4000/descriptor.py)
为准，精确命令与事务行为以 [driver](../src/wavebench_rigol_dg4000/driver.py) 为准。

[功能覆盖里程碑](DG4000_COVERAGE_MILESTONES.md)记录开发顺序、退出门和实机证据，
[`conformance/`](../conformance/) 保存机器可读证据。它们用于追溯，不会独立增加当前 capability。
命令出现在本矩阵中，也不表示 production descriptor 已经公开对应能力。

## 范围

审计输入为文档编号 `PGB04008-1110` 的 DG4000 系列中文编程手册。手册以 DG4162
给出部分参数示例，并说明范围会随型号、负载和频率变化，因此这些数值不能外推给 DG4202。
本地转录只用于内部审计，位于 Git 忽略且不进入 wheel／sdist 的 `doc/vendor-local/`。

本矩阵按可审计的功能域说明覆盖情况，不以 set/query 变体、短写或转录标题计算完成率。
`rigol.dg4202` 保留 legacy capability；`rigol.dg4202-v2` 额外公开受限 Sweep；
`rigol.dg4202-v2-workspace` 只公开 Source V2 读取／输出关闭基础和一项仪器级 volatile ARB
workspace 替换能力。三个入口都不是通用 DG4000 SCPI shell。

## 当前公开写入口

DG descriptor 设置 `v1_route_migration_enabled=false`。V2 capability 只通过显式 V2
入口调用，不接管 legacy V1 route；Sweep 和 volatile workspace 分别由两个独立 opt-in
descriptor 公开。

| Capability | 当前入口与边界 |
|---|---|
| `source.basic_configure_v2` | CLI `source basic-configure-v2`；run `source.basic_configure_v2`。目标输出必须 OFF，频率模式必须 FIX，并先取得 fresh V2 snapshot；每次只接受一个 Basic field。 |
| `source.basic_live_configure_v2` | CLI `source basic-live-configure-v2`；run `source.basic_live_configure_v2`。输出必须 ON、频率模式必须 FIX，且每次只能修改 frequency 或 Vpp 中的一个字段；禁止 output cycling。 |
| `source.output_v2` | CLI `source output-v2`；run `source.output_enable_v2` / `source.output_disable_v2`。Core 分别对 ON 和 OFF 执行 V2 preflight 与最终状态回读。 |
| `source.sweep_configure_v2` | 仅限 `rigol.dg4202-v2`；run `source.sweep_configure_v2`。输出必须 OFF，V2 snapshot 必须 fresh，Burst／Modulation 必须 OFF；配置后独立回读。 |
| `source.sweep_fire_v2` | 仅限 `rigol.dg4202-v2`；run `source.sweep_fire_v2`。必须复用同一 session 中已配置的 Sweep，当前通道输出必须 ON，触发源必须为 manual；不得盲目重试。 |
| `source.arbitrary_workspace_volatile_replace_v2` | 仅限 `rigol.dg4202-v2-workspace`。需要 CH1／CH2 的 fresh V2 snapshot 且两路输出均为 OFF；`workspace_id` 固定为 `volatile`，接受 2–16,384 点且 payload 不超过 32,768 bytes。写入没有 channel selector，不声明哪一路选择 USER，也不能回读或恢复此前内容；结果不明会锁停配置写入。 |
| Legacy V1 route | `source.set-*`、`source.output`、离散频响、`arb-load`、basic restore 与现有 artifact 保持 V1 合同。 |

基础和 Sweep descriptor 不公开 workspace 写入；workspace descriptor 的 `source.output_v2`
只提供读取和关闭方向。三个 production descriptor 都不公开 Burst、Coupling、Noise Overlay
或 Sync 写 capability。实机适用范围与尚未通过的故障门见
[功能覆盖里程碑](DG4000_COVERAGE_MILESTONES.md)。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开覆盖 | 当前边界 |
|---|---|---|---|
| 身份与错误队列 | `*IDN?`、`:SYSTem:ERRor?`、`:SYSTem:VERSion?` | `source.idn`、`source.errors` | `errors()` 会读取并消费队列；未公开 SCPI version、状态寄存器或非消费型 health API。 |
| IEEE 488.2 保存、复位与触发 | `*RCL`、`*RST`、`*SAV`、`*TRG` | 未公开 | 保存／调用会改写非易失状态，复位改变整机，`*TRG` 可启动 Sweep／Burst 输出，因此默认拒绝。 |
| CH1／CH2 基础状态 | output、function、frequency、voltage、offset、phase、Sweep state、apply、square duty | `source.status`；`source.snapshot_v2` 返回双通道类型化 Basic、输出状态及前后锚点 | V2 Output 不重复 `source.channel_profile` 已提供的 load／polarity；snapshot 不扩大自动恢复范围。 |
| 固定频率 | `[:SOURce<n>]:FREQuency[:FIXed]` | `source.set_frequency` | 事务先取得快照、切换 FIX、逐步回读，并在失败时执行 off-first 恢复；结果不明会锁停写入。 |
| 基础函数与方波占空比 | `FUNCtion[:SHAPe]`、square duty、`APPLy:*` | `source.set_function`、`source.set_square_duty_cycle` | 不公开 ramp symmetry、pulse 边沿、noise 参数或组合 `APPLy` 写入。 |
| 幅度、单位、偏移与相位 | `VOLTage`、`UNIT`、`OFFSet`、`HIGH`、`LOW`、`PHASe` | `source.set_amplitude_vpp`；状态读取 offset／phase | 公开写入采用 VPP；没有独立 offset／phase／high／low setter。实际范围仍受型号、频率和负载约束。 |
| 输出开关 | `OUTPut[<n>][:STATe]` | `source.output` | 只在调用方明确请求时切换；任意波上传不会隐式打开输出，驱动不会盲目重试 ON。 |
| 负载、极性、Noise Overlay 与 Sync | `OUTPut:LOAD/POLarity/NOISe/SYNC` | `source.channel_profile`；`source.snapshot_v2` 的类型化 Noise Overlay／Sync facet | 当前只读；basic restore 不恢复这些字段，也没有公开 setter。 |
| 双通道耦合 | `COUPling:*` | `source.snapshot_v2` 的 `CHANNEL_SET` facet | 当前只读；descriptor 不声明配置方向，也没有完整 target 与恢复事务。 |
| Sweep 与触发 | `SWEep:*`、frequency window、`*TRG` | `source.sweep_profile`；`source.snapshot_v2` 的 Sweep facet；`rigol.dg4202-v2` 的 configure／manual-fire | V2 不恢复完整 Sweep；raw immediate trigger 仍默认拒绝，opt-in 行为不迁移到 V1 route。 |
| Burst、Pulse、Marker、Harmonic | `BURSt:*`、`PULSe:*`、`MARKer:*`、`HARMonic:*` | `source.snapshot_v2` 提供只读 facet；Harmonic 为 `PARTIAL` | 不公开逐阶 Harmonic、Marker 写入或配置／触发 API；缺失字段不能由相邻证据补齐。 |
| 调制 | `MOD:*` | `source.channel_profile` 与 `source.snapshot_v2` 只读返回 state／type | 不公开模式专属参数或 setter；state／type 查询不等于调制控制能力。 |
| DAC14 任意波上传 | `TRACe:DATA:DAC VOLATILE,<binary-block>` | `source.arbitrary_upload` | 只接受校验后的 little-endian `DG4000DacBlock`；目标必须 OFF、FIX、Sweep OFF。上传覆盖 volatile USER 波表，无法恢复。 |
| Source V2 volatile workspace | `TRACe:DATA:DAC VOLATILE,<binary-block>` | `source.arbitrary_workspace_volatile_replace_v2`，仅限 `rigol.dg4202-v2-workspace` | 仪器级、无 channel selector；两路输出必须 OFF。只返回写入完成与 payload identity，不验证内容，也不能恢复此前 workspace。 |
| 任意波诊断查询 | `FUNC?`、`FUNC:USER?` 与候选 ARB／DATA query | `source.arbitrary_probe` | 只接受问号结尾的候选并记录错误队列；这是排障入口，不是稳定任意波 capability。 |
| 任意波编辑、float 与 DAC16 | `TRACe:DATA`、`DAC16`、`POINts`、`VALue`、`LOAD?` | 未公开 | 格式、字节序、内存生命周期和回读语义尚无公开合同。 |
| 频率计 | `COUNter:*` | `source.counter_profile`、`source.counter_configure_v2`、`source.counter_enable_v2`、`source.counter_measure_v2` | 配置每次只写一个字段；enable／disable 独立；只有启用后才测量。Auto、gate、HF、sensitivity、display、clear 未公开。 |
| 外接 PA | `PA:*` | 未公开 | 可能产生更高功率并写入持久状态，默认拒绝。 |
| 显示与截图 | `DISPlay:*`、`HCOPy:SDUMp:DATA?` | 未公开 | 显示写入改变全局前面板状态；截图尚无公开传输与格式合同。 |
| 内部状态槽 | `MEMory:*`、`*SAV/*RCL` | 未公开 | 可能覆盖、删除、锁定或调用用户状态，默认拒绝。 |
| 外部文件系统 | `MMEMory:*` | 未公开 | 路径、删除、覆盖和加载具有持久副作用，默认拒绝。 |
| 通信与全局设置 | LAN、USB class、language、key lock、beeper、power-on、reference oscillator、channel copy | 未公开 | 修改网络可能断开会话，其余操作改变全局状态，默认拒绝。 |
| preset、重启与关机 | `SYSTem:PRESet/RESTART/SHUTDOWN` | 未公开 | 会中断实验、丢失 session 或改变整机配置，默认拒绝。 |

## 当前直接使用的 SCPI 表面

以下命令按手册长写形式归一化；实现使用兼容短写。这不是原始通信日志，也不表示每条命令
都单独完成了实机验收。

```text
*IDN?
SYSTem:ERRor?
OUTPut<n>?
SOURce<n>:FUNCtion[:SHAPe]?
SOURce<n>:FREQuency[:FIXed]?
SOURce<n>:VOLTage?  SOURce<n>:VOLTage:UNIT?  SOURce<n>:VOLTage:OFFSet?
SOURce<n>:PHASe?  SOURce<n>:SWEep:STATe?  SOURce<n>:APPLy?
SOURce<n>:FUNCtion:SQUare:DCYCle?
OUTPut<n>:LOAD?  OUTPut<n>:POLarity?
OUTPut<n>:NOISe:STATe?  OUTPut<n>:NOISe:SCALe?
OUTPut<n>:SYNC:STATe?  OUTPut<n>:SYNC:POLarity?
COUPling[:STATe]?  COUPling:CHannel:BASE?
COUPling:AMPLitude:DEViation?  COUPling:FREQuency:DEViation?
COUPling:PHASe:DEViation?
SOURce<n>:BURSt:STATe?  SOURce<n>:MOD:STATe?  SOURce<n>:MOD:TYPe?
SOURce<n>:MARKer:STATe?  SOURce<n>:PULSe:HOLD?
SOURce<n>:FREQuency:STARt?  SOURce<n>:FREQuency:STOP?
SOURce<n>:FREQuency:CENTer?  SOURce<n>:FREQuency:SPAN?
SOURce<n>:SWEep:SPACing?  SOURce<n>:SWEep:STEP?  SOURce<n>:SWEep:TIME?
SOURce<n>:SWEep:HTIMe:STARt?  SOURce<n>:SWEep:HTIMe:STOP?
SOURce<n>:SWEep:RTIMe?  SOURce<n>:SWEep:TRIGger:SOURce?
SOURce<n>:SWEep:TRIGger:SLOPe?  SOURce<n>:SWEep:TRIGger:TRIGOut?
SOURce<n>:MARKer:FREQuency?
COUNter[:STATe]?  COUNter:MEASure?  COUNter:COUPing?  COUNter:IMPedance?
COUNter:ATTenuation?  COUNter:GATEtime?  COUNter:HF?  COUNter:LEVel?
COUNter:SENSitive?  COUNter:STATIstics:STATe?  COUNter:STATIstics:DISPlay?

OUTPut<n> ON|OFF
SOURce<n>:FREQuency[:FIXed] <frequency>
SOURce<n>:FUNCtion[:SHAPe] <basic-wave>
SOURce<n>:VOLTage:UNIT VPP  SOURce<n>:VOLTage <vpp>
SOURce<n>:FUNCtion:SQUare:DCYCle <percent>
TRACe:DATA:DAC VOLATILE,<IEEE-488.2-binary-block>
SOURce<n>:VOLTage:OFFSet <voltage>  SOURce<n>:FUNCtion[:SHAPe] USER
```

实现另使用 `:SOUR<n>:FREQ:MODE?` / `... FIX`，避免在 Sweep 状态下误解固定频率写入；
该 DG4202 兼容路径不在所选手册的 frequency 索引中。任意波上传前还会写 `*CLS`，因此会
清除已有错误状态，不能视为只读诊断。

## 行为与安全边界

- Core 负责读取 CSV／NPY、拒绝非有限值、归一化和 DAC14 编码；插件只接收
  `DG4000DacBlock`。
- basic-state 事务只恢复 output、function、frequency、frequency mode、amplitude
  unit／value、offset 和 square duty。phase、load、modulation、完整 Sweep profile 和被覆盖的
  volatile USER 波表不在恢复范围内。
- `source.channel_profile`、`source.sweep_profile` 和 `source.counter_profile` 都是全有或全无的
  只读上下文，不会隐式启用功能或扩大自动恢复字段。
- descriptor 校验只证明 capability 与方法映射有效，不证明厂商命令语义、实机兼容性或测量准确度。

## 相关来源

- [Production descriptor](../src/wavebench_rigol_dg4000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dg4000/driver.py)
- [功能覆盖里程碑与验收边界](DG4000_COVERAGE_MILESTONES.md)
- [机器可读 conformance](../conformance/)
