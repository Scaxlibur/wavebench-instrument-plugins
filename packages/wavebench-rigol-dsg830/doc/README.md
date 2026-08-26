# DSG830 插件文档

[English](README_EN.md)

这里记录 DSG830 插件的公开开发边界、离线验证和后续实机证据。厂商原文及转换稿保存在 [`vendor-local/`](vendor-local/README.md)，不进入 Git 或发行制品。

公开文档必须区分三类事实：手册声明、fake transport 离线结果和受控实机验收。手册命令或离线测试均不能单独证明 production capability。

当前公开文档：

- [DSG830 功能覆盖里程碑](DSG830_COVERAGE_MILESTONES.md)

源码 checkout 还提供不含资源地址的
[`A2 本地证据 setup 模板`](../tools/a2_output_evidence.setup.template.toml)。A2 harness 与回归测试已用于完成
受控实机验收；production descriptor 现在声明 `rf_source.output`，但 CW 和后续 RF 写 capability 仍保持关闭。

[`A3 本地证据 setup 模板`](../tools/a3_cw_evidence.setup.template.toml) 与对应 harness 已加入源码 checkout，供下一次
CW 环回验收使用。它已通过离线回归，但尚未产生实机证据；因此 production descriptor 仍不声明
`rf_source.cw_configure`。

当前包 `0.2.0` 已完成 `rf_source` M0 的只读迁移、M1 离线 CW 映射和 M2 输出事务。A1 与 A2 受控实机证据已经完成并复核，production descriptor 声明 `rf_source.idn`、`rf_source.snapshot` 和 `rf_source.output`；A3 的本地准备已完成，但 M1 的 CW 写入与 M3／M4 capability 仍分别由 A3–A5 实机证据门控。边界与提升条件见里程碑文档。
