# DG4000 功能覆盖里程碑

[English](DG4000_COVERAGE_MILESTONES_EN.md)

## 1. 目标与状态

本文把 DG4000 编程手册的广阔命令面拆成 M0–M12。里程碑编号是风险顺序，不是命令数量或完成率；每一级只有在代码、失败路径、发行包和相应实机证据同时满足退出门后才算完成。

当前版本：`wavebench-rigol-dg4000 0.2.0`。

| 里程碑 | 状态 | 范围 |
|---|---|---|
| M0 | **完成** | 命令域审计、公开边界、证据等级、发行包隔离 |
| M1 | **下一步 / 未完成** | 现有 API 的严格输入、回包、型号与只读快照收口 |
| M2 | 未完成 | 现有固定波形/输出写路径事务化 |
| M3 | 未完成 | 完整只读通道 profile 与受限恢复契约 |
| M4 | 已有实现，里程碑未通过 | DAC14 任意波事务与外置插件实机复验 |
| M5 | 未开始 | Sweep 只读 profile |
| M6 | 未开始 | Counter 非破坏性只读 profile |
| M7 | 未开始 | Sweep 受控事务与触发 |
| M8 | 未开始 | Pulse/Burst/Marker 受控 profile |
| M9 | 未开始 | 双通道 Coupling 原子事务 |
| M10 | 未开始 | 基础调制 AM/FM/PM/PWM |
| M11 | 未开始 | 高级调制、谐波和高级任意波格式 |
| M12 | 未开始 | 型号/通道验收矩阵与发布收口 |

M0 完成不表示仪器功能增加。0.2.0 只交付规划、双语文档和发行包防泄漏回归。

## 2. 所有阶段共同规则

- 不公开 raw-SCPI 逃生口；所有操作通过窄 capability、严格参数模型和明确权限进入。
- 所有数值输入与仪器数值回包必须是有限数；`NaN`、正负无穷和无法解析值 fail closed。
- 枚举值必须显式白名单；不把未知值猜成 OFF、FIX、SIN 或默认单位。
- 每个面向指定通道的 API 显式携带通道；CH1/CH2 不依赖前面板当前选择。
- 所有 transport I/O 由同一个可重入锁串行化。快照、写入、回读、错误检查和恢复不可交织。
- 写前快照必须完整成功；否则零写入。写后逐字段回读，不以“命令未抛异常”代表成功。
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
- 实际 wheel 只有一个 `wavebench.instruments` entry point 并包含 MIT LICENSE；
- 实际 sdist 不含本地厂商资料。

## 5. M1 — 现有 API 严格收口

**状态：未完成；P0。** 不增加 capability。

目标命令：`*IDN?`、`SYSTem:ERRor?`、`OUTPut<n>?`、`SOURce<n>:FUNCtion?`、`FREQuency?`、`VOLTage?`、`VOLTage:UNIT?`、`VOLTage:OFFSet?`、`PHASe?`、`FREQuency:MODE?`、`SWEep:STATe?`、`APPLy?`、`FUNCtion:SQUare:DCYCle?`。

实施要求：

- 写入口拒绝所有非有限频率、Vpp、offset、duty；只读状态也拒绝非有限回包，不返回含不可信字段的部分 `SourceStatus`；
- output、function、unit、frequency mode、sweep state 使用严格枚举；
- `*IDN?` 解析 manufacturer/model，区分“可只读识别”与“允许写入且已验收”的型号；
- 聚合状态查询全有或全无；任一查询失败不得产生写入；
- 统一 `check_errors_after_ops` 的实例默认语义，直接 driver 调用与 Service 调用一致；
- 保留 `source.arbitrary_probe` 的 query-only 限制，并明确它会消费错误队列、候选 `-113` 不代表 capability。

退出门：

- 每个 query 位置的异常、空串、非有限数、未知枚举和错误通道均有失败注入；
- M1 相关 core/fallback 与外置插件行为保持一致；
- 真实 DG4202 对 CH1/CH2 各完成一轮零写入 profile，查询集合和最终错误队列有脱敏证据。

## 6. M2 — 固定波形与输出写事务

**状态：未完成；P0。** 覆盖现有 `source.set_frequency`、`set_function`、`set_amplitude_vpp`、`set_square_duty_cycle` 和 `source.output`。

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

## 7. M3 — 完整只读通道 profile 与恢复声明

**状态：未完成；P1。**

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

退出门：CH1/CH2 profile 全有或全无、有限数/枚举严格校验、无写入；README、artifact 和 run restore 不再使用“完整状态恢复”描述当前 basic restore。

## 8. M4 — DAC14 任意波事务与实机复验

**状态：已有离线实现，里程碑未通过；P1。**

目标命令：`TRACe:DATA:DAC VOLATILE,<IEEE-488.2 binary block>`、固定播放频率、`VOLTage:UNIT VPP`、Vpp、offset、`FUNCtion USER` 和显式 output。

冻结边界：只接受核心生成并校验的 `DG4000DacBlock`；DAC14、little-endian、volatile 目标；不接收 raw bytes、十进制波表、DAC16 或文件路径。

前置与事务：

- 目标通道必须已经 OFF，且处于 FIX、非 sweep、非 burst、非 modulation；不静默改为安全态；
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

## 9. M5 — Sweep 只读 profile

**状态：未开始；P2。** 只查询已经存在的 sweep，不启动、不停止、不触发。

profile 至少包含 `SWEep:STATe?`、`FREQuency:STARt?/STOP?/CENTer?/SPAN?`、`SWEep:SPACing?`、`SWEep:STEP?`、`SWEep:TIME?`、hold/return time、trigger source/slope/trigger-out 和 marker 状态/频率。

退出门：严格枚举、内部字段关系校验、任一查询失败时不返回部分 profile；在仪器 OFF 且 sweep OFF/ON 两种预置状态各验证三轮，整个验收零写入。

## 10. M6 — Counter 非破坏性只读 profile

**状态：未开始；P2。**

允许查询：`COUNter:STATe?`、`MEASure?`、`COUPing?`、`IMPedance?`、`ATTenuation?`、`GATEtime?`、`HF?`、`LEVel?`、`SENSitive?` 和统计状态/显示。

默认拒绝 `COUNter:AUTO`、`STATIstics:CLEAr` 以及自动启用 counter。若 counter 当前为 OFF，返回状态并明确“无测量”，不偷偷打开输入。50 Ω 只作为回读值；未来写入必须有独立接线确认。

退出门：未知/非有限回包 fail closed，重复查询不改变 counter/统计状态，真实 DG4202 记录零写入证据。

## 11. M7 — Sweep 受控事务

**状态：未开始；P2。** 必须在 M2、M3、M5 后实施。

事务覆盖 start/stop 或 center/span、spacing/steps/time、marker、trigger source/slope/trigger-out 和 sweep state。手动 immediate trigger 或 `*TRG` 只作为已建立且回读确认的 sweep session 内的一次显式动作。

退出门：完整 snapshot→write→readback→external measurement→OFF→restore；任何失败保持 output OFF；CH1/CH2 分开验收，禁止在没有负载/频率约束时开放通用 sweep。

## 12. M8 — Pulse、Burst 与 Marker

**状态：未开始；P2/P3。**

- Pulse profile：hold mode、width/duty、delay、leading/trailing transition；
- Burst profile：mode、cycles、phase、internal period、delay、gate polarity、trigger source/slope/trigger-out；
- Marker 只在相关 sweep/burst profile 中开放，不做全局裸 setter。

先只读，后事务写。输出与 trigger 必须显式分离；immediate trigger 不允许重试。退出门包括输出 OFF 失败收敛、边沿/占空比约束和示波器时域证据。

## 13. M9 — 双通道 Coupling 原子事务

**状态：未开始；P3。**

覆盖 `COUPling:STATe`、base channel，以及 amplitude/frequency/phase coupling state 和 deviation。一次操作影响两路，因此必须使用双通道快照、单一设备锁和双通道恢复；任一通道状态不可读则零写入。

退出门：CH1/CH2 均 OFF 配置并回读，随后低风险闭环；故障注入覆盖每条写和恢复；恢复失败时两路都保持 OFF 并锁存。

## 14. M10 — 基础调制

**状态：未开始；P3。**

第一批只考虑 AM/FM/PM/PWM 的 state、type、内部 source、内部 frequency/function 和 depth/deviation。外部调制源不在本级开放。每种调制是独立 profile 和 capability，不使用一个巨大的通用参数字典。

退出门：M2/M3 事务基础复用；调制 OFF 时配置、逐字段回读、显式 ON、示波器/频谱证据、OFF 与恢复；不同 mode 的不适用字段不能被猜测或遗留。

## 15. M11 — 高级调制、谐波与高级任意波

**状态：未开始；P3。**

候选范围：ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK、harmonic order/type/user/amplitude/phase，以及与 DAC14 明确分离的 `TRACe:DATA:DAC16`、points/value/interpolate/load 查询。

每个候选先经过手册/固件探针、独立数据契约和资源上限审计。DAC16 不能复用 `DG4000DacBlock` 冒充 DAC14；分包、字节序、最大点数、RAM/DDR 生命周期与回读语义必须先冻结。没有具体实验需求时可永久留在 backlog。

## 16. M12 — 型号矩阵与发布收口

**状态：未开始。**

M12 不增加 raw SCPI 或高副作用维护命令。它收敛：

- 每个已公开 capability 的型号、固件、CH1/CH2、backend 和证据等级矩阵；
- 外置插件与内建 fallback 的差异测试；
- lifecycle、wheel/sdist、editable、升级/降级/卸载回退与公开安装文档；
- 慢传输、query/write timeout、binary partial failure、并发、锁存后行为和 artifact 脱敏；
- 版本兼容范围与变更日志，不把“某型号可识别”写成“该型号已验收”。

最终退出门要求所有公开写 capability 都有正常路径、失败矩阵、恢复/锁存证据和至少一个明确型号/通道的实机验收；其余命令保持未覆盖或默认拒绝。

## 17. 当前证据边界

- 外置插件实机通过：DG4202 CH1 受控 1 kHz、1 Vpp 正弦闭环，错误队列为空，basic restore 回读通过。
- 离线通过：CH2 基础命令前缀与现有 DAC14 精确命令序列。
- 历史但未迁移：内建驱动 DAC14 little-endian/三角波闭环。
- 尚未通过：M1–M3 严格/事务基础，外置 DAC14 CH1/CH2 实机复验，以及 M5–M12。

状态升级必须同步更新中英文矩阵、里程碑、README、测试和真实构建产物检查。
