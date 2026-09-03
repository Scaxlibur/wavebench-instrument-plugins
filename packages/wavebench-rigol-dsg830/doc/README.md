# DSG830 插件文档

[English](README_EN.md)

本页将 DSG830 的当前使用合同与开发证据分开。手册命令、fake transport 测试和受控实机验收都可以支持判断，但只有 production descriptor 声明当前 capability。

## 当前 Reference

- [DSG830 capability 与 profile](reference.md)：当前型号、兼容范围、精确 profile、安全前置条件和明确拒绝项。
- [仓库级插件目录](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog.md)：由 `pyproject.toml` 与 descriptor 生成的版本、入口点和 capability 摘要。

## 历史与开发证据

- [DSG830 功能覆盖里程碑](DSG830_COVERAGE_MILESTONES.md)：A1–A5 的开发边界、验收结论和仍未开放的方向。

源码 checkout 的 [`tools/` 目录](https://github.com/Scaxlibur/wavebench-instrument-plugins/tree/main/packages/wavebench-rigol-dsg830/tools)保留 A2 输出、A3 CW、A4 调制／Pulse／Step Sweep、A4-MO、A5-0 trigger configuration 诊断和 A5 Pulse Output 的 harness 与无资源 setup 模板。`tools/` 不进入 sdist；安装包内文档应通过上述仓库链接查看这些材料。

这些记录用于追溯验收范围，不替代当前 Reference，也不授权重新执行实机 harness。

## 厂商资料

源码 checkout 中的厂商原文及转换稿保存在被忽略的 `doc/vendor-local/` 目录，不进入 Git 或 distribution。公开文档不得包含真实仪器地址、序列号、凭据、原始采集数据或实验室专用配置。

返回 [DSG830 插件入口](../README.md)。
