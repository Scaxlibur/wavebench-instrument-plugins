# RFC-0007：可移植的示波器统计、FFT 与光标读取合同

状态：core R1 已实现（未发布）；MSO8104 受控开发采用 statistics/FFT/cursor V2 子集

目标仓库：WaveBench core

## 问题

WaveBench 已有 `scope.measurement_statistics`、`scope.fft_status` 与 `scope.cursor_readout`，但三项公共模型都固定了 R&S RTM2000 风格的寻址或返回字段。RIGOL MSO8000 的只读命令面不同，无法在不丢失语义或制造默认值的情况下完整映射。

### 测量统计

当前方法按整数 `slot` 寻址，并要求调用方确认该 slot 已配置：

```python
get_measurement_statistics(
    slot,
    *,
    configured_slot,
    include_buffer=False,
    acquisition_stopped=False,
)
```

MSO8000 的统计 query 按 `<type>,<item>,<source...>` 寻址。设备界面虽然保留最后打开的十个测量项，却没有 query 可以把 `ITEM1`～`ITEM10` 解析回测量 item 与 source。插件因此不能把公共 `slot=1` 无歧义转换成 `VPP,CHAN1` 等命令。

MSO8000 可以分别查询 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT，但手册没有统计样本 buffer 查询。`include_buffer=True` 也不能通过重复查询当前值来模拟。

### FFT 状态

当前 `ScopeFftStatus` 把以下字段全部定义为必填：

```text
math_index, average_complete, resolution_bandwidth_hz, sample_rate_hz
```

MSO8000 可以查询 Math operator、FFT source、window、vertical unit/scale/offset、frequency range/center/start/end 和 peak search。手册没有 FFT average-complete 或 resolution-bandwidth query；全局 acquisition sample rate 也不等于手册明确声明的 FFT sample rate。核心模型反而没有字段承载设备实际报告的 source、window、unit 与频率范围。

### 光标读取

当前 `ScopeCursorReadout` 只有一个 `source` 和一个 `function`，并把水平差固定为秒/赫兹字段：

```text
x_delta_s, inverse_x_delta_hz, y_delta, inverse_y_delta,
x_ratio, y_ratio
```

MSO8000 使用一套全局 cursor 状态，支持 MANual、TRACk、XY 与 MEASure 模式。手动和追踪模式分别拥有 A/B 两个 source；水平单位可为秒、赫兹、角度或百分比，垂直单位可为 source unit 或百分比。单 `source` 无法表达双源，`x_delta_s` 也不能装入 Hz、degree 或 percent 而仍保持类型真实。

当前插件因此只公开可无损映射的窄子集：公共 index 固定为 1，模式必须是 MANual，A/B 必须同源，类型与单位必须是 `TIME + SEC` 或 `AMPL + SOUR`。其他配置在读取结果前拒绝。

## 建议接口

### 用 selector 取代固定统计 slot

```python
@dataclass(frozen=True)
class ScopeMeasurementSelector:
    slot: int | None = None
    item: str | None = None
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopeMeasurementStatisticsRequestV2:
    selector: ScopeMeasurementSelector
    configured: bool
    include_buffer: bool = False
    acquisition_stopped: bool = False
```

selector 必须采用且只采用一种寻址方式。RTM driver 可使用 `slot`，MSO driver 可使用 `item + sources`。若设备没有 buffer query，`include_buffer=True` 应在 I/O 前明确报告 unsupported，而不是返回空 tuple 或重复当前值。

结果应回显规范化 selector，避免只有 `category` 而丢失 source。现有 actual/average/deviation/minimum/maximum/count 字段可以继续使用。

### 允许 FFT 状态报告设备实际具备的字段

```python
@dataclass(frozen=True)
class ScopeFftStatusV2:
    math_index: int
    source: str | None = None
    window: str | None = None
    vertical_unit: str | None = None
    frequency_start_hz: float | None = None
    frequency_stop_hz: float | None = None
    average_complete: bool | None = None
    resolution_bandwidth_hz: float | None = None
    sample_rate_hz: float | None = None
```

`None` 表示设备没有对应 query，不允许从频率跨度、点数或全局采样率猜测 RBW 与 FFT sample rate。已有 `scope.math_metadata` 可以继续提供实际 waveform preamble；FFT status 不必重复读取数据。

### 为光标值携带 source 与 unit

```python
@dataclass(frozen=True)
class ScopeCursorQuantity:
    value: float | None
    unit: str


@dataclass(frozen=True)
class ScopeCursorReadoutV2:
    cursor_index: int | None
    mode: str
    function: str
    source_a: str | None
    source_b: str | None
    x_a: ScopeCursorQuantity | None = None
    x_b: ScopeCursorQuantity | None = None
    x_delta: ScopeCursorQuantity | None = None
    inverse_x_delta: ScopeCursorQuantity | None = None
    y_a: ScopeCursorQuantity | None = None
    y_b: ScopeCursorQuantity | None = None
    y_delta: ScopeCursorQuantity | None = None
```

具体 unit 枚举和迁移方式由 core 决定，但秒、赫兹、角度、百分比与 source-defined unit 必须可区分。A/B source 不应拼接成一个字符串，也不能在不相等时只保留其中一个。

## capability 影响

core 当前开发分支已实现 selector、statistics、FFT 与 cursor 的 V2 合同。MSO8104 在受控开发中声明 `scope.measurement_statistics_v2`：只接受 `item_sources`、不支持统计 buffer，并以 6 条纯读取查询返回完整聚合值；legacy `scope.measurement_statistics` 仍不声明。`scope.fft_status_v2` 先确认 math operator 为 `FFT`，再读取 source、window、vertical unit 与起止频率；average-complete、RBW 和 FFT sample rate 保持 unavailable。受控实机的前面板 MATH1 返回 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`；FFT 准确度仍待单独验证。

当前 `scope.cursor_readout` 只声明上述无损子集。V2 发布后可以扩展到双源、追踪与多单位模式；XY 和 measurement cursor 仍须逐项取得返回语义证据后再开放。

`scope.reference_metadata` 与 `scope.history_timestamps` 不属于本 RFC 的核心缺口。MSO8000 手册没有 reference waveform 的轴/点数查询，也没有逐帧 relative/calendar timestamp；这两项是厂商证据缺口，当前直接不声明 capability。

## 替代方案

- 把 MSO 的 `ITEM1` 当作可查询的统计 slot：手册只允许清除该位置，不能反查 item/source。
- 用全局 sample rate 和频率跨度计算 FFT RBW：手册没有给出该等式的合同。
- 把 cursor A/B source 拼成一个 `source` 字符串：破坏公共字段语义和下游解析。
- 把 Hz、degree 或 percent 数值放进 `x_delta_s`：单位错误比缺字段更危险。
- 重复查询 CURRENT 构造统计 buffer：不是设备维护的历史样本序列。
