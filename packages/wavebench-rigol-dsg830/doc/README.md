# DSG830 插件文档

[English](README_EN.md)

这里记录 DSG830 插件的公开开发边界、离线验证和后续实机证据。厂商原文及转换稿保存在 [`vendor-local/`](vendor-local/README.md)，不进入 Git 或发行制品。

公开文档必须区分三类事实：手册声明、fake transport 离线结果和受控实机验收。手册命令或离线测试均不能单独证明 production capability。

当前公开文档：

- [DSG830 功能覆盖里程碑](DSG830_COVERAGE_MILESTONES.md)

源码 checkout 还提供不含资源地址的
[`A2 本地证据 setup 模板`](../tools/a2_output_evidence.setup.template.toml)。A2 harness 与回归测试已用于完成
受控实机验收；production descriptor 现在声明 `rf_source.output`。

[`A3 本地证据 setup 模板`](../tools/a3_cw_evidence.setup.template.toml) 与对应 harness 已加入源码 checkout，供下一次
CW 环回验收使用。A3 已完成并经复核，production descriptor 现在声明 `rf_source.cw_configure`；M3 调制、Pulse 与 Step Sweep 的提升均由各自的 A4 证据单独决定，调制输出、Sweep execute／fire 和 trigger 仍保持关闭。

[`A4 本地证据 setup 模板`](../tools/a4_modulation_evidence.setup.template.toml) 与对应 harness 已完成受控硬件验收。它每次只配置一个内部 Sine AM／FM／PM 模式，配置读回后关闭同一模式，最终 snapshot 必须确认 RF 输出与调制均关闭；不读取 scope，不调用 RF 输出控制。AM／FM／PM 序列均已通过。PM 的 production profile 固定为 `1.25 rad`，使 capability 与严格读回证据保持一致。显式 `--recover` 只生成私有恢复记录；显式 `--diagnose` 保留 `read_only` 配置，读取指定模式 profile 与初始／最终 RF snapshot，并以零写 audit 记录诊断结果。两类记录都不构成新的 capability 提升证据。

[`A4 Pulse 本地证据 setup 模板`](../tools/a4_pulse_evidence.setup.template.toml) 与对应 harness 已完成受控实机验收。它只验证 `rf_out` 的 internal／single Pulse 配置：初始、写后与最终 snapshot 都必须确认 RF 输出、调制、Pulse、Sweep 关闭且无活动 protection。`--execute` 固定配置 period、width、polarity 并保持 Pulse OFF；`--diagnose` 保持 `read_only` 且零写。工具不读取 scope、不调用 RF output、不使用后面板 Pulse I/O 或 trigger。normal／inverted 两种 polarity 均通过独立配置、读回、最终关闭与审计复核，证据已将 `rf_source.pulse_configure` 提升到 production descriptor；historical harness 在提升后会拒绝重跑。

当前包 `0.2.0` 已完成 `rf_source` M0 的只读迁移、M1 CW 映射、M2 输出事务、M3 内部 Sine AM／FM／PM 映射及按模式关闭，以及 M4 internal／single Pulse 与 frequency-only Step Sweep 的实机验收。A1、A2、A3、A4 调制／Pulse／Step Sweep 受控实机证据已经完成并复核，production descriptor 声明 `rf_source.idn`、`rf_source.snapshot`、`rf_source.cw_configure`、`rf_source.output`、`rf_source.modulation_configure`、`rf_source.pulse_configure` 和 `rf_source.sweep_configure`。A5-0 已提供逻辑 trigger configuration 的严格只读 query 映射，但 production descriptor 不声明 `rf_source.trigger_snapshot`，也不把 `rf_out` 作为物理 trigger／sync connector。PM production profile 仅为 `1.25 rad`；`rf_source.modulation_disable`、调制开启时的 RF 输出、外部 trigger、Sweep execute／fire、Level Sweep 与 list 继续由独立 A4–A5 证据门控。边界与提升条件见里程碑文档。

源码 checkout 已提供 A4 Step Sweep 的 [本地证据 setup 模板](../tools/a4_step_sweep_evidence.setup.template.toml) 与对应 harness。它只验证 RF-OFF／Sweep-OFF 的 frequency-only profile，不读取 Scope、不调用 RF output、不 arm／fire 或 trigger；诊断路径零写，执行路径须显式授权。零写诊断与受控配置均已通过并完成最终关闭复核，`rf_source.sweep_configure` 已提升到 production descriptor；historical harness 会拒绝重跑。
