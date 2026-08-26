# DSG830 插件文档

[English](README_EN.md)

这里记录 DSG830 插件的公开开发边界、离线验证和后续实机证据。厂商原文及转换稿保存在 [`vendor-local/`](vendor-local/README.md)，不进入 Git 或发行制品。

公开文档必须区分三类事实：手册声明、fake transport 离线结果和受控实机验收。手册命令或离线测试均不能单独证明 production capability。

当前公开文档：

- [DSG830 功能覆盖里程碑](DSG830_COVERAGE_MILESTONES.md)

当前包 `0.2.0` 已完成 `rf_source` M0 的离线 parser 与 descriptor 迁移。A1 受控只读实机证据已经完成并复核，production descriptor 声明 `rf_source.idn` 和 `rf_source.snapshot`；其余 capability 仍由 A2–A5 分别门控。边界与提升条件见里程碑文档。
