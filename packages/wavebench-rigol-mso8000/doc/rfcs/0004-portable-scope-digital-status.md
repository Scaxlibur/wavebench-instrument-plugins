# RFC-0004：可移植的示波器数字通道状态模型

状态：提议

目标仓库：WaveBench core

## 问题

WaveBench `ScopeDigitalChannelStatus` 把以下字段全部定义为必填：

```text
channel, group_start_channel, group_stop_channel, displayed,
activity, technology, threshold_v, threshold_coupled,
hysteresis, deskew_s, size, position_div, label, label_enabled
```

该模型能完整表达 R&S RTM2000 的数字通道查询面，却不能移植到 RIGOL MSO8000。MSO8000 手册可以证明以下只读状态：

- `:SYSTem:MODules?` 报告 LA 硬件模块是否存在；
- `:LA:DIGital:DISPlay? D<n>` 报告逐通道显示状态；
- `:LA:POD<n>:THReshold?` 报告 D0～D7 或 D8～D15 共用的阈值；
- `:LA:SIZE?` 报告全局数字波形显示大小；
- `:LA:DIGital:POSition? D<n>` 与 `:LA:DIGital:LABel? D<n>` 报告位置和标签；
- `:LA:TCALibrate?` 报告数字通道的全局延时校正。

手册没有 activity、technology、hysteresis 或标签显示使能的查询。固定的 POD 共享阈值也不能无歧义映射为 RTM 风格的 `threshold_coupled` 状态。把缺失字段填成 `LOW`、`MANUAL`、`NORMAL`、`False` 或其他默认值，会制造仪器从未报告过的状态。

## 建议接口

为跨厂商数字通道状态增加能够区分「已查询值」与「设备不支持」的模型。可新增 V2 模型，保留最小公共字段，并把厂商可选状态设为可空：

```python
@dataclass(frozen=True)
class ScopeDigitalChannelStatusV2:
    channel: int
    displayed: bool
    group_start_channel: int | None = None
    group_stop_channel: int | None = None
    activity: ScopeDigitalActivity | None = None
    technology: ScopeDigitalTechnology | None = None
    threshold_v: float | None = None
    threshold_coupled: bool | None = None
    hysteresis: ScopeDigitalHysteresis | None = None
    deskew_s: float | None = None
    size: ScopeDigitalSize | None = None
    position_div: float | None = None
    label: str | None = None
    label_enabled: bool | None = None
```

具体类型名和迁移方案由 core 决定。无论采用新模型、可选字段还是分层子模型，都应满足：

- `None` 表示设备没有可证明的查询合同，不等于默认值；
- POD 共享阈值可以明确报告分组范围，不伪装成独立逐通道阈值；
- 全局 deskew、size 与逐通道状态可以区分作用域；
- CLI 和序列化输出保留未知值，不擅自归一化成具体枚举。

## capability 影响

核心提供可移植模型前，MSO8104 descriptor 不声明 `scope.digital_status`。插件不通过额外波形采集推断 activity，也不从数值阈值反推 TTL、ECL 或 CMOS technology。

`scope.digital_waveform` 是另一个独立问题。现有 `ScopeDigitalWaveform` 的 `uint16` bitset 合同足够表达结果，但 MSO8000 手册没有定义 D0～D15 作为 waveform source 时 BYTE/WORD payload 到 LOW/HIGH 的确切编码，WORD 字节序也不明确。因此该 capability 同样暂不声明，但不需要用本 RFC 修改核心模型。

## 替代方案

- 用固定默认值补齐必填字段：返回内容不是设备状态。
- 从 POD 阈值猜测 technology：同一阈值可能来自手动设置，无法证明协议类型。
- 读取一段数字波形推断 activity：会引入 waveform 状态事务和采集前提，仍不能补齐其他字段。
- 只在插件中定义私有状态类型：绕过 WaveBench capability、Service 与 CLI 的类型合同。
