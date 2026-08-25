# RFC-0004：可移植的示波器数字通道状态模型

状态：core R1 已实现（未发布）

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
- `:LA:DIGital:LABel? D<n>` 报告标签；
- `:LA:TCALibrate?` 报告数字通道的全局延时校正。

手册的 `:LA:DIGital:POSition` 查询格式参数与示例互相矛盾，且返回值是离散显示槽位而非以 div 为单位的可证明位置，因此不进入本轮 V2 子集。手册没有 activity、technology、hysteresis 或标签显示使能的查询。固定的 POD 共享阈值也不能无歧义映射为 RTM 风格的 `threshold_coupled` 状态。把缺失字段填成 `LOW`、`MANUAL`、`NORMAL`、`False` 或其他默认值，会制造仪器从未报告过的状态。

## core R1 接口

core 已采用按作用域分层的 V2 模型，能够区分「已查询值」与「设备不支持」：

```python
@dataclass(frozen=True, slots=True)
class ScopeDigitalPodStatusV2:
    start_channel: int
    stop_channel: int
    threshold_v: float | None = None
    threshold_scope: Literal["channel", "pod", "unknown"] | None = None

@dataclass(frozen=True, slots=True)
class ScopeDigitalSharedStatusV2:
    module_present: bool | None = None
    timing_calibration_s: float | None = None
    size: ScopeDigitalSizeV2 | None = None

@dataclass(frozen=True, slots=True)
class ScopeDigitalChannelStatusV2:
    channel: int
    displayed: bool | None = None
    position_div: float | None = None
    label: str | None = None
    label_enabled: bool | None = None
    activity: ScopeDigitalActivityV2 | None = None
    technology: ScopeDigitalTechnologyV2 | None = None
    hysteresis: ScopeDigitalHysteresisV2 | None = None
    pod: ScopeDigitalPodStatusV2 | None = None
    shared: ScopeDigitalSharedStatusV2 | None = None
    unavailable_fields: tuple[ScopeDigitalStatusFieldV2, ...] = ()
```

R1 以 `ScopeDigitalStatusDriverV2.get_digital_status_v2(channel)` 和 `scope.digital_status_v2` 公开该模型；该 capability 不需要 descriptor profile，但使用 `stateful_read / exclusive` 操作合同。它不触发 acquisition，也不读取 waveform 推断 activity。实现必须满足：

- `None` 表示设备没有可证明的查询合同，不等于默认值；
- POD 共享阈值可以明确报告分组范围，不伪装成独立逐通道阈值；
- 全局 timing calibration、size 与逐通道状态保持独立作用域；
- `unavailable_fields` 以稳定顺序精确解释每个 `None`；设备已查询但无法映射的枚举才使用 `unknown`；
- CLI 和序列化输出保留未知值，不擅自归一化成具体枚举。

## capability 影响

MSO8104 descriptor 继续不声明 legacy `scope.digital_status`，但在 core R1 下受控声明 `scope.digital_status_v2`。driver 只接受 D0～D15；每次先查询 `:SYSTem:MODules?`。LA 缺席时只返回 `shared.module_present=false`，不发送 `:LA:*?`。LA 存在时，driver 只读取逐通道 display/label、所属 POD 的共享阈值、全局 timing calibration 与 display size；D0～D7 映射 POD1，D8～D15 映射 POD2。`position_div`、label-enabled、activity、technology 与 hysteresis 保持 unavailable。插件不通过额外波形采集推断 activity，也不从数值阈值反推 TTL、ECL 或 CMOS technology。

在记录的 MSO8104 固件、LAN/PyVISA 与只读步骤中，D0、D8 已验证模块存在、逐通道 display/label、POD 范围与 `1.4 V` 阈值，以及共享 `0 s` timing calibration 和 `MEDIUM` size。该证据不外推为数字探头、电气阈值、逻辑活动、位置或数字编码准确度。

`scope.digital_waveform` 是另一个独立问题。现有 `ScopeDigitalWaveform` 的 `uint16` bitset 合同足够表达结果，但 MSO8000 手册没有定义 D0～D15 作为 waveform source 时 BYTE/WORD payload 到 LOW/HIGH 的确切编码，WORD 字节序也不明确。因此该 capability 同样暂不声明，但不需要用本 RFC 修改核心模型。

## 替代方案

- 用固定默认值补齐必填字段：返回内容不是设备状态。
- 从 POD 阈值猜测 technology：同一阈值可能来自手动设置，无法证明协议类型。
- 读取一段数字波形推断 activity：会引入 waveform 状态事务和采集前提，仍不能补齐其他字段。
- 只在插件中定义私有状态类型：绕过 WaveBench capability、Service 与 CLI 的类型合同。
