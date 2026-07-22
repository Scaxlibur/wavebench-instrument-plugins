# WaveBench SP3000A 插件（孵化中）

[English](README_EN.md)

面向 SP3000A 系列扫频仪的 WaveBench 外置插件孵化目录。首个目标型号暂定为 SP30120A。

## 当前状态

本目录目前只建立文档与资料边界，尚未创建可安装 distribution、entry point 或仪器驱动。以下标识均为开发暂定值，需在手册审计和实机身份查询后冻结：

- 计划 distribution：`wavebench-shengpu-sp3000a`
- 暂定 canonical driver ID：`shengpu.sp30120a`
- 候选 instrument kind：`sweep_analyzer` 或 `frequency_response`

WaveBench 是否需要新增 instrument kind、扫描计划和复数频率响应数据模型，必须先在核心仓库评审；本插件不会自行复制核心安全策略、状态恢复、报告或 artifact 逻辑。

## 手册投放位置

将本地 Markdown 手册复制到：

```text
doc/vendor-local/SP3000A_manual.md
```

`doc/vendor-local/` 中除说明文件外的内容会被 Git 忽略，不会随仓库推送。我们基于手册重新整理的能力矩阵、通信参数、SCPI 摘要、曲线格式和验收计划将放在 `doc/` 中，并清楚区分“手册声明”和“实机验证”。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地保存的厂商手册及其转写不因此获得 MIT 授权，也不属于公开 distribution 的发布内容。
