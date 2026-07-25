# RTM2000 手册功能覆盖矩阵

[English](RTM2000_COVERAGE_MATRIX_EN.md)

## 目的与统计口径

本矩阵将 RTM2000 编程手册的本地命令索引与 WaveBench RTM2000 外置插件、内建 fallback 和已记录的 RTM2032 实机验收逐项对照。它回答“手册声明了什么、当前产品覆盖了什么、下一步最值得补什么”，不把手册声明等同于当前 RTM2032 已安装选件或实机能力。

指定手册的 1490 行转录中共有 1434 个命令索引条目，精确去重后为 1417 个命令模板（608 个带查询标记、809 个非查询形式）。进一步按大小写不敏感并去除排版空白后为 1416 个模板（607 个查询、809 个非查询）；最后一个差异来自重复/排版变体。这个数字仍包含参数化模板和少量 OCR 异常，因此只用于描述命令面规模，不作为功能完成率分母。

当前外置插件公开 8 项 WaveBench capability，直接使用约 20 个 SCPI 命令模板。它是经过实机验收的模拟波形采集 MVP，不是通用 RTM2000 远程控制层。

覆盖状态：

- **实机通过**：外置插件实现、离线测试和 RTM2032 受控实机验收均已有证据。
- **已实现**：代码和离线测试存在，但该细项没有独立实机结论。
- **部分覆盖**：只覆盖该手册功能族中一小部分。
- **未覆盖**：插件、内建 fallback 和通用 ScopeService 均无对应 API。
- **验收工具限定**：仅用于实验前后恢复或验收，不属于生产驱动 API。
- **选件/型号门控**：应先读取身份和选件，再决定是否暴露。

## 功能覆盖矩阵

| 功能域 | 手册命令面 | 当前覆盖 | 实机状态 | 主要缺口 | 建议 |
|---|---|---|---|---|---|
| 身份、同步与基本错误 | IEEE 488.2 公共命令，`SYSTem:ERRor:*` | `*IDN?`、`*OPT?`、非消费型 health snapshot、`*CLS`、`*OPC?` 等待、显式错误队列 | **实机通过** | 自检和完整事件寄存器 API 未暴露 | identity/options/health P1 已完成；EVENT 保持显式边界 |
| Acquisition 控制 | 16 个模板：模式、平均、采样率、记录长度、插值、分段和可用点数 | 只读 available/count/sample-rate 状态；`SINGle` 单次采集；显式 `AUToscale` | **部分实机通过** | 连续运行/停止、平均、分段采集、写入率和插值仍缺失 | 只读 P1 已完成；**P2**：有界 average/segmented plan |
| 模拟通道配置 | 约 48 个模板：状态、耦合、量程、比例、偏置、位置、带宽、极性、skew、标签、过载、阈值 | RTM2032 CH1/CH2 类型化只读状态；既有状态开、比例、位置归零写路径 | **实机通过** | 无阈值读回；setter 没有通用快照与回滚 | 只读 P1 已完成；写入继续受高阻和恢复策略约束 |
| 模拟波形传输 | `CHANnel<m>:DATA*`、envelope、独立 X/Y 元数据 | REAL/LSBF、header + data、`DEF/MAX/DMAX`、一次 acquisition 后逐通道读取；类型化 X/Y 缩放、点数、量化位数和 values-per-sample 快照 | **实机通过** | 无 envelope、history/segment 选择或流式块 API；不承诺跨通道硬件同步 | 波形元数据已完成；**P2**：分段/history/envelope |
| 时基、缩放与时间戳 | 12 个 timebase 模板、zoom、timestamp 导航 | 类型化 acquisition time/divisions/position/range/reference/scale/roll 只读状态；既有 `TIMebase:RANGe` 写入 | **实机通过** | 无 zoom 或 timestamp | 基础 P1 已完成；**P2**：zoom/history timestamp |
| 触发系统 | 约 159 个模板：A/B、edge、width、runt、rise time、pattern、TV、holdoff、外部和协议触发 | CH1/CH2 基础 edge-trigger 类型化只读快照；RTM2032 CH2 `EDGE/AUTO/POS/DC/level` 厂商专用受控 setter；单次采集沿用仪器当前触发设置 | **只读与 CH2 写入/恢复实机通过** | setter 仅接受健康、高阻、未过载 CH2 和当前量程内电平；无自动恢复 journal、其他 trigger 类型、B trigger 或 trigger out | P1 已完成；恢复责任保持显式，扩展写能力前另行设计事务模型 |
| 自动测量与统计 | 20 个模板：测量槽、source/main、actual、峰值、均值、标准差、波形计数 | 未暴露生产 API | **只读探测部分通过**：槽位 category 可读；未配置槽的 actual 超时 | 当前 RsInstrument 超时诊断会读取错误队列并报告 `-200/-410`，因此不能把未知配置槽当作无副作用快照 | **P1 暂停**：先取得已配置槽位和响应语法证据，或提供不自动消费错误队列的有界 query 路径；不得隐式配置/启用/复位槽位 |
| 光标 | 约 27 个模板：X/Y 光标、delta、ratio、tracking、结果 | 未覆盖 | 无 | 无光标配置或结果读取 | **P2**：先只读结果，再考虑受控定位 |
| 数学与 FFT | 约 51 个模板：表达式、math 波形、envelope、FFT window/span/RBW | 未覆盖 | 无 | 无仪器 math/FFT 配置和波形读取 | **P2**：优先只读 math/FFT waveform；保留主机 DSP 作为独立能力 |
| Spectrum / spectrogram | 107 个模板：频谱波形、频率轴、RBW、marker、history、spectrogram | 未覆盖 | 无 | 完整频谱分析应用缺失 | **P3，选件门控**：先探测选件和 `SPECtrum[:STATe]`，再设计独立 capability |
| Search | 约 119 个模板：edge/width/runt/pattern、结果和协议搜索 | 未覆盖 | 无 | 无搜索配置、结果列表或结果导航 | **P3**：依赖 history/trigger/protocol 模型成熟后再做 |
| Mask test | 约 36 个模板：mask 数据、计数、动作、保存/加载 | 未覆盖 | 无 | 无 mask 生命周期、违规计数或 action 安全模型 | **P3，破坏性动作分离**：只读结果与保存/打印/脉冲动作必须分开 |
| 数字通道 / MSO | 约 33 个模板：数字波形、阈值、技术类型、deskew、history | 未覆盖 | 无 | 无数字波形模型、逻辑位宽或阈值 API | **P3，选件门控** |
| 串行/并行总线解码 | 约 249 个模板：I²C、SPI/SSPI、UART、CAN、LIN、I²S、ARINC、MIL-STD、并行总线及帧结果 | 未覆盖 | 无 | 无总线配置、帧列表、字段解析或 history | **P3，按选件拆包**；不要放进基础 scope capability |
| 协议触发与协议搜索 | 触发和 search 内另有大量 CAN/LIN/I²C/SPI/UART/I²S/ARINC/MIL-STD 模板 | 未覆盖 | 无 | 依赖总线源、阈值、协议格式和选件探测 | **P3**：在总线只读解码之后实现 |
| DVM 与频率计数器 | 6 个 DVM、3 个 counter 模板 | 未覆盖 | 无 | 无 source/type/result/status API | **P2，选件门控**：适合小型只读 capability |
| Probe 元数据与设置 | 约 18 个模板：探头身份、衰减、带宽、阻抗、偏置、模式 | RTM2032 CH1/CH2 衰减、带宽、电容、阻抗、名称、类型只读快照 | **实机通过** | 无探头 ID 字段、DC offset、mode 或安全限值联动 | 基础 P1 已完成；ID 与安全联动后续补充，写入延后 |
| Reference curve | 约 19 个模板：source/save/load/state、缩放和数据 | 未覆盖 | 无 | 无 reference 波形读取或状态管理 | **P2**：先只读/下载，再做 save/load |
| 显示与截图 | 24 个 display 模板和 8 个 hardcopy 模板 | PNG、颜色方案、菜单开关 | **实机通过** | 无 grid、palette、persistence、XY、virtual screen、页面/打印设置 | 截图已满足 MVP；其余 **P3** |
| 仪器文件系统与导出 | 16 个 `MMEMory` 模板；波形、测量、搜索和 power 导出 | 未覆盖；WaveBench 仅保存主机侧 artifact | 无 | 仪器盘目录、复制/删除、仪器侧 CSV/报告导出均缺失 | **默认不做**；若实现需独立文件系统权限和路径沙箱 |
| Setup 快照与恢复 | `SYSTem:SET`、`MMEMory:STORE/LOAD:STATE` | 生产驱动未暴露；验收工具使用 setup blob 恢复 | **验收路径通过** | SocketIO 对 setup blob 写入曾部分生效；可靠恢复依赖受控 VXI-11 分片 | 保持 **验收工具限定**，不要伪装成普通 setter |
| 状态寄存器与健康监控 | operation/questionable/status byte、overload/mask/limit 状态 | 不消费 EVENT/错误队列的 health snapshot；通道 overload 只读 | **实机通过** | 无 mask/limit 聚合或事件寄存器 API | 基础 P1 已完成；EVENT 保持显式、消费型边界 |
| 电源分析 | 约 358 个模板：quality、harmonics、ripple、switching、SOA、efficiency、inrush、modulation 等 | 未覆盖 | 无 | 是独立应用域，涉及专用探头、deskew、报告和大量结果类型 | **P3，选件门控、独立 capability/package** |
| Calibration、reset 与系统设置 | calibration、`*RST`、preset、日期/时间、语言、蜂鸣器、教育模式 | 未覆盖 | 无 | 这些操作会改变全局状态或需要人工恢复 | **默认禁止或仅验收工具显式授权** |

## 当前直接覆盖的 SCPI 表面

当前外置驱动主要使用以下等价命令族：

```text
*IDN?  *CLS  *OPC?
SYSTem:ERRor[:NEXT]?
AUToscale  SINGle
TIMebase:RANGe
CHANnel<n>:STATE  CHANnel<n>:COUPling?
CHANnel<n>:SCALe  CHANnel<n>:POSition
FORMat[:DATA]  FORMat:BORder
CHANnel:DATA:POINTs
CHANnel<n>:DATA:HEADer?  CHANnel<n>:DATA?
HCOPy:LANGuage  HCOPy:COLor:SCHeme  HCOPy:MENU  HCOPy:DATA?
```

实现使用仪器支持的短写形式。这里按手册长写形式归一化，便于审计；它不是原始通信日志。

## WaveBench 核心已覆盖但不属于仪器 SCPI 的能力

- 采集前读取 coupling，并默认拒绝可能为 50 Ω 的 `AC` / `DC`；只有显式 opt-in 才允许继续。`ACL` / `DCL` 作为高阻路径接受。
- 将采集结果原子化落盘为 CSV、NPY、metadata、截图和脱敏命令日志；失败时保留失败元数据及已经生成的证据。
- 通过 capability 检查、受限外置插件覆盖槽位和卸载 fallback，确保未实现能力不会因为安装插件而被错误宣称。
- `AUToscale` 始终是显式动作，不会由 capture 隐式触发并改变前面板状态。

这些能力提高了实验安全性和可追溯性，但不应计入 RTM2000 手册命令覆盖率。

## 建议路线

### P1：把采集 MVP 补成可诊断的基础示波器驱动

1. `identity/options/health` 只读快照：`*OPT?`、acquisition 和非消费型 status 条件。**已完成。**
2. RTM2032 CH1/CH2 类型化模拟通道、时基和探头状态。**基础字段已完成并实机验证。**
3. 基础 edge trigger：严格只读快照与 CH2 source/type/mode/slope/coupling/level 最小受控闭环已完成；不隐式调用 find level，生产 setter 不伪装拥有持久恢复 journal。
4. 仪器自动测量只读结果与统计；与主机侧 DSP 结果明确区分来源。当前未配置槽的结果查询会超时，且 transport 诊断会消费错误队列，故在获得已配置槽位证据或非消费型 query 路径前暂停。
5. 波形缩放与形状元数据。**已完成并实机验证。** `DATA:HEADER?` 第四字段是每个 sample interval 的值数量，不是 segment ID；segment/history identity 必须走独立 history/timestamp 路径。

### P2：扩展分析与特殊采集

- average/segmented acquisition、history/timestamp；
- math/FFT/reference waveform；
- cursor、DVM、counter；
- probe 身份和衰减/阻抗只读安全联动。

### P3：按选件拆分的高级应用

- spectrum/spectrogram；
- digital/MSO 和各类 bus decode；
- protocol trigger/search；
- mask test；
- power analysis。

这些功能不应通过一个“raw SCPI”入口绕过 capability、选件探测、状态恢复和权限边界。

## 明确不计入缺陷的边界

- 手册命令索引覆盖多个 RTM2000 型号、固件和选件；未实现选件命令不等同于基础驱动缺陷。
- WaveBench 主机侧 CSV/NPY/PNG artifact 已覆盖实验结果落盘，但不等同于仪器 `MMEMory`/`EXPort` 文件系统能力。
- 主机侧 DSP 可做 FFT/THD 等分析，但不等同于仪器 `CALCulate:MATH:FFT`、`SPECtrum` 或 `POWer` 应用结果。
- setup blob 恢复是验收安全机制，不应因为手册有 `SYSTem:SET` 就直接成为生产配置 API。
- “一次 acquisition 后逐通道读取”不等同于新增或证明跨通道硬件同步保证。

## 证据边界

- 手册侧：本地保存的 RTM2000 编程手册命令索引，仅用于内部审计，不进入发行包。
- 实现侧：`driver.py` 和 `descriptor.py` 的当前外置插件实现，以及 WaveBench 内建 fallback 和 ScopeService。
- 实机侧：公开 README 中记录的 RTM2032 `DEF/MAX/DMAX`、双通道单次采集、autoscale、coupling、截图、20/20 重复采集、空错误队列和恢复结论。
- 本矩阵没有访问仪器，也没有把“代码存在”提升为“实机通过”。
