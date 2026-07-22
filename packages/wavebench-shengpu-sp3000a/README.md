# WaveBench SP3000A 插件（孵化中）

[English](README_EN.md)

面向 SP3000A 系列扫频仪的 WaveBench 外置插件孵化目录。首个目标型号暂定为 SP30120A。

## 当前状态

本目录目前只建立文档与资料边界，尚未创建可安装 distribution、entry point 或仪器驱动。手册协议审计和核心公共契约已经完成；RS-232 标量只读协议已部分通过实机验证，但曲线查询与精确子型号仍未确认：

- 计划 distribution：`wavebench-shengpu-sp3000a`
- 暂定 canonical driver ID：`shengpu.sp30120a`
- 计划 instrument kind：`sweep_analyzer`

`frequency_response` 是通用能力与数据域，不是第二种 instrument kind。本插件不会自行复制核心安全策略、状态恢复、报告或 artifact 逻辑。详见[远控协议与能力审计](doc/PROTOCOL_AUDIT.md)和 [RS-232 只读协议验收](doc/RS232_READONLY_ACCEPTANCE.md)。

## 手册投放位置

将本地 Markdown 手册复制到：

```text
doc/vendor-local/SP3000A_manual.md
```

`doc/vendor-local/` 中除说明文件外的内容会被 Git 忽略，不会随仓库推送。我们基于手册重新整理的能力矩阵、通信参数、SCPI 摘要、曲线格式和验收计划将放在 `doc/` 中，并清楚区分“手册声明”和“实机验证”。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地保存的厂商手册及其转写不因此获得 MIT 授权，也不属于公开 distribution 的发布内容。
