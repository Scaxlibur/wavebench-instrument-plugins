# DG4000 编程手册功能覆盖矩阵

[English](DG4000_COVERAGE_MATRIX_EN.md)

分阶段实现顺序、事务规则和实机退出门见
[DG4000 功能覆盖里程碑](DG4000_COVERAGE_MILESTONES.md)。当前 `0.2.0` 仅完成 M0；
M1–M12 不因本矩阵列出命令而视为已实现。

## 目的、范围与统计口径

本矩阵将本地保存的 DG4000 中文编程手册与 WaveBench 的外置
`wavebench-rigol-dg4000` 插件、内建 `dg4202` fallback，以及已记录的 DG4202
验收证据对照。它回答“手册列出了什么”“当前公开 API 实际覆盖了什么”“哪部分有哪一级
证据”，不把手册、DG4162 示例参数、内建驱动的历史验收或方法存在性等同于当前外置
插件的功能验收。

审计输入为 DG4000 系列中文编程手册，标注的软件版本为 `00.01.12`、文档编号
`PGB04008-1110`。转录为 12,236 行 Markdown，保存在本插件的
`doc/vendor-local/`；该目录被 Git 忽略、不会进入 wheel/sdist，也不会随本文提交。
手册明确以 DG4162 给出若干范围示例，且提示不同型号、负载和频率会改变参数范围。因此
本矩阵不把任何 DG4162 数值范围外推给 DG4202。

按手册的“命令系统”目录，本矩阵覆盖 12 个命令域：10 个具名厂商子系统
(`COUNter`、`COUPling`、`DISPlay`、`MEMory`、`MMEMory`、`OUTPut`、`PA`、
`SOURce`、`SYSTem`、`TRACe`)、单独列出的 `HCOPy:SDUMp:DATA?`，以及 IEEE
488.2 公用命令。手册转录的排版标题不能作为完成率分母：同一命令的 set/query、可选
关键字、同义短写，以及转录中的缺失 `]`、缺失代码围栏和断裂标题都会造成歧义。因此矩阵
按可审计的功能域和公开 capability 说明覆盖状态，而不报告一个伪精确的百分比。

当前外置插件声明 10 项 WaveBench capability。它是对 DG4202 双通道基础输出和窄
任意波上传的受控实现，不是通用 DG4000 SCPI shell，也不承诺覆盖手册中所有 DG4000
型号、固件或外部附件能力。

覆盖标签：

- **外置实机通过**：当前外置插件实现、FakeTransport 测试和受控 DG4202 实机证据均存在。
- **已实现 / 离线验证**：当前代码和离线精确命令测试存在，但没有该细项的外置插件实机结论。
- **历史实机证据，未迁移验收**：内建驱动时代有文档化的实机证据；外置插件虽迁移相同协议，仍不把它升级为该插件的实机验收。
- **诊断探针**：显式只查询候选命令，可能消费错误队列；不等同于稳定功能或厂商正式路径。
- **未覆盖**：外置插件、内建 fallback 和公开 SourceService 都没有相应 API。
- **默认拒绝**：即使手册提供命令，也因网络、存储、输出安全或全局状态风险而不暴露。

## 功能覆盖矩阵

| 功能域 | 手册命令面 | 当前公开覆盖 | 证据状态 | 主要缺口与安全边界 | 建议 |
|---|---|---|---|---|---|
| 身份与错误队列 | `*IDN?`、`:SYSTem:ERRor?`、`:SYSTem:VERSion?` | `source.idn`、`source.errors`；写操作后可检查错误队列 | **外置实机通过（受控 CH1 正弦闭环的前后错误队列）**；精确 SCPI 有离线测试 | `errors()` 会读取并消费队列；未公开 SCPI version、状态寄存器或非消费型健康 API | 保持错误队列显式；若要扩展只读 health，先定义消费语义 |
| IEEE 488.2 状态保存、复位与触发 | `*RCL`、`*RST`、`*SAV`、`*TRG` | 未公开 | **默认拒绝** | 恢复/保存会覆盖非易失状态；复位改变整机；`*TRG` 会启动 sweep/burst 输出 | 只在单独的受控事务设计、快照和人工确认后考虑 |
| CH1/CH2 基础状态读取 | `OUTPut?`、`SOURce:FUNCtion?`、`FREQuency?`、`VOLTage?` / `UNIT?` / `OFFSet?`、`PHASe?`、`SWEep:STATe?`、`APPLy?`、方波 duty | `source.status` 返回 output、function、frequency、amplitude/unit、offset、phase、sweep 状态、apply 原串和 duty | **已实现 / 离线验证**；受控 CH1 正弦闭环间接覆盖所需状态回读 | 状态对象是恢复与诊断的窄快照，不是完整配置画像；不覆盖 load、polarity、sync、modulation、burst、marker、harmonic | 优先补齐可安全恢复的字段之前，不扩大 snapshot/restore 承诺 |
| 固定频率 | `[:SOURce<n>]:FREQuency[:FIXed]`；扫频的 center/span/start/stop 同属 frequency 域 | `source.set_frequency`，可先读并写 `:SOUR<n>:FREQ:MODE FIX`，再写固定频率并回读 | **外置实机通过（CH1 1 kHz 闭环）**；CH2 有 FakeTransport 覆盖 | `FREQ:MODE` 是当前 DG4202 兼容路径，未在这份手册的 frequency 列表中出现；不设置 sweep profile，也不恢复 sweep mode | 保留“先切 FIX”的显式安全语义；后续 sweep 必须是独立 profile 事务 |
| 基础函数与方波占空比 | `FUNCtion[:SHAPe]`、`FUNCtion:SQUare:DCYCle`，以及 `APPLy:SINusoid/SQUare/RAMP/PULSe/NOISe` | `source.set_function`：SIN/SQU/RAMP/PULS/NOIS/DC；`source.set_square_duty_cycle` | **外置实机通过仅限 CH1 正弦闭环**；函数/占空比精确写入有离线测试 | 不公开 ramp symmetry、pulse 宽度/边沿、noise 参数、apply 组合写入或 function-specific 完整状态恢复 | 先为每种函数定义完整、可回读且可恢复的 profile，再增加 setter |
| 幅度、单位、偏移与相位 | `VOLTage`、`UNIT`、`OFFSet`、`HIGH`、`LOW`、`PHASe` | `source.set_amplitude_vpp` 写 `UNIT VPP` + amplitude；状态读取 offset/phase；任意波上传内部写 offset | **CH1 正弦的 VPP 写入/回读在受控闭环中通过**；其余离线或读取 | 没有公开 offset/phase/high/low setter；VPP 限制由核心 safety limit 约束，仪器实际范围仍依赖型号、频率与负载；DBM/VRMS 未公开 | 保持 VPP-first API；实现其它单位或电平前必须联动 load、范围和恢复策略 |
| 输出开关 | `OUTPut[<n>][:STATe] ON|OFF` | `source.output`，只在用户明确请求时切换；任意波上传默认不打开输出 | **外置实机通过仅限受控 CH1 闭环**；CH2 离线 | 输出会直接影响被测电路；不提供隐式 enable 或重试 | 保持独立 capability；所有更高层流程必须显式记录 output 目标态 |
| 输出负载、极性、噪声和同步 | `OUTPut:IMPedance/LOAD`、`POLarity`、`NOISe:*`、`SYNC:*` | 未公开 | **未覆盖** | load 会改变幅度语义和可用范围；极性/同步会改变时序和被测电路观测 | **P1：先只读 load/impedance**，再考虑受控写入和 VPP safety 联动 |
| 双通道耦合 | `COUPling:AMPL/FREQuency/PHASe`、base channel 与状态 | 未公开 | **未覆盖** | 设置一侧会影响另一通道，无法用当前单通道 snapshot 安全恢复 | **P2**：先设计双通道原子快照、恢复与 lockout |
| 扫频与手动/外部触发 | `SWEep:*`、frequency start/stop/center/span、`*TRG` | `source.status` 只读 sweep state；固定频率会离开 sweep；无 sweep setter | **部分覆盖**：仅状态读取和离开 sweep 的固定频率路径；profile 无实机验收 | current restore 故意不恢复 sweep mode、时长、间隔、触发源或 trigger-out | **P1**：先做完整只读 sweep profile；写入必须是显式、可恢复的事务 |
| Burst、Pulse、Marker、Harmonic | `BURSt:*`、`PULSe:*`、`MARKer:*`、`HARMonic:*` | 未公开 | **未覆盖** | 会改变输出形状、外部触发或同步行为；部分参数与当前 function 有强耦合 | **P2/P3**：按独立 profile、输出风险和测试夹具拆分 |
| 调制 | `MOD:AM/FM/PM/ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK/PWM:*` | 未公开 | **未覆盖** | 大量模式专属且会修改输出；外部源、码率、极��与 phase 有交叉依赖 | **P3**：不要通过 raw-SCPI 入口绕过 capability 和恢复策略 |
| 任意波上传：DAC14 | `TRACe:DATA:DAC VOLATILE,<binary-block>` 或十进制 DAC 数据 | `source.arbitrary_upload` 接收核心校验后的 `DG4000DacBlock`；发送 `:DATA:DAC VOLATILE,#...`，再配置 frequency/VPP/offset、选择 `FUNC:SHAP USER`，仅在显式参数下 enable 输出 | **已实现 / 离线精确命令验证**；已有内建路径的历史实机证据表明 DG4202 采用 little-endian DAC14，并完成过闭环，**但外置插件未重复验收** | 没有公开十进制/浮点上传、DAC16 分段上传、任意波编辑/读回、插值或大波表 API；上传会覆盖 volatile 波形且切换当前通道到 USER | 外置插件下一步实机验收应先 output-off 上传、读回/示波器闭环、检查错误队列和恢复，不要扩大协议面 |
| 任意波诊断查询 | 当前插件候选含 `FUNC?`、`FUNC:USER?` 与若干 `SOURce:*ARB*` / `SOURce:*DATA*` 查询 | `source.arbitrary_probe`：仅允许问号结尾的候选并记录每条命令后的错误队列 | **诊断探针**；FakeTransport 覆盖 | 手册把 waveform data 放在 `TRACe:DATA`，不是 `SOURce:DATA`；某些候选本来就可能得到 `-113`。`errors()` 消费队列，因此它不是非侵入健康读取 | 保留为显式排障工具；不要将候选接受/拒绝升级为功能能力或实机验收 |
| 任意波编辑、浮点与 DAC16 传输 | `TRACe:DATA`、`DAC16`、`POINts`、`VALue`、`LOAD?`、interpolate | 未公开 | **未覆盖** | 不同数据格式、内存长度、自动选择 USER 与本机编辑规则不同；手册对 DAC16 给出固定分包条件 | **P2**：在明确 RAM/DDR 生命周期、字节序和回读语义后再实现 |
| 频率计 | `COUNter:*`：输入配置、gate、统计、测量结果 | 未公开 | **未覆盖** | 50 Ω / 1 MΩ 输入与计数器状态会影响接线安全；统计 clear 是破坏性操作 | **P2**：可先设计窄的只读 result/status capability |
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
- 任意波上传前写 `*CLS`，用于清理并检查本次上传的错误状态。此命令不在这份手册列出的五条 IEEE 488.2 项中，且会清空错误队列，因此不属于“只读诊断”。

## WaveBench 提供、但不计入仪器手册覆盖的保障

- 核心在上传前读取 CSV/NPY、拒绝 NaN/inf、归一化并编码 14-bit DAC 数据；插件只接收 `DG4000DacBlock`，不复制文件解析和 safety policy。
- `max_source_vpp`、显式 `output_on`、run plan safety、artifact 和可选 source-state restore 属于核心工作流，不能计作 DG4000 某条 SCPI 的实现。
- 当前 restore 只覆盖 output、function、frequency、amplitude 和 square duty；明确**不**恢复 offset、phase、load、modulation 或 sweep mode。因而一次流程恢复成功，不等于整台 DG4000 状态已经恢复。
- descriptor capability 校验仅证明声明的方法存在且可调用；它不证明命令语义、返回值解析或实机兼容性。

## 推荐路线

1. **P1：输出负载与完整只读 profile。** 先增加 `OUTPut:LOAD/IMPedance?`，然后定义包含 offset、phase、sweep state 与 load 的只读 profile；禁止在没有完整快照前扩大自动恢复范围。
2. **P1：外置任意波实机复验。** 用 output-off 上传低风险 DAC14 波形，验证 little-endian 数据、`USER` 选择、错误队列与示波器/DMM 证据；之后再明确恢复语义。
3. **P2：扫频 profile 与计数器只读。** 扫频需要 start/stop/spacing/time/trigger 的整体快照和恢复；频率计可先做不清统计的只读结果。
4. **P3：调制、burst、pulse、双通道耦合。** 按模式拆分 capability 和事务，不能用 raw-SCPI 旁路输出风险。
5. **默认不做：文件系统、网络、内部状态槽、PA、restart/shutdown。** 它们需要与普通实验流程不同的权限模型和人工确认。

## 证据边界

- **手册侧**：本地 `vendor-local` 中文 DG4000 手册，仅用于内部审计；本文不复制手册正文或将它打进发行包。
- **实现侧**：外置插件的 `driver.py`、`descriptor.py` 和 FakeTransport 测试；内建 fallback 的历史文档仅用于区分来源，不自动成为外置插件验收。
- **外置实机侧**：已记录 DG4202 CH1 受控 1 kHz、1 Vpp 正弦 → DS1104Z Plus CH1 闭环；测得 1000.000 Hz、1.008 Vpp，前后错误队列为空，并确认 finally 路径的恢复回读。CH2 仅有 FakeTransport 覆盖。
- **历史任意波侧**：旧内建 DG4202 路径有 `DATA:DAC VOLATILE` little-endian 和三角波闭环记录，但当前外置插件 README 明确写为“未重复实机验收”；矩阵因此不把它标为外置实机通过。

只有明确控制过的命令、实际回读/外部测量和所需恢复检查，才能提升为“外置实机通过”。
