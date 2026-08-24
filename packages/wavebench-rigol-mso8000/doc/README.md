# MSO8000 插件文档

这里放公开的覆盖矩阵、命令索引、测试说明和实机验收记录。厂商手册原文及其转换稿放在 `vendor-local/`，不进入公开发行物。

公开文档必须区分三类事实：手册声明、FakeTransport 测试结果和真实仪器验收结果。不能把手册中列出的命令直接写成已支持能力。

当前公开文档：

- [MSO8104 功能覆盖里程碑](MSO8104_COVERAGE_MILESTONES.md)
- [MSO8104 编程手册功能覆盖矩阵](MSO8104_COVERAGE_MATRIX.md)
- [MSO8104 受控实机验收记录](MSO8104_HARDWARE_ACCEPTANCE.md)

实机结论仅适用于记录中的型号、固件、transport 和受控步骤。当前 waveform binary 读取受 [RFC-0008](rfcs/0008-bounded-waveform-block-trailing-contract.md) 阻断，不把身份或输入安全验证扩展为波形采集成功。
