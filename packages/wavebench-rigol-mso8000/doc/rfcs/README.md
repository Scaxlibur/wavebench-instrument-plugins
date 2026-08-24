# MSO8104 相关 WaveBench RFC

本目录记录 MSO8104 插件无法通过 WaveBench 公开接口安全表达的合同缺口。RFC 是核心修改建议，不表示对应接口已经存在，也不允许插件提前声明依赖该接口的 capability。

| RFC | 状态 | 影响 |
| --- | --- | --- |
| [RFC-0001：非重放文本查询](0001-nonreplayable-text-query.md) | 提议 | `scope.errors` 暂不声明 |
| [RFC-0002：示波器通道输入状态](0002-scope-channel-input-state.md) | 提议 | 当前使用兼容归一化，独立阻抗语义尚未进入核心 |
| [RFC-0003：示波器截图 framing 与菜单合同](0003-scope-screenshot-framing-and-menu-contract.md) | 提议 | `scope.screenshot` 暂不声明 |
| [RFC-0004：可移植的示波器数字通道状态模型](0004-portable-scope-digital-status.md) | 提议 | `scope.digital_status` 暂不声明 |
| [RFC-0005：可组合的示波器状态快照](0005-portable-scope-snapshot.md) | 提议 | `scope.snapshot` 暂不声明，继续使用 partial summary |
| [RFC-0006：可移植的示波器采集状态与平均采集合同](0006-portable-scope-acquisition-contracts.md) | 提议 | `scope.acquisition_status` 与 `scope.capture_average` 暂不声明 |
| [RFC-0007：可移植的示波器统计、FFT 与光标读取合同](0007-portable-scope-analysis-reads.md) | 提议 | 统计与 FFT 暂不声明；cursor 仅开放无损子集 |
| [RFC-0008：有界示波器波形块的尾随字节合同](0008-bounded-waveform-block-trailing-contract.md) | 提议 | waveform/capture 暂不声明，等待可声明的 binary trailing 与大小合同 |

RFC 被核心实现并发布后，插件必须提高最低 WaveBench 版本、补充核心集成测试，再启用相应 capability。不能只根据 RFC 文本调用不存在的方法。
