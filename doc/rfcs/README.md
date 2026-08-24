# 接口 RFC

本目录保存从仪器插件实现和实机验收中形成的 WaveBench 公共接口提案及其评审历史。已经由
核心接受的合同以核心仓库副本为准；插件侧副本保留提交评审时的证据和修订过程。

状态说明：

- `Draft`：仍在插件侧收集证据，不得据此声明核心能力；
- `Proposed`：已有至少两个独立仪器族或两种 backend 行为作为证据，可提交主仓库评审；
- `Accepted`：主仓库已经冻结合同；
- `Superseded`：已由后续方案取代。

## 当前 RFC

- [WaveBench scope 通用扩展接口 RFC](WaveBench_scope通用扩展接口RFC.md)：插件侧
  `R1.3` 评审存档。核心 `0.8.23` 已接受并实现公共合同；当前规范以
  [核心 RFC](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC.md)
  和[核心实施说明](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC_核心实施说明.md)
  为准。
- [R1.3 Acceptance Addendum A1](WaveBench_scope通用扩展接口RFC-R1.3-acceptance-addendum.md)：
  插件侧验收门存档。核心离线 A1 已通过；每个插件仍需按 capability 单独完成实现、conformance
  和实机验收。

## 后续文档拆分

总 RFC 暂作单一规范事实源，避免把同一合同复制到多份文件后变得不一致。核心同意分拆后，按以下依赖拆出四份子 RFC：

1. `binary-screenshot`：依赖 OperationSpec、phase authorization 和 artifact；包含 binary framing、budget、screenshot profile、恢复。
2. `acquisition`：依赖 OperationSpec 和共享恢复接口；包含 control profile、SINGLE、continuous、recovery。
3. `trace`：依赖 binary transfer 字段闭包和 source/axis 模型；包含 analog、digital、reference、spectrum。
4. `error-policy`：依赖非嵌套 phase authorization 和 artifact；包含 `scope.error_drain_v1` 与旧 `scope.errors` 迁移。

Acceptance Addendum A1 是核心采用的验收索引，不构成并行版本。核心合同完成不改变现有插件
descriptor；只有完成插件自身验收后，才能声明对应 capability。
