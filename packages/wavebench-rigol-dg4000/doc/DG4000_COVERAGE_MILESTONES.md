# DG4000 功能覆盖里程碑

[English](DG4000_COVERAGE_MILESTONES_EN.md)

## 1. 目标与状态

本文把 DG4000 编程手册的广阔命令面拆成 M0–M12。里程碑编号是风险顺序，不是命令数量或完成率；每一级只有在代码、失败路径、发行包和相应实机证据同时满足退出门后才算完成。

当前版本：`wavebench-rigol-dg4000 0.7.0`。

| 里程碑 | 状态 | 范围 |
|---|---|---|
| M0 | **完成** | 命令域审计、公开边界、证据等级、发行包隔离 |
| M1 | **完成** | 现有 API 的严格输入、回包、型号与只读快照收口 |
| M2 | **完成** | 现有固定波形/输出写路径事务化 |
| M3 | **完成** | 完整只读通道 profile 与受限恢复契约 |
| M4 | **完成** | DAC14 任意波事务与外置插件实机复验 |
| M5 | **完成** | Sweep 只读 profile |
| M6 | **完成** | Counter 非破坏性只读 profile |
| M7 | **完成（受限 opt-in）** | `rigol.dg4202-v2` 的 Sweep Source V2 configure/manual fire 已通过 DG4202 双通道 A4 实机门 |
| M8 | **部分完成** | Pulse/Burst Source V2 只读 facet 已实现；Marker 与受控写未开始 |
| M9 | **部分完成** | Coupling 只读 facet 与写事务候选设计完成；生产写入未开始 |
| M10 | 未开始 | 基础调制 AM/FM/PM/PWM |
| M11 | **部分完成** | 部分 Harmonic 只读 facet 已实现；逐阶分量、高级调制和任意波格式未开始 |
| M12 | **部分完成** | Basic／Output／Counter 及受限 opt-in Sweep 的 wheel-bound conformance 已完成；其余高级能力仍待验收 |

M0 完成不表示仪器功能增加。`0.7.0` 保留 M1–M5 的 DG4202 CH1/CH2 实机退出门和
M6 的全局 counter-OFF 实机退出门，并增加 Source V2 纯查询适配。只有当前
OFF/SIN/FIX 状态、output-OFF Pulse/1 Vpp 状态，以及包含 Coupling、Sync、Noise Overlay、
Counter、Modulation 和部分 ARB 的最终 67-query 快照完成新鲜 V2 实机读取；其余活跃 facet
仍按各节证据边界处理。

## 2. 所有阶段共同规则

- 不公开 raw-SCPI 逃生口；所有操作通过窄 capability、严格参数模型和明确权限进入。
- 所有数值输入与仪器数值回包必须是有限数；`NaN`、正负无穷和无法解析值 fail closed。
- 枚举值必须显式白名单；不把未知值猜成 OFF、FIX、SIN 或默认单位。
- 每个面向指定通道的 API 显式携带通道；CH1/CH2 不依赖前面板当前选择。
- 所有 transport I/O 由同一个可重入锁串行化。快照、写入、回读、错误检查和恢复不可交织。
- 写前快照必须完整成功；否则零写入。写后逐字段回读，不以「命令未抛异常」代表成功。
- 首次写入超时、连接中断或其它无法判断命令是否到达仪器的情况属于歧义写入：不盲目重试，并锁存该 driver 的后续配置写。
- 确定性失败可尝试保守恢复；恢复本身歧义、失败或无法回读时同样锁存。
- 输出相关恢复先强制目标通道 OFF，恢复其余字段，全部成功后才按快照恢复原 output。恢复失败保持 OFF。
- `SYSTem:ERRor?` 会消费错误队列；健康 API 必须标注消费语义，写事务只在明确边界检查。
- `*CLS` 会清状态，不属于只读探针。任何 binary block 写入都是不可盲重试的状态变更。
- 实机证据按型号、通道、固件和 capability 分开记录；DG4202 CH1 结论不外推到 CH2 或其它 DG4000 型号。
- 测试、文档和产物不得包含真实资源地址、序列号、命令日志、截图或原始波形。

## 3. 永久默认拒绝区

以下命令不因 M0–M12 推进而自动开放：

- 仪器状态槽与复位：`*SAV`、`*RCL`、`*RST`、`MEMory:STATe:DELete/LOCK`、`SYSTem:PRESet`；
- 外部文件系统：`MMEMory:COPY/DELete/LOAD/MDIRectory/STORe`；
- 网络与全局连接配置：`SYSTem:COMMunicate:LAN:*`、USB class；
- 中断会话：`SYSTem:RESTART`、`SYSTem:SHUTDOWN`；
- 外部功放：`PA:*`；
- 无上下文的 `*TRG`、裸 sweep/burst immediate trigger，以及任何绕过 capability 的原始写命令。

这些功能若未来确有需求，应使用独立权限模型、人工确认和独立项目，不作为普通 WaveBench 实验流程的一部分。

## 4. M0 — 命令审计与发行边界

**状态：完成。**

覆盖内容：

- 清点 `COUNter`、`COUPling`、`DISPlay`、`MEMory`、`MMEMory`、`OUTPut`、`PA`、`SOURce`、`SYSTem`、`TRACe`、`HCOPy:SDUMp:DATA?` 和 IEEE 488.2 命令域；
- 区分外置实机通过、离线验证、历史未迁移证据、诊断探针、未覆盖和默认拒绝；
- 固定 canonical ID `rigol.dg4202` 与内建短名 fallback 的迁移语义；
- 双语矩阵、双语里程碑、MIT 元数据和真实 sdist 内容检查；
- wheel 只收 Python 包和许可证；sdist 显式排除 `doc/vendor-local/`，四份公开覆盖文档进入 sdist。

退出证据：

- package tests、Ruff、`wavebench plugin package check` 通过；
- 实际 wheel 恰有 `rigol.dg4202` 与 `rigol.dg4202-v2` 两个预期的 `wavebench.instruments` entry point，并包含 MIT LICENSE；
- 实际 sdist 不含本地厂商资料。

## 5. M1 — 现有 API 严格收口

**状态：完成。** 不增加 capability。DG4202 固件 `00.01.14` 的 CH1/CH2 零写入实机门已通过。

目标命令：`*IDN?`、`SYSTem:ERRor?`、`OUTPut<n>?`、`SOURce<n>:FUNCtion?`、`FREQuency?`、`VOLTage?`、`VOLTage:UNIT?`、`VOLTage:OFFSet?`、`PHASe?`、`FREQuency:MODE?`、`SWEep:STATe?`、`APPLy?`、`FUNCtion:SQUare:DCYCle?`。

实施要求：

- 写入口拒绝所有非有限频率、Vpp、offset、duty；只读状态也拒绝非有限回包，不返回含不可信字段的部分 `SourceStatus`；
- output、function、unit、frequency mode、sweep state 使用严格枚举；
- `*IDN?` 解析 manufacturer/model，区分「可只读识别」与「允许写入且已验收」的型号；
- 聚合状态查询全有或全无；任一查询失败不得产生写入；
- 统一 `check_errors_after_ops` 的实例默认语义，直接 driver 调用与 Service 调用一致；
- 保留 `source.arbitrary_probe` 的 query-only 限制，并明确它会消费错误队列、候选 `-113` 不代表 capability。

退出门：

- 每个 query 位置的异常、空串、非有限数、未知枚举和错误通道均有失败注入；
- M1 相关 core/fallback 与外置插件行为保持一致；
- 真实 DG4202 对 CH1/CH2 各完成一轮零写入 profile，查询集合和最终错误队列有脱敏证据。

2026-07-27 证据：同一只读会话查询 CH1/CH2，共 24 queries、0 writes；两路均为
ON/SIN/1 kHz/5 Vpp/0 V/FIX/sweep OFF，最终错误队列为空。固件记录为 `00.01.14`，
不记录序列号与资源地址。

## 6. M2 — 固定波形与输出写事务

**状态：完成。** 覆盖现有 `source.set_frequency`、`set_function`、`set_amplitude_vpp`、`set_square_duty_cycle` 和 `source.output`。

目标命令：

```text
SOURce<n>:FREQuency:MODE FIX
SOURce<n>:FREQuency[:FIXed] <frequency>
SOURce<n>:FUNCtion[:SHAPe] <wave>
SOURce<n>:VOLTage:UNIT VPP
SOURce<n>:VOLTage <vpp>
SOURce<n>:FUNCtion:SQUare:DCYCle <percent>
OUTPut<n> ON|OFF
```

其中 `FREQuency:MODE FIX` 是现有 DG4202 兼容路径，不在本地手册的 frequency 命令目录中；
M2 必须以目标固件探针和实机回读验证它，不能仅凭当前代码存在而当作手册保证。

事务要求：

- driver 级统一 `RLock`；完整快照后再写；每一步回读目标字段并按明确容差验证；
- amplitude 的 unit+value 两步不能留下半更新状态；切 FIX 和写 frequency 作为同一事务处理；
- 写失败时先 OFF，再恢复 function/frequency/unit/amplitude/duty，最后才恢复原 output；
- output ON 前重新检查核心 Vpp safety limit、完整 profile 和错误队列；
- 歧义写入、回读失败后无法确认状态、恢复失败均锁存配置写；锁存后只允许诊断与显式关闭输出的应急路径；
- run restore 采用同样的 off-first 规则，不能在 live output 上逐项改波形。

退出门：

- 对每个快照 query、每条 forward write、每个 readback、错误检查和每条 restore write 注入故障；
- 并发测试证明同一实例的公共 I/O 不交织；
- DG4202 CH1 与 CH2 分别完成低 Vpp、高阻负载下的固定正弦、方波 duty、输出 ON→OFF 和逐字段恢复；
- 首次写入歧义与恢复失败的实机故障路径只在可控代理/故障注入层执行，不通过拔线猜测成功。

2026-07-27 证据：CH1/CH2 分别执行 OFF→临时 SQU/不同固定频率/0.8 Vpp/37% duty
→ON→OFF→off-first 恢复；每路均由新会话逐字段复核。最终两路恢复为原始
ON/SIN/1 kHz/5 Vpp/0 V/FIX/sweep OFF，错误队列为空。故障矩阵继续由离线
FakeTransport 注入覆盖，不把断线实验当作状态证据。

## 7. M3 — 完整只读通道 profile 与恢复声明

**状态：完成。**

在 M1 基础上增加只读字段：

```text
OUTPut<n>:LOAD? / IMPedance?
OUTPut<n>:POLarity?
OUTPut<n>:NOISe:STATe? / NOISe:SCALe?
OUTPut<n>:SYNC:STATe? / SYNC:POLarity?
SOURce<n>:BURSt:STATe?
SOURce<n>:MOD:STATe? / MOD:TYPe?
SOURce<n>:MARKer:STATe?
SOURce<n>:PULSe:HOLD?
```

profile 必须区分：

- **可恢复字段**：WaveBench 已经写入且已具备事务恢复的字段；
- **只读上下文**：用于拒绝不安全操作，但当前不会自动恢复；
- **不可恢复副作用**：例如 volatile USER 波形内容被覆盖。

退出门：CH1/CH2 profile 全有或全无、有限数/枚举严格校验、无写入；README、artifact 和 run restore 不再使用「完整状态恢复」描述当前 basic restore。

2026-07-27 证据：外置插件 `0.4.0` 在 DG4202 固件 `00.01.14` 的同一受控会话中读取
CH1/CH2。transport 守卫禁止任何 text/binary write，最终完成 45 次 query、0 次 text
write、0 次 binary write；两路基础状态与 load/polarity/noise/sync/burst/modulation/marker/
pulse-hold 上下文均全量返回。错误队列是消费型读取，本退出门没有读取它。M3 不扩大
basic restore；只读上下文和 volatile USER 不进入自动恢复承诺。

## 8. M4 — DAC14 任意波事务与实机复验

**状态：完成；CH1/CH2 均通过完整实机退出门。**

目标命令：`TRACe:DATA:DAC VOLATILE,<IEEE-488.2 binary block>`、固定播放频率、`VOLTage:UNIT VPP`、Vpp、offset、`FUNCtion USER` 和显式 output。

冻结边界：只接受核心生成并校验的 `DG4000DacBlock`；DAC14、little-endian、volatile 目标；不接收 raw bytes、十进制波表、DAC16 或文件路径。

前置与事务：

- 目标通道必须已经 OFF，且处于 FIX、sweep OFF；M3 已能可靠读取 burst/modulation 状态，但当前 M4 上传事务尚未把它们纳入 preflight，因此不宣称验证这两项上下文；不静默改为安全态；
- `output_on=false` 的含义是上传后保持 OFF，而不是保留原来的 ON；
- binary block 不盲重试。首次 binary write 结果不明时锁存，并记录 volatile 波表状态未知；
- 上传后逐项回读 USER/frequency/Vpp/offset；只有用户显式请求且 safety 再检查通过才启用输出；
- 恢复先 OFF。原 function/frequency/Vpp/offset 等可恢复字段逐项恢复；原 volatile USER 数据不可恢复，必须写入 artifact。

实机退出门：

1. DG4202 CH1 输出 OFF，上传低点数、1 kHz、1 Vpp、0 V offset 的 DAC14 三角波或正弦波；
2. 回读 USER/frequency/Vpp/offset 且错误队列为空；
3. 显式 ON，由高阻示波器闭环确认频率、Vpp 与形状，再 OFF；
4. 恢复并新会话逐字段复核；
5. CH2 单独重复；外置插件证据不能由内建驱动历史记录代替。

2026-07-27 证据：CH1/CH2 各自在 OFF/FIX/sweep OFF 下上传一次 64 点 little-endian
DAC14 三角波，逐项回读 USER/1 kHz/1 Vpp/0 V，错误队列为空，并在新会话确认原态
恢复。CH1 另以 2 Vpp 显式输出并由高阻 RTM2032 采集 10,000 点，测得 997.26 Hz、
2.16 Vpp；三角模板 RMSE 为 0.0390 V，是正弦模板的 49.2%。恢复后原正弦复测为
998.25 Hz、5.12 Vpp。CH2 随后接入 RTM2032 CH2 高阻输入并以 1 kHz、1 Vpp 三角波
重复第 3 步，测得 999.75 Hz、1.12 Vpp；归一化三角模板 RMSE 为 0.09285，正弦模板
RMSE 为 0.2196，比值为 0.4229。DG4202 CH2 原始状态随后恢复，错误队列为空；示波器
时基、量程和触发设置在验收前后保持不变。两路 volatile USER 内容均已被覆盖。

## 9. M5 — Sweep 只读 profile

**状态：完成。** 只查询已经存在的 sweep，不启动、不停止、不触发。

profile 至少包含 `SWEep:STATe?`、`FREQuency:STARt?/STOP?/CENTer?/SPAN?`、`SWEep:SPACing?`、`SWEep:STEP?`、`SWEep:TIME?`、hold/return time、trigger source/slope/trigger-out 和 marker 状态/频率。

退出门：严格枚举、内部字段关系校验、任一查询失败时不返回部分 profile；在仪器 output
OFF 且 sweep OFF/ON 两种预置状态各验证三轮。每个 profile 读取会话必须严格零写；制造
预置状态与最终恢复使用单独的受控写会话，不混入 query-only 能力证据。

2026-07-27 证据：外置插件 `0.5.0` 在 DG4202 固件 `00.01.14` 上完成 CH1/CH2 双通道
验收。初始两路均为 output ON、FIX、sweep/burst/modulation/marker OFF。受控预置先关闭
输出，再分别建立 sweep OFF 与 sweep ON；两个独立零写 transport 会话各对两路连续读取
三轮，每个会话均为 104 queries、0 text writes、0 binary writes，各状态下三轮逐字段
一致。返回字段覆盖 start/stop/center/span、spacing、steps、sweep/hold/return time、trigger
source/slope/out 与 marker；离线测试同时覆盖每个查询位置失败、空/非有限/未知枚举、非整数
steps 和跨字段关系错误。恢复后，CH1/CH2 完整 channel profile 与 sweep profile 均和初始
快照一致，错误队列为空。未发送 immediate trigger 或 `*TRG`，未开放 sweep setter。

## 10. M6 — Counter 非破坏性只读 profile

**状态：完成。** 只读取全局 counter；不自动启用、不改输入配置、不清统计。

允许查询：`COUNter[:STATe]?`、条件式 `MEASure?`、`COUPing?`、`IMPedance?`、
`ATTenuation?`、`GATEtime?`、`HF?`、`LEVel?`、`SENSitive?` 和统计状态/显示。
正式驱动固定使用 DG4202 固件 `00.01.14` 验证过的短路径，包括 `:COUN?`、
`:COUN:LEVE?` 和 `:COUN:STATI:*`，不把其它缩写或长写形式的存在当作实机证据。

默认拒绝 `COUNter:AUTO`、`STATIstics:CLEAr` 以及自动启用 counter。若 counter 当前为 OFF，返回状态并明确「无测量」，不偷偷打开输入。50 Ω 只作为回读值；未来写入必须有独立接线确认。

退出门：未知/非有限回包 fail closed，重复查询不改变 counter/统计状态，真实 DG4202 记录零写入证据。

2026-07-27 证据：外置插件 `0.6.0` 在 DG4202 固件 `00.01.14` 上完成 counter-OFF
退出门。连续三轮完整 profile 逐字段一致；整个验收共 39 queries、0 text writes、
0 binary writes。counter 与 statistics 前后均为 OFF，display 前后均为 DIGITAL；profile
返回 AC、1 MΩ、1X、USER1、HF OFF、0 V、50% sensitivity 和 `measurement=None`。
OFF 分支未查询 `MEASure?`，也未发送 enable、`AUTO` 或 statistics clear。离线故障矩阵
覆盖每个查询位置、未知枚举、非有限/越界配置，以及 counter-ON 五元组的字段数、有限性、
frequency/period、pulse-width/period 和 duty/width 关系；counter-ON 尚无实机测量结论。

## 10.1. Source V2 P1 迁移

**状态：部分完成。** 当前 `0.7.0` 开发分支保留 `source.snapshot_v2`，并声明
`source.basic_configure_v2`、`source.basic_live_configure_v2`、`source.output_v2`、
`source.counter_configure_v2`、`source.counter_enable_v2` 与 `source.counter_measure_v2`。

- Basic：CH1/CH2 function、frequency mode/value、带单位 amplitude、offset、phase 和 square duty；
- Output：只读取 enabled，load/polarity 继续由 V1 `source.channel_profile` 提供；
- Sweep：激活时复用 M5 严格 profile，未激活时返回 `inactive_by_anchor`；
- Pulse：Pulse 波形激活时读取 hold、width/duty、delay 和双边沿；
- Burst：始终读取 state，OFF 时其余字段不适用，ON 时读取完整模式、时序和 trigger；
- Harmonic：只读取 enabled、configured/max order 与 preset，completeness 固定为 `PARTIAL`，
  不读取或伪造逐阶 amplitude/phase。
- Modulation 与 ARB：每通道读取 modulation state/type；ARB 只复用 Basic 锚点中的当前选择与频率，
  不伪造 playback mode、sample rate、point count 或 digest。
- Coupling：以 CH1/CH2 `CHANNEL_SET` 读取全局状态、基准通道及 amplitude/frequency/phase
  三维 enabled 与 typed deviation。
- Sync 与 Noise Overlay：每通道分别读取 enabled/polarity 和 enabled/percent scale。
- Counter：OFF 时复用 M6 严格 profile 且不发送 measurement query；V2 额外允许单字段配置、
  独立 enable/disable 与已启用后的五元组测量。
- Basic P1：输出 OFF、FIX 和 fresh snapshot 后，每次只写一个 Basic field；接受
  SIN/SQU/RAMP/PULS/NOIS/DC、frequency、Vpp、offset 或 square duty。
- Live Basic P1：输出 ON、FIX 时每次只写一个 frequency 或 Vpp field，禁止 output cycle。
- Output P1：ON/OFF 是独立 operation，各自有 preflight 和最终状态回读。

最坏查询预算为 138。每个查询项均为 `PURE_READ`，identity、Basic 与 Output 在前后阶段
复读；任何锚点漂移由 Core 标记，驱动不为快照发送 selector 或 write。

DG descriptor 设置 `v1_route_migration_enabled=false`。因此既有 V1 `source.set-*`、
`source.output`、离散频响、`arb-load` 与 basic restore 保持 V1 合同；只有显式 V2 CLI、
run step 或 Service operation 调用 P1/Counter V2 adapter。独立 `rigol.dg4202-v2` entry point
另声明受限的 Sweep configure/fire；volatile ARB、Burst、Coupling、Noise Overlay 和 Sync 仍不声明
生产写 capability。

2026-08-30 证据：DG4202 `00.01.14` 的 CH1/CH2 均为 OFF、SIN、1 kHz、5 Vpp、
0 V offset、FIX、sweep OFF。公开 CLI 完成 40-query Source V2 快照，前后锚点一致，
session health 前后均为 healthy。随后使用既有 V1 事务将两路临时设为 PULSE、1 Vpp，
输出始终 OFF；第二次 V2 快照完成 52 queries，并返回两路 DUTY hold、500 µs width、
50% duty、0 s delay 和 1.9531 µs 双边沿。最终新会话确认两路恢复为 OFF、SIN、1 kHz、
5 Vpp、0 V offset、FIX。该证据接受 Pulse 活跃 facet；Sweep、Burst ON 和 Harmonic
活跃态仍未验收，不使用 raw SCPI 临时激活。

同日后续验收在旧的 `:COUP:CHAN:BASE?` 写法处得到一次 timeout。验收没有重试该查询，
会话立即关闭；新会话复读确认两路状态未变。驱动改用手册完整关键字
`:COUP:CHANNEL:BASE?` 后，DG 包全量 `213 passed`。最终只读快照完成 67 queries，
前后锚点一致、session health 为 healthy；完整 harness 共 112 queries，所有 text/binary
write request、transmitted、completed 和 instrument mutation 均为 0。Coupling 三维均为
OFF、基准 CH1；两路 Sync 均为 ON/POSITIVE，Noise Overlay 均为 OFF/10%。最终两路保持
OFF、SIN、1 kHz、5 Vpp、0 V offset、FIX，session 健康关闭；RTM2032 未被访问或采集。

同日 P1 normal-path 验收使用当前 Core、DG 和 RTM 的隔离 wheel。CH1→RTM CH1 在输出 OFF
下完成 RAMP/PULSE/NOISE/DC/SIN 的 V2 write/readback，随后以正弦分别完成 1 kHz/1 Vpp、
live 2 kHz/1 Vpp、live 2 kHz/2 Vpp 的高阻采集。CH2→RTM CH2 完成 SQUARE/25% duty、
1 kHz/1 Vpp 与同样两次 live 变更采集。每路最大 2 Vpp、每次只开启对应通道，所有
capture quality/expect 门均通过。独立恢复 run 最终复读两路 OFF/SIN/1 kHz/5 Vpp/0 V/FIX/
50% duty，RTM 两路均为 high-Z。未向在线仪器注入 timeout、二义写或 recovery-failure。

## 10.2. Counter V2 生产写能力

**状态：DG4202 已通过受控实机验收。** Core 与 descriptor 声明
`source.counter_configure_v2`、`source.counter_enable_v2` 与 `source.counter_measure_v2`；
Core 以同一 enable capability 覆盖独立的 `source.counter_disable_v2` operation。adapter 使用
fresh Source V2 snapshot 的 Counter cache，MAIN 不查询、不调用 V1 setter。

- 配置仅接受 coupling、50 Ω／1 MΩ impedance、1X／10X attenuation、-2.5 V 至 2.5 V trigger level 与
  statistics enable。每次只写一个 `:COUN:*` 命令，正常完成后由 Core 独立回读。
- enable/disable 仅写 `:COUN ON|OFF`，不附带配置、AUTO、gate 或 clear。measure 仅对已经由 fresh snapshot
  证实为 ON 的 Counter 发送 `:COUN:MEAS?`。刚启用或无输入时的零值在 V2 snapshot 中标为不可用，
  仍允许 disable；legacy profile 与 measure 仍严格拒绝无效五元组。
- 2026-08-31 的安全夹具为 DG CH1→三通→RTM CH1 高阻与 DG Counter 输入。Counter 输入上限为
  5 Vpp，实际信号为 1 kHz、1 Vpp。配置逐项回读后，Counter 测得 1000.011247 Hz，RTM capture/FFT
  为 1000 Hz、1.0 Vpp；随后新会话确认 CH1 OFF、5 Vpp 配置、Counter OFF/AC。输出保持 OFF 的
  Counter enable→disable 也通过。

二义写会清 Counter cache 并锁定后续配置写；Core 不回滚配置、不自动 disable，而是将 session
标记为保守失效。timeout、二义写与 recovery-failure 尚无上机故障注入结论。`AUTO`、gate、HF、
sensitivity、statistics display 与 statistics clear 继续不属于 production capability。

## 10.3. Coupling、Noise Overlay 与 Sync 写能力候选

**状态：设计完成；未实现、未注册 capability。** 通用合同由 Core Source RFC 的 R8 候选章节
定义；本节只记录 DG4202 的协议顺序和退出门，不把设计文档当作写授权。

- Coupling 沿用 `source.coupling_configure_v2` 名称，但首次稳定版前把尚未发布的
  `channels + enabled` 请求替换为完整 target：全局 enabled、基准通道和三维 enabled + typed
  deviation。CH1/CH2 与 relation closure 内的主输出必须先为 OFF。DG 适配器的安全顺序为
  Coupling 全关、写 base、写三个 deviation、逐维恢复状态；postcondition 和失败恢复都读取完整
  Coupling，且不自动恢复主输出 ON。
- Noise Overlay 候选为 `source.noise_overlay_configure_v2`，request 包含 channel、enabled 和
  percent scale。目标主输出必须为 OFF；DG 正常顺序为先 scale、后 enabled。失败恢复保持主输出
  OFF，先禁用 Noise，再恢复 scale，最后按 baseline 恢复 enabled。手册的 `0–50 %` 不提供确定性
  峰值，因此 Noise Overlay 启用后不能绕过 Core 的 `noise_overlay_bound_missing` 输出门。
- Sync 必须拆成 `source.sync_configure_v2` 与 `source.sync_output_v2`。前者只在 Sync 端口 OFF 时
  配置 polarity；后者的 disable 是 decrease-only，enable 会在独立物理 Sync 连接器发出信号。
  当前 Core 还没有 Sync port ID、逻辑通道到物理端口的绑定或电气上界，因此 DG descriptor 不得
  声明任何 Sync 写 capability。port ID／binding／closure 完成后才能先评审配置与 disable；enable
  还需要电气上界和 A5。失败恢复只保证 Sync 端口 OFF 和 polarity 回读，不自动恢复 Sync ON。

三项写入都要求 fresh consistent snapshot、单次字段写入、独立 postcondition、完整 baseline 和
有界恢复。任一结果未知不重试；session poisoned 时只关闭连接。Coupling 与 Noise 的后续实机门
至少要求 A4，Sync enable 需要真实 Sync→scope 接线的 A5。当前 CH1→CH1、CH2→CH2 主输出接线
不能替代 Sync 物理端口证据。

## 11. M7 — Sweep 受控事务

**状态：完成，但仅作为独立 `rigol.dg4202-v2` opt-in driver 的受限 capability。** `rigol.dg4202`
保持原 V1 Sweep 路由；这不是完整 V1 API 迁移。

事务覆盖 start/stop 或 center/span、spacing/steps/time、marker、trigger source/slope/trigger-out 和 sweep state。手动 immediate trigger 或 `*TRG` 只作为已建立且回读确认的 sweep session 内的一次显式动作。

DG 候选将 start/stop、spacing、steps、time、hold/return、trigger slope/output、marker 和 Sweep state
写成一次 compound write；manual fire 只发送 channel-scoped immediate trigger。手册规定启用 Sweep 会关闭
Burst 与 Modulation，因此 Core 在该 driver 声明的动态闭包中于写前和写后都要求两项可读且为 OFF，不会替用户
自动关闭、恢复或重新启用它们。

2026-08-31 证据：CH1、CH2 分别在 output OFF 下配置线性 1–2 kHz、101 点、12 s、manual trigger、
marker OFF 的 Sweep；随后只开启当前通道，在同一会话 fire，并完成三段高阻 RTM 外部采集。CH1 频率估计为约
1202/1546/1872 Hz，CH2 为约 1265/1628/1982 Hz，最大采集为 1.016 Vpp。每个 run 在两路 output OFF
后结束。已关闭 marker 保留的 550 Hz 陈旧频率不代表启用配置错误；启用 marker 时仍做窗口校验。

退出门：完整 snapshot→write→readback→external measurement→OFF→独立恢复；任何失败保持 output OFF；CH1/CH2
分别验收。`source.sweep_configure_v2`／`source.sweep_fire_v2` 的 conformance 仅绑定上述夹具与参数，不外推
任意频率、幅度或时序。V2 操作不恢复 Sweep 状态，因此验收用单独 legacy 事务把两路恢复为 FIX/OFF 并由新会话确认。
不实现 raw `*TRG`，也不替代 V1 Sweep 路由。

## 12. M8 — Pulse、Burst 与 Marker

**状态：Pulse/Burst 只读 facet 已实现；Marker 与受控写未开始，P2/P3。**

- Pulse profile：hold mode、width/duty、delay、leading/trailing transition；
- Burst profile：mode、cycles、phase、internal period、delay、gate polarity、trigger source/slope/trigger-out；
- Marker 只在相关 sweep/burst profile 中开放，不做全局裸 setter。

只读阶段已完成离线精确命令与失败测试；Pulse 活跃 facet 已在两路 output OFF、1 Vpp
状态下通过实机读取，Burst ON 仍未验收。后续事务写要求输出与 trigger 显式分离；
immediate trigger 不允许重试。退出门包括输出 OFF 失败处理、边沿/占空比约束和示波器
时域证据。

## 13. M9 — 双通道 Coupling 原子事务

**状态：只读 facet 与候选事务设计完成；生产写入未开始，P3。**

覆盖 `COUPling:STATe`、base channel，以及 amplitude/frequency/phase coupling state 和 deviation。
只读实现与 DG4202 当前三维 OFF／基准 CH1 实机回读已经通过。后续一次写操作影响两路，因此
必须使用完整 target、双通道 snapshot、单一设备锁、relation closure 和双通道恢复；任一通道、
dimension 或 graph 状态不可读则零写入。

退出门：CH1/CH2 均 OFF 配置并回读，随后低风险闭环；故障注入覆盖每条写和恢复；恢复失败时两路都保持 OFF 并锁存。

## 14. M10 — 基础调制

**状态：未开始；P3。**

第一批只考虑 AM/FM/PM/PWM 的 state、type、内部 source、内部 frequency/function 和 depth/deviation。外部调制源不在本级开放。每种调制是独立 profile 和 capability，不使用一个巨大的通用参数字典。

退出门：M2/M3 事务基础复用；调制 OFF 时配置、逐字段回读、显式 ON、示波器/频谱证据、OFF 与恢复；不同 mode 的不适用字段不能被猜测或遗留。

## 15. M11 — 高级调制、谐波与高级任意波

**状态：Harmonic 部分只读 facet 已实现；其余未开始，P3。**

候选范围：ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK、harmonic order/type/user/amplitude/phase，以及与 DAC14 明确分离的 `TRACe:DATA:DAC16`、points/value/interpolate/load 查询。

当前 Harmonic 只读结果明确为 `PARTIAL`，不包含 USER mask 或逐阶 amplitude/phase。
DG4000 没有独立 Harmonic state-off 命令。输出 OFF、FIX 且 Basic readback 明确为 `HARM`／`HARMONIC` 时，
现有 Basic V2 Sine 写可作为明确的离开 Harmonic waveform 操作；它不声明 `source.harmonics_disable_v2`，也不把
Basic waveform 变化伪装成只改 Harmonic state。DG4202 `00.01.14` 已在 CH1、output OFF、FIX 条件下完成一次
受控的 active-Harmonic → Sine 写入与最终 readback。该结果没有示波器环回或外部测量，不覆盖 CH2、其它固件或
逐阶参数保持，因此不是 A3/A4 conformance，也不改变现有 Basic manifest 的限制。其余候选仍需先经过手册/固件探针、独立数据契约和资源上限审计。DAC16 不能复用
`DG4000DacBlock` 冒充 DAC14；分包、字节序、最大点数、RAM/DDR 生命周期与回读语义
必须先冻结。没有具体实验需求时可永久留在 backlog。

`rigol.dg4202-v2-workspace` 单独承载 `source.arbitrary_workspace_volatile_replace_v2`，仅保留 identity／snapshot
和 OFF safety closure 所需的 `source.output_v2`：它只表示一个无通道 volatile DAC14 工作区，不替代已有通道型
ARB 合同。Core 在写前确认 CH1/CH2 均 OFF，写后验证两路 OFF；失败时仅对仍可用的两路各最多尝试一次 OFF recovery。
结果不标识 USER 属于哪一路，也不承诺内容读回或恢复。该 entry point
与 `rigol.dg4202-v2` 分离，避免未验收工作区能力改变已绑定的 Sweep conformance 制品。实机验收前不
附加 manifest，也不将其描述为通道定向上传。

## 16. M12 — 型号矩阵与发布收口

**状态：部分完成。**

M12 不增加 raw SCPI 或高副作用维护命令。它收敛：

- 每个已公开 capability 的型号、固件、CH1/CH2、backend 和证据等级矩阵；
- 外置插件与内建 fallback 的差异测试；
- lifecycle、wheel/sdist、editable、升级/降级/卸载回退与公开安装文档；
- 慢传输、query/write timeout、binary partial failure、并发、锁存后行为和 artifact 脱敏；
- 版本兼容范围与变更日志，不把「某型号可识别」写成「该型号已验收」。

当前 `0.7.0` wheel 已将 Basic、Output、Counter 和受限 opt-in Sweep 的 10 份 conformance manifest 放入
自身 dist-info，并绑定各自 descriptor 与 wheel 的非 manifest 成员。该机制不提升 volatile ARB、Burst、
Coupling、Noise Overlay、Sync 或 Harmonic 活跃态的证据等级。

最终退出门要求所有公开写 capability 都有正常路径、失败矩阵、恢复/锁存证据和至少一个明确型号/通道的实机验收；其余命令保持未覆盖或默认拒绝。

## 17. 当前证据边界

- 外置插件实机通过：DG4202 固件 `00.01.14` 的 M1–M5 CH1/CH2 实机门、M6
  全局 counter-OFF 零写入门，以及 Counter V2 的配置、启停、测量和 RTM/FFT 交叉验收；`0.7.0` 的 52-query output-OFF Pulse 活跃快照和最终
  67-query 全 facet 基线快照也已通过。P1 的 Basic／Live Basic／Output normal path 已在
  CH1/CH2 高阻 RTM 闭环通过，恢复后两路均为 OFF/SIN/1 kHz/5 Vpp/0 V/FIX/50% duty。
  最终只读 harness 为 112 queries、0 text/binary writes。
- 受限 opt-in Sweep 实机通过：`rigol.dg4202-v2` 在 CH1 与 CH2 分别完成 output-OFF 配置、同会话 manual fire、
  三段 RTM 高阻采集、两路 output OFF，并通过独立 legacy 事务和新会话恢复 FIX/OFF；该结论仅覆盖线性
  1–2 kHz、101 点、12 s、1 Vpp、marker OFF 的夹具。
- active Harmonic 的受控状态迁移观察：DG4202 `00.01.14` 的 CH1 在 output OFF、FIX 下由
  `HARM`／`HARMONIC` 切换到 Sine，并完成最终 Basic／Output readback。未进行示波器环回或外部测量，未验证
  参数保持，不覆盖 CH2 或其它固件，因此不提升 Source conformance 等级。
- 历史证据仅保留来源区分，不再替代当前外置插件验收。
- 尚未通过：M8–M12 的其余受控写退出门；Coupling、Noise Overlay 与 Sync 只有写候选设计，
  未声明生产 capability。Burst ON 与 Harmonic 活跃 V2 facet 仍没有完整的外置实机证据。P1/Counter
  timeout、二义写和 recovery-failure 仍无上机 fault-injection 结论。

状态升级必须同步更新中英文矩阵、里程碑、README、测试和真实构建产物检查。
