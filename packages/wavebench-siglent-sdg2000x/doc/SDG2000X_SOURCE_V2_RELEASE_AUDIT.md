# SDG2000X Source V2 C3 发布审计准备

[English](SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md)

## 当前状态

截至插件版本 `0.8.1`，C3 尚未完成。本文件只记录可离线复核的发布准备情况，并把 A0 与需要真实设备的
A1–A3 分开。它不是发布签核、wheel conformance manifest，也不构成任何型号或固件的实机声明。

## C3 条件与当前证据

| C3 条件 | 当前离线证据 | 状态 |
| --- | --- | --- |
| 首个插件的 M5 Basic/Output 离线合同 | descriptor 声明 `source.snapshot_v2`、`source.basic_configure_v2` 与 `source.output_v2`；driver 和 core fake transport 测试覆盖查询、写入和恢复分支 | A0 已完成 |
| Basic 的已声明写面 | 频率、Vpp、Sine/Square/Ramp/Pulse 函数和方波占空比均有单字段、单写、无 MAIN 查询的 fake 测试；`offset_v` 与多字段 patch 在 I/O 前拒绝 | A0 已完成 |
| Output 的已声明写面 | CH1/CH2 可同时 ON，且任一路 OFF 不影响另一路；核心 phase、写后回读不一致的一次 OFF 恢复，以及 poisoned transport 的零追加 I/O 均有 fake 测试 | A0 已完成 |
| 版本、descriptor 和包元数据 | `pyproject.toml`、descriptor、README、覆盖矩阵和 A0 记录统一为 `0.8.1`；wheel/sdist、隔离发现、dependency/descriptor 交叉校验均有离线测试 | 离线已完成 |
| 未登记写 capability | descriptor、driver、`validate_source_descriptor()` 与 `validate_declared_capabilities()` 一起校验；未暴露 raw SCPI | 当前源码已审计 |
| A1、A2、A3 | 尚未执行真实设备的只读、输出转换/恢复和示波器环回验证 | 待单独授权 |
| 稳定核心与发布物签核 | WaveBench `0.8.24` 仍是开发线；没有最终插件 wheel 摘要、A1–A3 manifest 或发布签核 | 待完成 |

## A0 的验证范围

离线测试只证明协议合同和核心调用边界：

- `source.snapshot_v2` 的 anchor/facet/anchor 计划、查询预算、deadline 和零写入；
- `source.basic_configure_v2` 的已审计 `BSWV` 写形式及写前拒绝；
- `source.output_v2` 的单写 MAIN、独立 postcondition、已知回读失败的 OFF 恢复，以及 poisoned
  session 的 close-only 行为；
- wheel/sdist 元数据、entry point、版本门和 descriptor 交叉校验。

这些结果不证明真实仪器接受命令、输出继电器转换、接线正确或波形测量值。

## C3 前仍需完成的项目

1. A1：在单独授权的型号、固件、resource 和 transport/backend 上确认 V2 snapshot 响应与查询预算。
2. A2：确认 V2 Basic/Output 的完成状态、独立回读、拒绝分支和 OFF 恢复；未知传输结果保持 poisoned，
   不执行未经授权的额外 I/O。
3. A3：通过示波器通道环回确认已声明写入的频率、Vpp、函数和占空比，并记录输出前读取到的偏置、端接、限制、容差和最终 OFF 状态。
4. 使用稳定核心和最终插件 wheel 生成与审核 conformance manifest，再执行实际发布签核。

实机项需要新的明确授权。本审计不修改 `wavebench.toml`，不连接仪器，也不替代任何恢复步骤。
