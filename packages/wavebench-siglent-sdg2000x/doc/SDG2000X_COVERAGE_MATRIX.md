# SDG2000X 功能覆盖矩阵

[English](SDG2000X_COVERAGE_MATRIX_EN.md)

## 当前结论

版本 `0.8.2` 声明 12 项 capability：既有的身份、状态、五项基础写能力和任意波只读探测，以及
`source.snapshot_v2`、`source.basic_configure_v2`、`source.output_v2` 和 `source.harmonics_disable_v2`。前 8 项已有 `SDG2122X`
核心消费路径实机证据；新增 4 项均有 A0 离线合同。对精确的 `SDG2122X`／`2.01.01.39R7T2` 目标，已完成 V2 快照的
A1，以及 Basic、Output 和 Harmonic 关闭正常路径的有限 A2；该证据不外推到其它型号、固件、功能字段或故障恢复。
其中 Harmonic 关闭仅对 `SDG2122X` 固件 `2.01.01.39R7T2` 适用。三个登记型号的
V1 capability 仍按共同手册合同和离线型号矩阵放行。

Source V2 的 C3 仍未完成。离线审计以及精确目标的 A1／有限 A2 记录均已具备；A3 示波器环回、稳定核心、最终发行物和签核仍待完成，详见 [C3 发布审计准备](SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)。

高级命令域已完成尽可能全面的分域协议/A4 验收，但核心缺少无损状态模型时继续不声明写 capability，也不提供 raw SCPI。历史覆盖率数字只对应版本 `0.8.0`；新增 Source V2 代码的当前覆盖率以本次离线测试报告为准，不用旧数字替代验证。代码覆盖不替代未接外部端口和未持有型号的物理证据。

## 覆盖状态

| 命令域 | WaveBench capability | 当前状态 | 放行条件 |
| --- | --- | --- | --- |
| 仪器身份 | `source.idn` | `SDG2122X` / `2.01.01.39R7T2` 实机通过；其它登记型号按共同协议放行 | 新型号或协议变体仍需脱敏证据 |
| 系统错误队列 | 无 | 未开放 | 确认查询命令、空队列语义和是否为消费型读取 |
| 通道基础状态 | `source.status` | SDG2122X 多轮只读稳定；CH1/CH2 均完成频率、Vpp、均值和最终独立零写审计 | 新固件响应变体需单独验收 |
| Source V2 快照 | `source.snapshot_v2` | A0 完成：CH1/CH2 纯读取 anchor/facet/anchor、38 查询 Sine fixture、0 写入，声明上限为 44；A1：精确目标实机双通道 38 查询、0 写入，快照一致且 session healthy | 其它型号、固件或响应变体单独验收 |
| Source V2 基础配置 | `source.basic_configure_v2` | A0 完成：CH1/CH2 的 Sine/Square/Ramp/Pulse 单字段 Basic MAIN 写入、核心回读与一次 OFF 恢复；`offset_v` 暂在写前拒绝。有限 A2：精确目标在输出 OFF 时对 CH1/CH2 各完成一次 1 Vpp 单字段写入及独立回读 | A3 通过示波器环回确认频率、Vpp、函数和占空比；不声明实机拒绝或故障恢复分支 |
| Source V2 输出 | `source.output_v2` | A0 完成：CH1/CH2 独立 ON/OFF、单写 MAIN、核心回读、可读不匹配时一次 OFF 恢复；独立端口可同时 ON。有限 A2：精确目标的 CH1、CH2 分别完成 ON 与 OFF 及独立回读，最终均 OFF | 不声明实机同时 ON、故障恢复或其它型号／固件结果 |
| 输出控制 | `source.output` | 三个型号通过离线合同；SDG2122X CH1/CH2 通过核心 Service ON→A4→OFF，未知写结果为 0 | 其它型号 A4 仅在有样机时补充 |
| 固定波频率 | `source.set_frequency` | SDG2122X CH1/CH2 均覆盖 OFF 写入和 ON 状态实时写入；按型号/函数边界离线全覆盖 | 其它型号 A4 仅在有样机时补充 |
| 固定波幅度 | `source.set_amplitude_vpp` | SDG2122X CH1/CH2 均覆盖 OFF 与 ON 实时写入；2 mVpp–10 Vpp、偏置包络和漂移分支 100% 覆盖 | 其它型号 A4 仅在有样机时补充 |
| 固定波函数 | `source.set_function` | Sine/Square/Ramp 在 CH1/CH2 经核心闭环；Pulse 在 CH2 闭环；Noise/DC 只允许 OFF 配置 | Noise/DC 等待可复用安全模型 |
| 方波占空比 | `source.set_square_duty_cycle` | CH2 20%/80% 实测 0.200/0.800；最终 CH1 30%、CH2 70% 实测 0.287/0.6949 | 高频频率相关钳位仍由严格回读 fail closed |
| Pulse 参数 | 无损 capability 暂缺 | SDG2122X 25%/65% 占空比、20/40 µs 边沿通过 A4；DLY 仅 A3 | Source V2 支持未知 hold 后再声明；补独立延迟参考 |
| 谐波 | `source.harmonics_disable_v2`，仅 `SDG2122X` / `2.01.01.39R7T2` | A0：在 Sine、目标输出 OFF 时，已关闭为零写入，已开启仅发送一条 `HARMSTATE,OFF`，并由核心独立回读 Harmonic 与输出。A1／有限 A2：精确目标的 Harmonic facet 可读，CH1 完成一次关闭写入并独立回读 Harmonic OFF／输出 OFF；SDG2122X H2–H16 槽位、H2/H3 幅度、H2 相位和 ALL/EVEN/ODD 仍是旧 A4 证据 | Harmonic 配置／启用继续等待更完整的 Source V2 模型；不外推到其它型号或固件 |
| 调制 | 无损 capability 暂缺 | SDG2122X 内部 AM/DSB-AM/FM/PM/PWM/ASK/FSK/PSK 均通过协议与 A4 波形 | Source V2 支持关闭态缺省与厂商范围后再声明；外部源需接线 |
| Sweep | 无损 capability 暂缺 | SDG2122X LINE/LOG/STEP、UP/DOWN/UP_DOWN 与 INT/MAN 通过协议和 A4 波形；EXT 仅回读 | Source V2 支持字段缺省后再声明；补外部触发线 |
| Burst | 无损 capability 暂缺 | 有限 INT/MAN 通过周期数/重复周期 A4；`TRDUCH` CH2→双路通过；EXT/Gate 仅回读；INF 未形成连续载波 | 补外部触发/门控接线；Source V2 采用判别联合 |
| Noise / DC / TARB | 无损 capability 暂缺 | Noise 与 -1/0/+1 V DC 通过 A4；20 MHz 下限钳位 A3；TARB 1 MSa/s 非平坦输出通过；Noise Add 在样机上稳定保持 OFF | 使用非周期 amplitude facet；Noise Add 需其它固件复核 |
| 任意波形 | `source.arbitrary_probe` | 双通道核心零写探测通过；内置目录 199/199 选择、回读与 A4；TARB 另有 A4 | 上传、删除和用户目录继续默认拒绝 |
| Combine | 无损 capability 暂缺 | CH1←CH2 与 CH2←CH1 双向异频 A4；源通道输出继电器无需开启 | 建模参与通道、最坏包络和互斥状态后再声明 |
| 相位模式 / Invert | 无损 capability 暂缺 | `EQPHASE` 后差 0.27°；CH1/CH2 反相约 179.9°；实机 token 为 `PHASE-LOCKED` | 拆分单字段 polarity/phase facet 后再声明 |
| 跟踪 / 耦合 / 复制 | 无损 capability 暂缺 | TRACE、F/P/A ratio/deviation、CH1→CH2 PACP 均有 A4；反向 PACP 有 A3 | Source V2 表达条件字段、动作和跨通道事务 |
| Sync / Counter / 时钟 / Cascade | 无 | 18 查询零写轮次通过；Sync 与 Counter OFF、ROSC INT、Cascade OFF；未接端口不宣称 A4 | 补 Sync、Counter、外部参考和第二台源的专用接线 |
| 代码路径 | 不适用 | V1 历史版本为 348 项测试、620/620 statements、244/244 branches；本次新增 V2 A0 测试单独执行 | 运行当前插件测试与覆盖率报告；不以空断言刷数值 |

## 默认拒绝项

- 不发送 `*RST` 或其它全局预置命令。
- 面向用户的输出开启只能经 `source.output` 或 `source.output_v2` 的核心 operation contract 执行；高级实机脚本不是公共 raw 接口。
- 不提供 raw SCPI 入口。
- 不上传、不删除、不覆盖用户任意波或状态文件。
- 不为覆盖率切换外部参考、保护、Counter、Cascade 或未知负载的辅助输出。
- 不把产品页列出的功能直接等同于已实现 capability。

## 事实源

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- 本地编程手册：`doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`，修订号 `PG02_E05C`
- [协议审计](SDG2000X_PROTOCOL_AUDIT.md)
- [只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)
- [输出控制实机验收](SDG2000X_OUTPUT_ACCEPTANCE.md)
- [频率写入实机验收](SDG2000X_FREQUENCY_ACCEPTANCE.md)
- [基础写入实机验收](SDG2000X_BASIC_WRITE_ACCEPTANCE.md)
- [Source V2 A0 离线适配记录](SDG2000X_SOURCE_V2_A0.md)
- [Source V2 A1／A2 实机验收](SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE.md)
- [Source V2 C3 发布审计准备](SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)
- [谐波协议与频谱验收](SDG2000X_HARMONIC_ACCEPTANCE.md)
- [调制协议与波形验收](SDG2000X_MODULATION_ACCEPTANCE.md)
- [Sweep 协议与波形验收](SDG2000X_SWEEP_ACCEPTANCE.md)
- [Burst 协议与波形验收](SDG2000X_BURST_ACCEPTANCE.md)
- [Pulse 协议与波形验收](SDG2000X_PULSE_ACCEPTANCE.md)
- [任意波只读探测验收](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE.md)
- [内置任意波全目录验收](SDG2000X_BUILTIN_ARB_ACCEPTANCE.md)
- [公共 Source 接口双通道验收](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE.md)
- [特殊波形协议与实机验收](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE.md)
- [双通道波形合成验收](SDG2000X_COMBINE_ACCEPTANCE.md)
- [相位模式、等相位与反相验收](SDG2000X_PHASE_INVERT_ACCEPTANCE.md)
- [通道跟踪、耦合、复制与双通道触发验收](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE.md)
- [辅助与全局状态只读验收](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE.md)
- [Source V2 通用 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)
- 当前 descriptor、driver 和 fake transport 测试
