# SDG2000X Source V2 A0 离线适配记录

[English](SDG2000X_SOURCE_V2_A0_EN.md)

## 结论

插件版本 `0.8.1` 声明 `source.snapshot_v2`、`source.basic_configure_v2`、`source.output_v2` 与
`source.harmonics_disable_v2`。本记录只证明 A0 离线合同：描述符、查询计划、SCPI 格式、发送次数、核心 phase
授权、失败前拒绝和故障注入后的失败关闭均由 fake transport 验证。它不构成任一型号或固件的 Source V2 实机验收。

已有的 SDG2122X V1 验收继续是旧 capability 的设备证据，不能替代 Source V2 的 A1、A2 或 A3。

## 已实现范围

- `source.snapshot_v2`：对 CH1 与 CH2 执行纯读取 anchor/facet/anchor 计划；不发送 selector 或配置写入。
- `source.basic_configure_v2`：仅覆盖 Sine、Square、Ramp、Pulse 的函数、频率、Vpp 幅度和方波占空比。
  单次请求只接受一个 `SET` 字段；`offset_v` 写入尚无已验证的 SCPI 证据，因此在任何写入前拒绝。
- `source.output_v2`：支持两个物理通道各自 ON/OFF。独立通道可以同时 ON；插件未增加全局单通道限制。
- `source.harmonics_disable_v2`：只关闭已读到的 Harmonic 状态，不配置或启用 Harmonic。它仅适用于
  `SDG2122X` 固件 `2.01.01.39R7T2` 的 CH1/CH2，且要求 Sine 与目标输出 OFF。已关闭时 MAIN 不写入；已开启时只发送一条
  `C<n>:HARM HARMSTATE,OFF`，随后由核心独立回读 Harmonic 与输出状态。
- V2 MAIN 阶段只发送一个已审计的 `BSWV`、`OUTP` 或 `HARM` 写命令。最终状态由核心随后发起独立快照回读。

启用输出仍要求当前通道处于 FIX、Sweep OFF、Vpp 与 Offset 可读、显示负载为高阻且已知高级模式关闭。
关闭输出不依赖 Vpp、Offset 或负载信息，并可作为核心失败恢复的单次 OFF 写入。Basic 或 Output 的可读回读不匹配时，
核心最多尝试一次 V2 OFF；写入结果未知而 session 已 poisoned 时，不发送额外 OFF。OFF 本身的未知结果也不重试。

## 查询与发送次数

每个 anchor phase 先读取一次 `*IDN?`，再对每个通道读取 `OUTP?`、`BSWV?`、`SWWV?`、调制、Burst、
Harmonic（仅 Sine）、Combine、Noise Add 与 Coupling 状态。Output 与 Harmonic facet 均复用同一通道 Basic 快照，
不增加额外 `OUTP?` 或 `HARM?`。

在两个通道均为 Sine 的 A0 fixture 中，完整 Source V2 快照发送 38 次查询、0 次写入，低于 descriptor
声明的 44 次查询上限。Basic、Output 与 Harmonic 关闭的 MAIN 测试分别证明写入期间不附带 driver 查询。核心负责在执行记录返回后
验证计划 deadline 和查询预算；该验证不替代真实设备的 A1 查询证据。

## Noise、DC 与 V1 兼容

当前 SDG2000X `BSWV?` 对 Noise 返回 `STDEV`，对 DC 或 Noise 不一定返回最终 Vpp 与 Offset。插件不会把
这些值猜测或换算为 Vpp。因此它们不在当前 V2 Basic profile 内，也不作为 V2 输出开启的可证明状态。

核心对这类无法无损表达的旧 `set_function` 调用保留 V1 setter：Sine 转 Noise，以及 Noise/DC 转可证明的
周期波，均继续执行原有的输出 OFF 事务。可由 V2 profile 完整表达的周期波调用仍进入 V2 事务。该分流不为
Noise 增加 RMS、峰值因子或统计安全模型。

## 尚未完成的门

- A1：在明确型号、固件、resource 与 transport/backend 后，确认 V2 snapshot 的真实响应、查询预算和 Harmonic 状态 facet。
- A2：验证 V2 Output 的 ON/OFF、独立回读和 OFF 恢复；同时确认 V2 Basic 的命令接受与回读形态，以及精确运行时目标上的 Harmonic 关闭与回读。
- A3：通过示波器通道环回确认 V2 Basic 已声明写入的频率、Vpp、函数和占空比，并记录偏置、端接、容差和最终 OFF 状态。

timeout、断连和未知写结果的故障注入属于 A0 合同；真实 transport 故障若另行验证，必须单独记录，且不替代 A1–A3。

实机测试需另行授权，且不得把离线 fixture 当作设备行为证据。
