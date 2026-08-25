# MSO8104 相关 WaveBench RFC

本目录记录 MSO8104 插件曾无法通过 WaveBench 公开接口安全表达的合同缺口。部分 RFC 已在 core 开发分支实现 R1；这些接口可用于受控开发和验收，但在 core 正式发布前不构成兼容性 wheel 发布依据。

| RFC | 状态 | 影响 |
| --- | --- | --- |
| [RFC-0001：非重放文本查询](0001-nonreplayable-text-query.md) | 提议 | `scope.errors` 暂不声明 |
| [RFC-0002：示波器通道输入状态](0002-scope-channel-input-state.md) | core R1 已实现（未发布） | 插件受控声明 `scope.channel_input_state_v2` |
| [RFC-0003：示波器截图 framing 与菜单合同](0003-scope-screenshot-framing-and-menu-contract.md) | 提议 | `scope.screenshot` 暂不声明 |
| [RFC-0004：可移植的示波器数字通道状态模型](0004-portable-scope-digital-status.md) | core R1 已实现（未发布） | 缺 LA 设备证据，`scope.digital_status_v2` 暂不声明 |
| [RFC-0005：可组合的示波器状态快照](0005-portable-scope-snapshot.md) | core R1 已实现（未发布） | 设备字段和实机证据不足，`scope.snapshot_v2` 暂不声明 |
| [RFC-0006：可移植的示波器采集状态与平均采集合同](0006-portable-scope-acquisition-contracts.md) | core R1 已实现（未发布） | 受控声明 acquisition status V2 静态子集；average/capture 暂不声明 |
| [RFC-0007：可移植的示波器统计、FFT 与光标读取合同](0007-portable-scope-analysis-reads.md) | core R1 已实现（未发布） | 受控声明 statistics/FFT/cursor V2；FFT MATH1 状态回包已验证 |
| [RFC-0008：有界示波器波形块的尾随字节合同](0008-bounded-waveform-block-trailing-contract.md) | core R1 已实现（未发布） | 受控声明有界 `DEF`；capture 暂不声明 |

core 正式发布后，插件必须提高最低 WaveBench 版本并重新完成核心集成测试，才可发布相应 compatibility wheel。不能只根据 RFC 文本调用不存在的方法。
