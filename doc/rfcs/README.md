# 接口 RFC

本目录保存从仪器插件实现和实机验收中形成的 WaveBench 公共接口提案及其评审历史。已经由
核心接受的合同以核心仓库副本为准；插件侧副本保留提交评审时的证据和修订过程。

状态说明：

- `Draft`：仍在插件侧收集证据，不得据此声明核心能力；
- `Proposed`：已有至少两个独立仪器族或两种 backend 行为作为证据，可提交主仓库评审；
- `Accepted`：主仓库已经冻结合同；
- `Superseded`：已由后续方案取代。

## 当前合同

scope 通用扩展合同已经由 WaveBench Core 接受。当前内容只在 Core 维护：

- [Accepted RFC](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC.md)
- [Accepted R1.3 A1](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC-R1.3-acceptance-addendum.md)
- [核心实施说明](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC_核心实施说明.md)

核心接受合同不等于具体插件已经通过 capability 实现、conformance 或实机验收。当前插件声明
仍以各包的 production descriptor 为准。

## 插件侧历史记录

- [R1.3 评审正文](../archive/rfcs/WaveBench_scope通用扩展接口RFC.md)：保留核心接受前的候选合同、证据和待决问题。
- [R1.3 Acceptance Addendum A1](../archive/rfcs/WaveBench_scope通用扩展接口RFC-R1.3-acceptance-addendum.md)：保留公共注册前的原始验收门。

新的跨仪器公共合同应在本目录收集插件证据，达到 `Proposed` 条件后提交 Core 评审。已经接受
的合同不在插件仓库继续维护并行副本。
