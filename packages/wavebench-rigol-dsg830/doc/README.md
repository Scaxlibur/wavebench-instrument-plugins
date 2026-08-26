# DSG830 插件文档

[English](README_EN.md)

这里记录 DSG830 插件的公开开发边界、离线验证和后续实机证据。厂商原文及转换稿保存在 [`vendor-local/`](vendor-local/README.md)，不进入 Git 或发行制品。

公开文档必须区分三类事实：手册声明、fake transport 离线结果和受控实机验收。手册命令或离线测试均不能单独证明 production capability。

当前公开文档：

- [DSG830 功能覆盖里程碑](DSG830_COVERAGE_MILESTONES.md)

源码 checkout 还提供不含资源地址的
[`A2 本地证据 setup 模板`](../tools/a2_output_evidence.setup.template.toml)。A2 harness 与回归测试已经实现，
但实机证据尚未执行，production descriptor 仍不声明 `rf_source.output`。

当前包 `0.2.0` 已完成 `rf_source` M0 的只读迁移、M1 离线 CW 映射和 M2 离线输出事务。A1 受控只读实机证据已经完成并复核，production descriptor 只声明 `rf_source.idn` 和 `rf_source.snapshot`；M1／M2 仍只用于 fake descriptor，所有写 capability 继续由 A2–A5 分别门控。边界与提升条件见里程碑文档。
