# 接口 RFC

本目录保存从仪器插件实现和实机验收中形成的 WaveBench 公共接口提案。RFC 只描述跨仪器
问题、兼容边界和建议合同，不代表主仓库已经接受或实现对应接口。

状态说明：

- `Draft`：仍在插件侧收集证据，不得据此声明核心能力；
- `Proposed`：已有至少两个独立仪器族或两种 backend 行为作为证据，可提交主仓库评审；
- `Accepted`：主仓库已经冻结合同；
- `Superseded`：已由后续方案取代。

## 当前 RFC

- [WaveBench scope 通用扩展接口 RFC](WaveBench_scope通用扩展接口RFC.md)：提议有界 binary
  framing、截图 profile、独立采集运行控制、类型化 trace source 和三态错误检查策略。
