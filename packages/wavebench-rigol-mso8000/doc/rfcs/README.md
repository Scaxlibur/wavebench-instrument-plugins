# MSO8104 相关 WaveBench RFC

本目录记录 MSO8104 插件无法通过 WaveBench 公开接口安全表达的合同缺口。RFC 是核心修改建议，不表示对应接口已经存在，也不允许插件提前声明依赖该接口的 capability。

| RFC | 状态 | 影响 |
| --- | --- | --- |
| [RFC-0001：非重放文本查询](0001-nonreplayable-text-query.md) | 提议 | `scope.errors` 暂不声明 |
| [RFC-0002：示波器通道输入状态](0002-scope-channel-input-state.md) | 提议 | 当前使用兼容归一化，独立阻抗语义尚未进入核心 |
| [RFC-0003：示波器截图 framing 与菜单合同](0003-scope-screenshot-framing-and-menu-contract.md) | 提议 | `scope.screenshot` 暂不声明 |

RFC 被核心实现并发布后，插件必须提高最低 WaveBench 版本、补充核心集成测试，再启用相应 capability。不能只根据 RFC 文本调用不存在的方法。
