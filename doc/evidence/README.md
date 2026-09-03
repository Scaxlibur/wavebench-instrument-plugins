# 插件验收与历史证据

[English](README_EN.md)

本页统一导航插件仓库中的手册审计、开发里程碑、conformance、RFC 和实机验收记录。它不是
当前型号支持状态或 capability 的事实源，也不表示记录中的能力已经发布。

查询当前插件元数据和 capability 时，应使用[生成式插件目录](../reference/plugin-catalog.md)
以及对应包的 production descriptor。查询 WaveBench 公共合同和 CLI 行为时，应使用
[WaveBench Core 文档](https://github.com/Scaxlibur/wavebench/tree/master/docs)。

## 跨插件合同

- [插件侧 RFC 索引](../rfcs/README.md)：区分仍在收集证据的提案、Core 当前合同和插件侧历史记录。
- [Scope R1.3 评审正文](../archive/rfcs/WaveBench_scope通用扩展接口RFC.md)：Core 接受前的插件侧评审存档。
- [Scope R1.3 A1 验收门](../archive/rfcs/WaveBench_scope通用扩展接口RFC-R1.3-acceptance-addendum.md)：公共注册前的插件侧验收门存档。

## RIGOL

### DG4000

- [编程手册功能覆盖矩阵](../../packages/wavebench-rigol-dg4000/doc/DG4000_COVERAGE_MATRIX.md)
- [功能覆盖里程碑](../../packages/wavebench-rigol-dg4000/doc/DG4000_COVERAGE_MILESTONES.md)

### DM3000

- [编程手册功能覆盖矩阵](../../packages/wavebench-rigol-dm3000/doc/DM3000_COVERAGE_MATRIX.md)
- [功能覆盖里程碑](../../packages/wavebench-rigol-dm3000/doc/DM3000_COVERAGE_MILESTONES.md)

### DP800

- [编程手册功能覆盖矩阵](../../packages/wavebench-rigol-dp800/doc/DP800_COVERAGE_MATRIX.md)
- [指令覆盖开发里程碑](../../packages/wavebench-rigol-dp800/doc/DP800_COVERAGE_MILESTONES.md)

### DS1000Z

- [受控实机验收记录](../../packages/wavebench-rigol-ds1000z/doc/DS1000Z_HARDWARE_ACCEPTANCE.md)

### DSG830

- [当前 Reference 与历史记录索引](../../packages/wavebench-rigol-dsg830/doc/README.md)

### MSO8000

- [编程手册功能覆盖矩阵](../../packages/wavebench-rigol-mso8000/doc/MSO8104_COVERAGE_MATRIX.md)
- [功能覆盖里程碑](../../packages/wavebench-rigol-mso8000/doc/MSO8104_COVERAGE_MILESTONES.md)
- [受控实机验收记录](../../packages/wavebench-rigol-mso8000/doc/MSO8104_HARDWARE_ACCEPTANCE.md)
- [型号相关 RFC 索引](../../packages/wavebench-rigol-mso8000/doc/rfcs/README.md)

## Rohde & Schwarz

### RTM2000

- [手册功能覆盖矩阵](../../packages/wavebench-rohde-schwarz-rtm2000/doc/RTM2000_COVERAGE_MATRIX.md)
- [0.1.0–0.15.0 开发与验收存档](../../packages/wavebench-rohde-schwarz-rtm2000/doc/archive/RTM2000_README_0.15.md)

## SHENGPU

### SP3000A

- [协议审计、认证与验收索引](../../packages/wavebench-shengpu-sp3000a/doc/README.md)

## SIGLENT

### SDG2000X

- [当前 Reference、验收记录与 RFC 索引](../../packages/wavebench-siglent-sdg2000x/doc/README.md)

### SDS3000

- [编程手册基线](../../packages/wavebench-siglent-sds3000/doc/MANUAL_BASELINE.md)
- [手册指令覆盖基线](../../packages/wavebench-siglent-sds3000/doc/COMMAND_COVERAGE.md)
- [WaveBench capability 覆盖矩阵](../../packages/wavebench-siglent-sds3000/doc/WAVEBENCH_CAPABILITY_MATRIX.md)
- [实机验收记录](../../packages/wavebench-siglent-sds3000/doc/HARDWARE_ACCEPTANCE.md)
- [Core RFC 影响评估](../../packages/wavebench-siglent-sds3000/doc/WAVEBENCH_CORE_RFC.md)

### SDS800X HD

- [编程手册功能覆盖矩阵](../../packages/wavebench-siglent-sds800x-hd/doc/SDS800X_HD_COVERAGE_MATRIX.md)
- [实机验收记录](../../packages/wavebench-siglent-sds800x-hd/doc/SDS800X_HD_HARDWARE_ACCEPTANCE.md)
- [Scope R1.3 conformance 证据](../../packages/wavebench-siglent-sds800x-hd/doc/SDS800X_HD_R13_CONFORMANCE.md)
