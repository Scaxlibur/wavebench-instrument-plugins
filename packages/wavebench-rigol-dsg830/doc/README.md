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
CW 环回验收使用。A3 已完成并经复核，production descriptor 现在声明 `rf_source.cw_configure`；调制、Pulse、Sweep
和 trigger 仍保持关闭。

当前包 `0.2.0` 已完成 `rf_source` M0 的只读迁移、M1 CW 映射、M2 输出事务和 M3 内部 Sine AM／FM／PM 离线映射。A1、A2 与 A3 受控实机证据已经完成并复核，production descriptor 声明 `rf_source.idn`、`rf_source.snapshot`、`rf_source.cw_configure` 和 `rf_source.output`；`rf_source.modulation_configure` 仍由 A4 门控，M4／外部 trigger 继续由 A4–A5 门控。边界与提升条件见里程碑文档。
