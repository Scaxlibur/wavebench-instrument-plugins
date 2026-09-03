# SDG2000X 插件文档

[English](README_EN.md)

本页将 SDG2000X 的当前使用合同与开发、协议和实机证据分开。production descriptor 声明当前 capability；验收记录保留特定型号、固件、接线和时间点的证据，不独立提升公共能力。

## 当前 Reference

- [SDG2000X 当前能力 Reference](SDG2000X_COVERAGE_MATRIX.md)：当前 capability、Source V2 型号／固件限制、安全行为和明确拒绝项。
- [仓库级插件目录](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog.md)：由 `pyproject.toml` 与 descriptor 生成的版本、入口点和 capability 摘要。

## 开发与合同记录

- [协议审计](SDG2000X_PROTOCOL_AUDIT.md)
- [覆盖里程碑](SDG2000X_COVERAGE_MILESTONES.md)
- [Source V2 A0 离线适配记录](SDG2000X_SOURCE_V2_A0.md)
- [Source V2 A1／A2 实机验收](SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE.md)
- [Source V2 A3 实机波形验收](SDG2000X_SOURCE_V2_A3_ACCEPTANCE.md)
- [Source V2 C3 候选包审计](SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)
- [Source V2 能力、状态与复合输出安全 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)

这些页面记录实施与评审过程。当前实现与文档冲突时，以包元数据、production descriptor、driver 和测试为准。

## 基础接口验收证据

- [只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)
- [输出控制实机验收](SDG2000X_OUTPUT_ACCEPTANCE.md)
- [频率写入实机验收](SDG2000X_FREQUENCY_ACCEPTANCE.md)
- [基础写入实机验收](SDG2000X_BASIC_WRITE_ACCEPTANCE.md)
- [公共 Source 接口双通道验收](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE.md)

## 高级命令域证据

- [谐波协议与频谱验收](SDG2000X_HARMONIC_ACCEPTANCE.md)
- [调制协议与波形验收](SDG2000X_MODULATION_ACCEPTANCE.md)
- [Sweep 协议与波形验收](SDG2000X_SWEEP_ACCEPTANCE.md)
- [Burst 协议与波形验收](SDG2000X_BURST_ACCEPTANCE.md)
- [Pulse 协议与波形验收](SDG2000X_PULSE_ACCEPTANCE.md)
- [任意波只读探测验收](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE.md)
- [内置任意波全目录验收](SDG2000X_BUILTIN_ARB_ACCEPTANCE.md)
- [特殊波形协议与实机验收](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE.md)
- [双通道波形合成验收](SDG2000X_COMBINE_ACCEPTANCE.md)
- [相位模式、等相位与反相验收](SDG2000X_PHASE_INVERT_ACCEPTANCE.md)
- [通道跟踪、耦合、复制与双通道触发验收](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE.md)
- [辅助与全局状态只读验收](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE.md)

高级命令域存在验收证据，不表示对应公共 capability 已进入 production descriptor。

## 厂商资料

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- 源码 checkout 中的 `doc/vendor-local/` 使用说明

`doc/vendor-local/` 只存在于源码 checkout；厂商原文和转换稿不进入 Git 或 distribution。返回 [SDG2000X 插件入口](../README.md)。
