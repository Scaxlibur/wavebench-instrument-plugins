# RFC-0002：示波器通道输入状态

状态：提议

目标仓库：WaveBench core

## 问题

当前 `scope.channel_coupling` 与 `channel_coupling(channel)` 同时承担显示耦合方式和高阻安全证明。该模型适合把 termination 编码在 coupling token 中的仪器，但 MSO8104 使用两条独立命令：

```text
:CHANnel<n>:COUPling?   # AC / DC / GND
:CHANnel<n>:IMPedance?  # OMEG / FIFT
```

只读取 coupling 无法区分 1 MΩ 与 50 Ω。插件可以把组合状态归一化为核心现有的 `ACL/DCL/AC/DC` token，但返回值不再是仪器原始 coupling，调用方也无法分别展示两项状态。

## 建议模型

```python
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ScopeChannelInputState:
    channel: int
    coupling: Literal["AC", "DC", "GND", "UNKNOWN"]
    termination: Literal["high_z", "50_ohm", "unknown"]
    impedance_ohm: float | None = None


class ScopeChannelInputStateDriver(Protocol):
    def get_channel_input_state(self, channel: int) -> ScopeChannelInputState: ...
```

建议 capability：

```text
scope.channel_input_state -> get_channel_input_state
```

## Service 规则

- `fixed-high-impedance` descriptor 可继续使用现有策略。
- `switchable-termination` 优先要求 `scope.channel_input_state`。
- 只有 `termination == "high_z"` 默认通过高阻保护。
- `50_ohm` 与 `unknown` 默认拒绝；现有显式 `allow_50ohm` 只放行前者，不放行 unknown。
- `GND` 与 termination 分开处理，不能靠字符串猜测。
- 旧 `scope.channel_coupling` 保留兼容，但不再作为 switchable termination 的完整证明。

## 插件过渡方案

核心发布新 capability 前，MSO8104 插件在 `channel_coupling()` 内联合查询两项状态，并按核心现有约定返回：

| coupling | impedance | 兼容 token |
| --- | --- | --- |
| AC | OMEG | ACL |
| DC | OMEG | DCL |
| AC | FIFT | AC |
| DC | FIFT | DC |

`GND`、未知 token 和不完整响应一律 fail closed。该兼容层必须在 README 和测试中明确，不得描述为原始 coupling 回包。
