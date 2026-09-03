# SP3000A 开发文档

[English](README_EN.md)

本目录用于维护项目原创、可公开的 SP3000A 插件开发资料。当前 capability 仍以 production
descriptor 为准；审计、计划和验收记录不独立提升公共能力。

## 当前 Reference

- [命令认证矩阵](COMMAND_CERTIFICATION_MATRIX.md)：记录命令级实现与证据状态。

## 审计与计划

- [远控协议与能力审计](PROTOCOL_AUDIT.md)
- [命令认证计划](COMMAND_CERTIFICATION_PLAN.md)

## 历史验收证据

- [RS-232 只读协议验收](RS232_READONLY_ACCEPTANCE.md)

开发资料按以下顺序整理：

1. 型号、固件、接口和阻抗能力矩阵；
2. LAN、USB Device、RS-232 与可选 GPIB 的通信参数；
3. 身份、错误队列、扫描配置和只读状态命令；
4. 幅频、相频及曲线数据读取格式；
5. 直通校准、DUT 测试和交叉验证的分级验收计划。

文档必须标注信息来源和验证状态，不把手册中的能力直接写成实机已通过。完整本地手册放在
[`vendor-local/`](vendor-local/README.md)，不会提交到 Git。
