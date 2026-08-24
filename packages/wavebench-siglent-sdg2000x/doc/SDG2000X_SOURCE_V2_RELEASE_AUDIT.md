# SDG2000X Source V2 C3 候选发布审计

[English](SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md)

## 当前状态

截至插件版本 `0.8.2`，C3 的核心实现、候选 wheel 检查和证据审核已完成；WaveBench `0.8.24`
仍是未发布开发线，因此正式发布签核尚未发生。本文件记录可离线复核的候选发布审计和精确目标的
A1／有限 A2／Basic A3 证据，不把有限证据外推为任意型号或固件的声明。

## C3 条件与当前证据

| C3 条件 | 当前离线证据 | 状态 |
| --- | --- | --- |
| 首个插件的 M5 Basic/Output 离线合同 | descriptor 声明 `source.snapshot_v2`、`source.basic_configure_v2` 与 `source.output_v2`；driver 和 core fake transport 测试覆盖查询、写入、回读不匹配和恢复分支 | A0 已完成 |
| Basic 的已声明写面 | CH1/CH2 的频率、Vpp、Sine/Square/Ramp/Pulse 函数和方波占空比均有单字段、单写、无 MAIN 查询的 fake 测试；`offset_v` 与多字段 patch 在 I/O 前拒绝；回读不匹配时最多一次 OFF，未知写结果不追加 I/O | A0 已完成 |
| Output 的已声明写面 | CH1/CH2 可同时 ON，且任一路 OFF 不影响另一路；核心 phase、写后回读不一致的一次 OFF 恢复，以及 ON/OFF 结果未知时的零重试或零追加 I/O 均有 fake 测试 | A0 已完成 |
| Harmonic 关闭的已声明写面 | `source.harmonics_disable_v2` 只在 `SDG2122X` / `2.01.01.39R7T2`、Sine、目标输出 OFF 时适用；已关闭时零 MAIN 写入，已开启时仅一条 `HARMSTATE,OFF`，核心独立回读 Harmonic 与输出；不提供配置或启用能力 | A0 已完成 |
| 版本、descriptor 和包元数据 | `pyproject.toml`、descriptor、README、覆盖矩阵和 A0 记录统一为 `0.8.2`；wheel/sdist、隔离发现、dependency/descriptor 交叉校验均有离线测试 | 离线已完成 |
| 未登记写 capability | descriptor、driver、`validate_source_descriptor()` 与 `validate_declared_capabilities()` 一起校验；未暴露 raw SCPI | 当前源码已审计 |
| Conformance manifest | 候选 wheel 内含 8 份 `wavebench.source.conformance.v1` manifest；核心已校验 `evidence_digest`、descriptor 摘要、适用域、当前 distribution 归属、`RECORD` 和 `wavebench.source.wheel-binding.v1` 摘要 | 候选包已完成 |
| A1：V2 快照 | `SDG2122X` / `2.01.01.39R7T2` 的 CH1/CH2 实机快照完成 38 查询、0 写入；快照一致且 session healthy | 已完成；不外推 |
| A2：正常 Basic／Output／Harmonic 关闭 | 同一目标上，CH1/CH2 各一次 1 Vpp Basic 写入与独立回读、各一次 Output ON/OFF，以及 CH1 一次 Harmonic 关闭均成功；最终两路 Harmonic OFF、输出 OFF，session healthy | 有限正常路径已完成；不等于完整 A2 |
| A2：故障、拒绝和恢复 | 未人为诱发传输失败、未知写结果或写后回读不一致。首次 Basic 被既有 Harmonic 状态拒绝发生在 Basic 命令发送前；因 MAIN 已进入，核心完成一次 OFF recovery | 不作为实机故障注入或 Basic 成功证据；A0 覆盖对应注入分支 |
| A3：Basic 示波器环回 | 在确认的高阻 CH1→CH1、CH2→CH2 接线下，CH1／CH2 的 Sine、Square、Ramp、Pulse 均于 2 kHz／2 Vpp 完成 scope capture；两次 Square 测得 25% 占空比，八次质量门均通过，最终两路输出 OFF | 精确工作点已完成；不外推 |
| 稳定核心与发布物签核 | 当前候选 wheel binding 为 `sha256:767c46ff3978908b681982a964a23558974be1353469b0011d3112b9cec57d6e`；WaveBench `0.8.24` 仍是开发线，未执行 push、tag、发布或正式签核 | 待发布时完成 |

8 份 manifest 按真实证据分别声明：Basic 配置 A3；Basic／Output／Harmonic 读取 A1；Output
Enable／Disable A2；CH1 Harmonic Disable A2；CH2 Harmonic Disable A0。CH1 的实机关闭证据没有
外推到 CH2，A3 也没有外推到 Output 或 Harmonic。

## A0 的验证范围

离线测试只证明协议合同和核心调用边界：

- `source.snapshot_v2` 的 anchor/facet/anchor 计划、查询预算、deadline 和零写入；
- `source.basic_configure_v2` 的已审计 `BSWV` 写形式、写前拒绝、可读回读不匹配时的一次 OFF 恢复，以及未知写结果的零追加 I/O；
- `source.output_v2` 的单写 MAIN、独立 postcondition、可读回读失败时的 OFF 恢复，以及 ON/OFF 结果未知时的零重试或零追加 I/O；
- `source.harmonics_disable_v2` 在精确运行时目标上的零写入幂等分支、单条 `HARMSTATE,OFF` 写入、模型/固件拒绝和 Harmonic/输出独立回读；
- wheel/sdist 元数据、entry point、版本门和 descriptor 交叉校验。

这些结果不证明真实仪器接受命令、输出继电器转换、接线正确或波形测量值。

## 正式发布前仍需完成的项目

1. 发布或冻结 WaveBench `0.8.24`，使用完全相同的插件源码重建最终 wheel；任何受 wheel binding
   约束的成员发生变化时，必须重新生成并审核 manifest 摘要。
2. 对实际发布的同一份 wheel 重跑包检查和隔离安装，再执行 push、tag、发布与正式签核。

超出 A3 的实机故障注入若有需要，必须单独授权；当前 C3 不把它作为最小安全闭环的替代品。
本审计没有修改 `wavebench.toml`、连接仪器或执行发布，也不替代任何恢复步骤。
