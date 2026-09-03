# RTM2000 手册功能覆盖矩阵

[English](RTM2000_COVERAGE_MATRIX_EN.md)

本页将 RTM2000 编程手册的功能域映射到外置 `wavebench-rohde-schwarz-rtm2000` 插件当前
公开的 WaveBench capability。当前包版本、依赖和入口点以 [包元数据](../pyproject.toml)为准，
型号、backend、配置字段和 capability 以
[production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py) 为准，profile
边界以 [profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py) 为准，精确 SCPI 与运行
行为以 [driver](../src/wavebench_rohde_schwarz_rtm2000/driver.py) 为准。

[功能覆盖开发路线](RTM2000_COVERAGE_MILESTONES.md)记录后续顺序和退出门；
[开发与验收存档](archive/RTM2000_README_0.15.md)保存特定版本、设备和时间点的实机与负向证据。
它们用于追溯，不会独立增加当前 capability。

## 范围

本地 RTM2000 编程手册索引覆盖多个型号、固件和选件，并包含少量重复与 OCR 异常。本矩阵按
功能域说明当前公开面，不用命令条目数量计算完成率。手册命令、driver 方法或一次实机成功均不
替代 production descriptor 声明。

`rohde-schwarz.rtm2032` 是外置插件的 canonical driver ID；短 alias `rtm2032` 属于 Core
fallback。外置插件是有界波形采集、只读状态／分析和受控视图配置实现，不是通用 RTM2000
远程控制层。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开 capability | 当前边界 |
|---|---|---|---|
| 身份、错误与健康 | IEEE 488.2、`SYSTem:ERRor:*`、status condition | `scope.idn`、`scope.errors`、`scope.snapshot`、`scope.snapshot_v2` | Snapshot V2 只保证 profile 中的 identity 字段；EVENT 和错误队列具有消费语义，不作为隐式 health 读取。 |
| Autoscale | `AUToscale` | `scope.autoscale` | 显式动作，会改变垂直、时基和触发；不会由 capture 隐式执行。 |
| Acquisition 状态 | mode、average、sample／record rate、segmented、available/count | `scope.acquisition_status` | 只读当前状态；选件相关字段先门控，不从计数或 OPC 推导未定义的完成语义。 |
| Average acquisition | average count、single count、channel arithmetic、`SINGle` | `scope.capture_average` | 调用方必须确认 acquisition 已停止；事务仅改动限定字段并恢复，结果不明会锁停对应写入。 |
| 模拟通道输入 | coupling、termination、range、scale、offset、position、bandwidth、probe | `scope.channel_coupling`、`scope.channel_input_state_v2`、`scope.snapshot` | V2 只映射 coupling／termination，数值 impedance 可为 unavailable；高阻安全策略由 Core 执行。 |
| 通道显示 | channel state | `scope.channel_display_configure_v2` | profile 只允许 CH1／CH2；Core 管理 baseline、回读、恢复与验证，插件只执行受控显示写入。 |
| 多通道 focus | time range、channel display、V/div | `scope.focus_configure_v2` | 只接受 profile 范围内的 CH1／CH2 和时基／垂直请求；不配置 position、offset、coupling、termination 或 bandwidth。 |
| 模拟波形 | REAL/LSBF、header、data、`DEF/MAX/DMAX` | `scope.fetch_waveform`、`scope.capture_waveform`、`scope.capture_waveforms` | 单次 acquisition 后逐通道读取，不新增跨通道硬件同步保证；长记录使用独立 timeout。 |
| 波形 metadata | X/Y scaling、point count、quantization、values per sample | `scope.snapshot` | Header 第四字段表示每个 sample interval 的值数量，不作为 segment ID。 |
| Timebase 与 history | range、position、zoom、history timestamp | `scope.snapshot`、`scope.history_timestamps`、`scope.focus_configure_v2` | History 先门控 K15；frame number 不替代 timestamp，timeout 后不盲目重试或清错。Zoom 未公开。 |
| Trigger | edge 与其他 trigger families | `scope.snapshot` 只读当前基础 edge 状态；capture 沿用已有设置 | Production descriptor 不声明通用 trigger 配置 capability；driver 专用方法不能当作当前 WaveBench capability。 |
| 测量统计 | slot、source、actual、聚合值、buffer | `scope.measurement_statistics`、`scope.measurement_statistics_v2` | 只读取调用方确认已配置的槽位；V2 限定 1–4 号且不支持 buffer，不配置或复位槽位。 |
| Cursor | X/Y、delta、ratio、tracking | `scope.cursor_readout` | 只读取调用方确认已配置的 cursor；不提供生产配置或定位 API。 |
| Math 与 FFT | expression、metadata、FFT state／RBW | `scope.math_metadata`、`scope.fft_status`、`scope.fft_status_v2` | V2 只返回 profile 中的字段；不配置 expression，不将主机 DSP 当作仪器 FFT 能力。 |
| Reference curve | source、state、scale、data、save/load | `scope.reference_metadata` | 只读取已有 reference；不执行 update／save／load，也不下载 payload。 |
| Digital／MSO | D0–D15 state、threshold、deskew、data | `scope.digital_status`、`scope.digital_status_v2`、`scope.digital_waveform` | 先门控 B1。Waveform 只读取已停止且满足格式前置条件的记录，不配置阈值、显示或传输格式。 |
| Spectrum、spectrogram | spectrum data、axis、RBW、marker、history | 未公开 | 属于选件相关分析应用，需要独立模型。 |
| Search、mask、protocol decode／trigger | result、navigation、action、bus configuration | 未公开 | 依赖选件、输入模型、恢复和结果合同；不通过 raw SCPI 绕过。 |
| DVM 与 counter | source、type、result、state | 未公开 | 缺少已声明的类型化 capability 与选件边界。 |
| Display 与截图 | display state、hardcopy | `scope.screenshot`、`scope.channel_display_configure_v2`、`scope.focus_configure_v2` | Screenshot 返回 PNG；未公开 grid、palette、persistence、XY、virtual screen 或 printer 设置。 |
| 仪器文件系统与导出 | `MMEMory`、instrument-side export | 未公开 | WaveBench 主机侧 artifact 不等于仪器文件系统；路径与持久写入默认拒绝。 |
| Setup 保存／恢复 | `SYSTem:SET`、state store/load | 未公开 | Setup blob 只属于验收恢复工具，不是 production 配置 API。 |
| Power analysis | quality、harmonics、ripple、switching、SOA 等 | 未公开 | 属于需要专用探头、deskew、选件和结果模型的独立应用域。 |
| Calibration、reset 与全局系统设置 | calibration、`*RST`、preset、clock、language、network | 未公开 | 会改变全局或持久状态，只能进入另行授权的维护流程。 |

## 协议与安全边界

- Driver 使用仪器支持的短写 SCPI；上表只按手册功能域建立索引。完整实际命令以
  [driver](../src/wavebench_rohde_schwarz_rtm2000/driver.py) 为准，不在本文维护第二份白名单。
- `DEF`、`MAX` 和 `DMAX` 原样传给设备；长波形读取使用 descriptor 配置的独立 timeout，
  失败的读取不会自动重放。
- Capture 前读取 coupling；Core 默认拒绝可能为 50 Ω 的 `AC`／`DC`，只有显式 opt-in
  才能继续，`ACL`／`DCL` 作为高阻路径。
- `scope.channel_display_configure_v2` 与 `scope.focus_configure_v2` 的通道、数值范围、步骤预算
  和恢复顺序由 [profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py) 定义。
- Host-side CSV／NPY／PNG artifact、DSP 分析和验收 setup 恢复不属于 RTM2000 SCPI capability。

## 相关来源

- [Production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py)
- [Descriptor profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py)
- [Driver implementation](../src/wavebench_rohde_schwarz_rtm2000/driver.py)
- [功能覆盖开发路线](RTM2000_COVERAGE_MILESTONES.md)
- [0.1.0–0.15.0 开发与验收存档](archive/RTM2000_README_0.15.md)
