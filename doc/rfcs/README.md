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

- [WaveBench scope 通用扩展接口 RFC](WaveBench_scope通用扩展接口RFC.md)：`R1 Draft`，吸收
  核心预审意见，补充 `OperationSpec` 映射、binary 失步语义、采集状态机、trace 不变量和
  错误 artifact；仍不代表核心已实现这些接口。
