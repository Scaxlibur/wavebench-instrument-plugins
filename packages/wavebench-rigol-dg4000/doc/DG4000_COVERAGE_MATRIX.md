# DG4000 编程手册功能覆盖矩阵

[English](DG4000_COVERAGE_MATRIX_EN.md)

分阶段实现顺序、事务规则和实机退出门见
[DG4000 功能覆盖里程碑](DG4000_COVERAGE_MILESTONES.md)。当前 `0.7.0` 开发分支保留
M0–M6、只读 `source.snapshot_v2`，并开放 Basic／Live Basic／Output Source V2 P1。
M4/M5 的 CH1/CH2 完整实机门、M6 的全局 counter-OFF 实机门、Source V2 只读门和 P1
normal-path 门已通过。M7–M12 的受控写入仍未通过。命令出现在本矩阵中不等于已实现。

## 目的、范围与统计口径

本矩阵将本地保存的 DG4000 中文编程手册与 WaveBench 的外置
`wavebench-rigol-dg4000` 插件、内建 `dg4202` fallback，以及已记录的 DG4202
验收证据对照。它回答「手册列出了什么」「当前公开 API 实际覆盖了什么」「哪部分有哪一级
证据」，不把手册、DG4162 示例参数、内建驱动的历史验收或方法存在性等同于当前外置
插件的功能验收。

审计输入为 DG4000 系列中文编程手册，标注的软件版本为 `00.01.12`、文档编号
`PGB04008-1110`。转录为 12,236 行 Markdown，保存在本插件的
`doc/vendor-local/`；该目录被 Git 忽略、不会进入 wheel/sdist，也不会随本文提交。
手册明确以 DG4162 给出若干范围示例，且提示不同型号、负载和频率会改变参数范围。因此
本矩阵不把任何 DG4162 数值范围外推给 DG4202。

按手册的「命令系统」目录，本矩阵覆盖 12 个命令域：10 个具名厂商子系统
(`COUNter`、`COUPling`、`DISPlay`、`MEMory`、`MMEMory`、`OUTPut`、`PA`、
`SOURce`、`SYSTem`、`TRACe`)、单独列出的 `HCOPy:SDUMp:DATA?`，以及 IEEE
488.2 公用命令。手册转录的排版标题不能作为完成率分母：同一命令的 set/query、可选
关键字、同义短写，以及转录中的缺失 `]`、缺失代码围栏和断裂标题都会造成歧义。因此矩阵
按可审计的功能域和公开 capability 说明覆盖状态，而不报告一个伪精确的百分比。

当前外置插件声明 17 项 WaveBench capability。它是对 DG4202 双通道基础输出、只读
通道/sweep 上下文、全局 counter 上下文和窄任意波上传的受控实现，不是通用 DG4000
SCPI shell，也不承诺覆盖手册中所有 DG4000 型号、固件或外部附件能力。

覆盖标签：

- **外置实机通过**：当前外置插件实现、FakeTransport 测试和受控 DG4202 实机证据均存在。
- **已实现 / 离线验证**：当前代码和离线精确命令测试存在，但没有该细项的外置插件实机结论。
- **历史实机证据，未迁移验收**：内建驱动时代有文档化的实机证据；外置插件虽迁移相同协议，仍不把它升级为该插件的实机验收。
- **诊断探针**：显式只查询候选命令，可能消费错误队列；不等同于稳定功能或厂商正式路径。
- **未覆盖**：外置插件、内建 fallback 和公开 SourceService 都没有相应 API。
- **默认拒绝**：即使手册提供命令，也因网络、存储、输出安全或全局状态风险而不暴露。

## 功能覆盖矩阵

### Source V2 P1

下表仅描述当前开发分支的显式 V2 写入口。DG descriptor 设置
`v1_route_migration_enabled=false`，因此这三项 capability 不接管任何 legacy V1 route。

| capability | 公开入口与严格边界 | DG4202 `00.01.14` normal-path 证据 |
|---|---|---|
| `source.basic_configure_v2` | CLI `source basic-configure-v2`；run `source.basic_configure_v2`。目标输出必须 OFF、频率模式必须 FIX、必须先取得 fresh V2 snapshot；DG adapter 每次只接受一个 Basic field。可请求 SIN/SQU/RAMP/PULS/NOIS/DC、frequency、Vpp、offset 或 square duty。 | CH1 在 OFF 下完成 RAMP/PULSE/NOISE/DC/SIN 写入与 V2 postcondition；CH2 完成 SQUARE/25% duty、frequency 和 Vpp 写入。外部高阻采集只覆盖 CH1 正弦与 CH2 方波。 |
| `source.basic_live_configure_v2` | CLI `source basic-live-configure-v2`；run `source.basic_live_configure_v2`。输出必须 ON、频率模式必须 FIX，且一次只能改一个 frequency 或 Vpp field；禁止 output cycling。 | CH1/CH2 都完成 1 kHz→2 kHz 和 1 Vpp→2 Vpp 的独立 live 写后高阻采集。 |
| `source.output_v2` | CLI `source output-v2`；run `source.output_enable_v2` / `source.output_disable_v2`。Core 对 ON/OFF 分别执行 V2 preflight 和最终状态回读。 | 两路各自低压输出、采集、V2 OFF；独立恢复 run 再次确认两路 OFF。 |
| legacy V1 route | `source.set-*`、`source.output`、离散频响、`arb-load`、basic restore 与原有 artifact 保持 V1 合同。 | Core 路由测试与 DG P1 实机计划共同确认 V2 只由显式入口调用。 |

P1 没有公开 volatile ARB、Counter、Sweep、Burst、Coupling、Noise Overlay 或 Sync 写 capability；
也没有对 timeout、二义写或 recovery-failure 做上机故障注入。此类结果继续以离线故障矩阵为准。

| 功能域 | 手册命令面 | 当前公开覆盖 | 证据状态 | 主要缺口与安全边界 | 建议 |
|---|---|---|---|---|---|
| 身份与错误队列 | `*IDN?`、`:SYSTem:ERRor?`、`:SYSTem:VERSion?` | `source.idn`、`source.errors`；写操作后可检查错误队列 | **外置实机通过**：DG4202 `00.01.14` 的 M1/M2/M4 前后错误队列与脱敏身份读取通过；精确 SCPI 有离线测试 | `errors()` 会读取并消费队列；未公开 SCPI version、状态寄存器或非消费型健康 API | 保持错误队列显式；若要扩展只读 health，先定义消费语义 |
| IEEE 488.2 状态保存、复位与触发 | `*RCL`、`*RST`、`*SAV`、`*TRG` | 未公开 | **默认拒绝** | 恢复/保存会覆盖非易失状态；复位改变整机；`*TRG` 会启动 sweep/burst 输出 | 只在单独的受控事务设计、快照和人工确认后考虑 |
| CH1/CH2 基础状态读取 | `OUTPut?`、`SOURce:FUNCtion?`、`FREQuency?`、`VOLTage?` / `UNIT?` / `OFFSet?`、`PHASe?`、`SWEep:STATe?`、`APPLy?`、方波 duty | `source.status` 保留 V1 结果；`source.snapshot_v2` 以类型化 Basic、输出开关和前后锚点返回双通道状态，频率模式由手册明确的 `SWEep:STATe?` 推导 | **外置实机通过**：V1 严格 profile 为 24 queries、0 writes；`0.7.0` 初始快照为 40 次纯查询，纳入全部新增 facet 后的最终快照为 67 次，均锚点一致且会话 healthy | Source V2 Output 暂不重复查询已由 `source.channel_profile` 覆盖的 load/polarity；快照不扩大自动恢复范围 | 保持 V1 写路由不变；新增字段先满足纯查询、预算和一致性合同 |
| 固定频率 | `[:SOURce<n>]:FREQuency[:FIXed]`；扫频的 center/span/start/stop 同属 frequency 域 | `source.set_frequency`，以快照、`FIX` 切换、逐步回读、off-first 恢复和歧义锁存组成事务 | **外置实机通过**：DG4202 `00.01.14` CH1/CH2 的 FIX 写入、回读和新会话恢复通过 | `FREQ:MODE` 是当前 DG4202 兼容路径，未在这份手册的 frequency 列表中出现；M5 sweep profile 只读，不设置这些字段 | 保留「先切 FIX」的显式安全语义；任何 sweep 写入必须使用独立事务 |
| 基础函数与方波占空比 | `FUNCtion[:SHAPe]`、`FUNCtion:SQUare:DCYCle`，以及 `APPLy:SINusoid/SQUare/RAMP/PULSe/NOISe` | `source.set_function`：SIN/SQU/RAMP/PULS/NOIS/DC；`source.set_square_duty_cycle` | **外置实机通过**：CH1/CH2 临时 SQU/37% duty、ON→OFF 和原 SIN 新会话恢复通过；其它函数仅离线 | 不公开 ramp symmetry、pulse 宽度/边沿、noise 参数、apply 组合写入或 function-specific 完整状态恢复 | 先为每种函数定义完整、可回读且可恢复的 profile，再增加 setter |
| 幅度、单位、偏移与相位 | `VOLTage`、`UNIT`、`OFFSet`、`HIGH`、`LOW`、`PHASe` | `source.set_amplitude_vpp` 写 `UNIT VPP` + amplitude；状态读取 offset/phase；任意波上传内部写 offset | **外置实机通过**：M2 CH1/CH2 的 0.8 Vpp 事务与恢复、M4 CH1 2 Vpp 与 CH2 1 Vpp 模拟闭环；offset 公开 setter 仍无 | 没有公开 offset/phase/high/low setter；VPP 限制由核心 safety limit 约束，仪器实际范围仍依赖型号、频率与负载；DBM/VRMS 未公开 | 保持 VPP-first API；实现其它单位或电平前必须联动 load、范围和恢复策略 |
| 输出开关 | `OUTPut[<n>][:STATe] ON|OFF` | `source.output`，只在用户明确请求时切换；任意波上传默认不打开输出 | **外置实机通过**：CH1/CH2 M2 的显式 ON→OFF 与恢复通过；M4 CH1/CH2 均有三角波闭环 | 输出会直接影响被测电路；不提供隐式 enable 或重试 | 保持独立 capability；所有更高层流程必须显式记录 output 目标态 |
| 输出负载、极性、噪声和同步 | `OUTPut:IMPedance/LOAD`、`POLarity`、`NOISe:*`、`SYNC:*` | `source.channel_profile` 只读返回 load/polarity/noise/sync；`source.snapshot_v2` 另以类型化 Noise Overlay 与 Sync facet 返回 enabled、scale 和 polarity | **外置实机通过**：M3 为 45 queries、0 text/binary writes；最终 V2 快照为 67 次纯查询，两路 Noise Overlay OFF/10%、Sync ON/POSITIVE | basic restore 仍不恢复这些字段；没有公开 setter；Noise Overlay 启用后缺少确定性硬峰值边界，Sync enable 还缺物理端口模型与 A5 接线证据 | 写入候选已拆为 Noise OFF-only 配置、Sync 配置和独立物理端口 enable/disable；当前保持 READ only |
| 双通道耦合 | `COUPling:AMPL/FREQuency/PHASe`、base channel 与状态 | `source.snapshot_v2` 以 `CHANNEL_SET` 返回全局状态、基准通道及 amplitude/frequency/phase 的 enabled + typed deviation | **外置实机通过（只读）**：最终 67-query 快照返回三维 OFF、基准 CH1；FakeTransport 覆盖混合三维、严格范围与零写 | 当前 relation graph 不可读，descriptor 不声明 CONFIGURE；尚未实现完整 target、双通道恢复或写故障矩阵 | Core 候选设计在首次稳定版前替换未发布的布尔 Coupling request；DG 写入仍等待双通道 OFF、完整恢复和 A4/A5 证据 |
| 扫频与手动/外部触发 | `SWEep:*`、frequency start/stop/center/span、`*TRG` | `source.sweep_profile` 保留完整 V1 只读结果；`source.snapshot_v2` 在 frequency mode 为 Sweep 时复用同一严格 profile 并返回类型化 Sweep facet；无 setter/trigger | **M5 外置实机通过**：sweep OFF/ON 预置状态均有零写证据；V2 活跃分支有离线精确命令测试，当前 FIX 实机快照正确返回 `inactive_by_anchor` | restore 不恢复完整 Sweep；V2 活跃分支尚无新鲜实机证据；`*TRG`/immediate trigger 仍默认拒绝 | **P2**：受控写事务仍需完整快照、逐字段回读、外部测量、off-first 恢复与 trigger 不重试语义 |
| Burst、Pulse、Marker、Harmonic | `BURSt:*`、`PULSe:*`、`MARKer:*`、`HARMonic:*` | `source.snapshot_v2` 可返回完整 Pulse facet、Burst OFF 或完整启用态 facet，以及 Harmonic enabled/configured order/maximum order/preset 的 `PARTIAL` facet；逐阶 amplitude/phase、Marker 写入和所有配置 API 未公开 | **Pulse 外置实机通过；其余部分离线验证**：CH1/CH2 在 output OFF、PULSE、1 Vpp 下完成 52-query V2 快照和完整 Pulse facet；Burst OFF 实机返回，Burst ON/Harmonic 活跃分支只有精确 FakeTransport 测试 | Harmonic 不声称分量列表；Burst ON/Harmonic 活跃态尚无外置 V2 实机证据；任何配置或 trigger 都缺少完整恢复事务 | 保持只读；活跃态由独立受控预置会话验收，不以 raw SCPI 绕过写 capability |
| 调制 | `MOD:AM/FM/PM/ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK/PWM:*` | `source.channel_profile` 与 `source.snapshot_v2` 均只读返回 modulation state/type；无模式专属参数或 setter | **部分只读上下文实机通过**：最终 V2 快照在 CH1/CH2 返回 OFF/AM；具体调制参数和写入未覆盖 | state/type 查询不等于调制能力；外部源、码率、极性与 phase 有交叉依赖 | **P3**：按模式拆分 capability，不通过 raw-SCPI 绕过恢复策略 |
| 任意波上传：DAC14 | `TRACe:DATA:DAC VOLATILE,<binary-block>` 或十进制 DAC 数据 | `source.arbitrary_upload` 只接收结构与样本均校验的 little-endian `DG4000DacBlock`；目标必须已 OFF、FIX、sweep OFF；binary 后逐项回读，失败锁存且明确 volatile USER 波表不可恢复 | **M4 外置实机通过**：CH1/CH2 均完成 output-off 上传、回读、错误队列、模拟频率/Vpp/形状闭环和恢复 | 没有公开十进制/浮点上传、DAC16、任意波编辑/读回；上传会覆盖 volatile 波形且切换到 USER | 保持当前窄协议面；新增格式前分别建立生命周期、回读与恢复证据 |
| 任意波诊断查询 | 当前插件候选含 `FUNC?`、`FUNC:USER?` 与若干 `SOURce:*ARB*` / `SOURce:*DATA*` 查询 | `source.arbitrary_probe`：仅允许问号结尾的候选并记录每条命令后的错误队列 | **诊断探针**；FakeTransport 覆盖 | 手册把 waveform data 放在 `TRACe:DATA`，不是 `SOURce:DATA`；某些候选本来就可能得到 `-113`。`errors()` 消费队列，因此它不是非侵入健康读取 | 保留为显式排障工具；不要将候选接受/拒绝升级为功能能力或实机验收 |
| 任意波编辑、浮点与 DAC16 传输 | `TRACe:DATA`、`DAC16`、`POINts`、`VALue`、`LOAD?`、interpolate | 未公开 | **未覆盖** | 不同数据格式、内存长度、自动选择 USER 与本机编辑规则不同；手册对 DAC16 给出固定分包条件 | **P2**：在明确 RAM/DDR 生命周期、字节序和回读语义后再实现 |
| 频率计 | `COUNter:*`：输入配置、gate、统计、测量结果 | `source.counter_profile` 保持严格只读；production 声明 `source.counter_configure_v2`、`source.counter_enable_v2` 和 `source.counter_measure_v2`。V2 只允许单字段 coupling／impedance／attenuation／level／statistics 配置、独立 enable/disable 与已启用后的五元组测量；不实现 auto/gate/HF/sensitivity/display/clear | **Counter V2 外置实机通过**：先逐项回读 50 Ω／1 MΩ、1X／10X、level、statistics 与 AC/DC，再以 1 kHz／1 Vpp 实测 Counter 1000.011247 Hz、RTM/FFT 1000 Hz；输出 OFF 的 Counter 启用→关闭也通过 | 50 Ω / 1 MΩ 输入与 counter enable 会影响接线安全；统计 clear 是破坏性操作；timeout、二义写与 recovery-failure 未上机故障注入 | 保持每字段单写、独立回读和最终 Counter OFF；最大输入约束与实际信号须由计划安全门和接线确认，不新增 auto/gate/clear |
| PA 外接功放 | `PA:*`：开关、增益、offset、极性、保存 | 未公开 | **默认拒绝** | 可直接造成更高功率输出，且 `PA:SAVE` 写内部状态 | 不纳入基础 DG4202 capability；必须有独立权限与人工安全检查 |
| 显示与屏幕截图 | `DISPlay:*`、`HCOPy:SDUMp:DATA?` | 未公开 | **未覆盖** | brightness/saver 写入属于前面板全局状态；截图需要 binary transfer 和格式验收 | **P3**：仅在确有诊断价值时设计只读 screenshot |
| 内部状态槽 | `MEMory:STATe:DELete/LOCK/VALid?`，以及 IEEE `*SAV/*RCL` | 未公开 | **默认拒绝** | 可能覆盖、删除、锁定或调用用户保存的状态；与 WaveBench 的临时恢复并非同一概念 | 保持主机侧 artifact 与恢复日志；不要写仪器内部槽位 |
| 外部 U 盘文件系统 | `MMEMory:CATalog/CDIR/COPY/DEL/LOAD/MDIR/RDIR/STORe` | 未公开 | **未覆盖** | 手册要求外部存储器；路径、删除、覆盖和 `.RAF/.RSF` 加载均有持久副作用 | 默认不做；若实现需路径沙箱、显式文件权限和 delete 双重确认 |
| 系统通信与全局设置 | `SYSTem:COMMunicate:LAN:*`、USB class、language、key lock、beeper、power-on、reference oscillator、channel copy | 未公开 | **默认拒绝** | 改 LAN/IP/DHCP 会断开当前会话；改 USB/clock/power-on/语言或复制状态影响全局行为 | 只考虑安全的只读 identity/version；网络配置永不经普通工作流写入 |
| 重启、关机与 preset | `SYSTem:PRESet/RESTART/SHUTDOWN` | 未公开 | **默认拒绝** | 中断实验、丢失会话或把整机恢复默认 | 仅限人工维护程序，不属于 WaveBench 生产驱动 |

## 当前直接使用的 SCPI 表面

以下按手册长写形式归一化；实现实际使用兼容短写，例如 `SOUR`、`OUTP`、`VOLT`。
这不是原始命令日志，也不代表每条都完成外置插件实机验收。

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

两项刻意的例外必须单独理解：

- 实现使用 `:SOUR<n>:FREQ:MODE?` / `... FIX`，以避免在 sweep 状态下把固定频率写入解释为 sweep 参数；该 DG4202 兼容路径没有出现在此手册的 frequency 命令列表，不能因代码存在而当作手册覆盖。
- 任意波上传前写 `*CLS`，用于清理并检查本次上传的错误状态。此命令不在这份手册列出的五条 IEEE 488.2 项中，且会清空错误队列，因此不属于「只读诊断」。

## WaveBench 提供、但不计入仪器手册覆盖的保障

- 核心在上传前读取 CSV/NPY、拒绝 NaN/inf、归一化并编码 14-bit DAC 数据；插件只接收 `DG4000DacBlock`，不复制文件解析和 safety policy。
- `max_source_vpp`、显式 `output_on`、run plan safety、artifact 和可选 source-state restore 属于核心工作流，不能计作 DG4000 某条 SCPI 的实现。
- driver 的 basic-state 事务恢复覆盖 output、function、frequency、frequency mode、amplitude unit/value、offset 和 square duty；核心 run restore 仍是更窄的 output/function/frequency/amplitude/duty 契约，且恢复必须先 OFF。两者都明确**不**恢复 phase、load、modulation、完整 sweep profile 或被覆盖的 volatile USER 波表。
- `source.channel_profile` 是独立、全有或全无的只读上下文。它不改变上述 basic restore
  的字段集合，也不把 load、polarity、noise、sync、burst、modulation、marker 或 pulse
  hold 纳入自动恢复。
- `source.sweep_profile` 同样是独立、全有或全无的只读上下文。它不启动、停止或触发
  sweep，也不把 frequency window、spacing、timing、trigger 或 marker 纳入自动恢复。
- `source.counter_profile` 是全局、全有或全无的只读上下文。counter OFF 时明确返回
  `measurement=None` 且不查询测量值；它不自动 enable、不发送 `AUTO` 或 statistics clear，
  也不把输入配置或统计状态纳入自动恢复。
- descriptor capability 校验仅证明声明的方法存在且可调用；它不证明命令语义、返回值解析或实机兼容性。

## 推荐路线

1. **P2/P3：M7–M10 受控写事务。** 已完成的 Sweep/Pulse/Burst/Coupling/Noise Overlay/Sync 只读 facet 不等于配置能力；Coupling、Noise Overlay 与 Sync 已有候选合同和恢复顺序，但尚未注册或实现写 capability。
2. **P3：M11 高级功能。** Harmonic 当前仅为 `PARTIAL` 只读 facet；逐阶分量、高级调制与 DAC16 继续分开建模。
3. **默认不做：文件系统、网络、内部状态槽、PA、restart/shutdown。** 它们需要与普通实验流程不同的权限模型和人工确认。

## 证据边界

- **手册侧**：本地 `vendor-local` 中文 DG4000 手册，仅用于内部审计；本文不复制手册正文或将它打进发行包。
- **实现侧**：外置插件的 `driver.py`、`descriptor.py` 和 FakeTransport 测试；内建 fallback 的历史文档仅用于区分来源，不自动成为外置插件验收。
- **外置实机侧**：DG4202 固件 `00.01.14` 已通过 M1–M5 双通道门和 M6 全局 counter-OFF 门；M4 CH1/CH2 的 DAC14 与 RTM2032 证据、M5 的 sweep OFF/ON 预置证据和 M6 的 counter-OFF 证据保持不变。`0.7.0` 的只读 V2 最终快照为 67 次纯查询，完整 harness 为 112 queries、0 text/binary writes，锚点一致、会话 healthy。P1 normal path 另完成 CH1/CH2 Basic／Live Basic／Output 的低压高阻验收，所有 capture quality/expect 门通过；Counter V2 另在 CH1 三通下以 1 kHz／1 Vpp 完成配置、启停、五元组测量和 RTM/FFT 交叉验收，最终 CH1 OFF、5 Vpp 配置、Counter OFF/AC。Sweep、Burst ON、Harmonic 活跃 V2 分支仍无新鲜实机证据；timeout、二义写和 recovery-failure 也尚无上机故障注入结论。
- **历史任意波侧**：旧内建 DG4202 证据仅用于来源区分；当前外置插件已有独立 CH1/CH2 协议证据，不再用历史结果替代验收。

只有明确控制过的命令、实际回读/外部测量和所需恢复检查，才能提升为「外置实机通过」。
