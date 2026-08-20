# 接口 RFC

本目录保存从仪器插件实现和实机验收中形成的 WaveBench 公共接口提案。RFC 只描述跨仪器
问题、兼容边界和建议合同，不代表主仓库已经接受或实现对应接口。核心预审意见只会形成
插件侧修订，不会自动修改主仓库。

状态说明：

- `Draft`：仍在插件侧收集证据，不得据此声明核心能力；
- `Proposed`：已有至少两个独立仪器族或两种 backend 行为作为证据，可提交主仓库评审；
- `Accepted`：主仓库已经冻结合同；
- `Superseded`：已由后续方案取代。

## 当前 RFC

- [WaveBench scope 通用扩展接口 RFC](WaveBench_scope通用扩展接口RFC.md)：`R1.3 Draft`，核心复审增补已添加
  snapshot/restore/verify、非嵌套 phase authorization、回绕拒绝和旧 `scope.errors` 隔离；仍不代表
  核心已实现这些接口，四项合同仍待核心团队复审。

## 后续文档拆分

总 RFC 暂作单一规范事实源，避免把同一合同复制到多份文件后变得不一致。核心同意分拆后，按以下依赖拆出四份子 RFC：

1. `binary-screenshot`：依赖 OperationSpec、phase authorization 和 artifact；包含 binary framing、budget、screenshot profile、恢复。
2. `acquisition`：依赖 OperationSpec 和共享恢复接口；包含 control profile、SINGLE、continuous、recovery。
3. `trace`：依赖 binary transfer 字段闭包和 source/axis 模型；包含 analog、digital、reference、spectrum。
4. `error-policy`：依赖非嵌套 phase authorization 和 artifact；包含 `scope.error_drain_v1` 与旧 `scope.errors` 迁移。

在子 RFC 实际拆出前，不创建并行版本的规范文本；这不改变当前 Draft 状态或任何插件能力。
