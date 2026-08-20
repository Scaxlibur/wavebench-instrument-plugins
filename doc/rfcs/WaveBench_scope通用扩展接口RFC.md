# WaveBench scope 通用扩展接口 RFC

> 状态：`Draft`
> 修订：`R0`
> 证据仓库：WaveBench Instrument Plugins
> 核心基线：WaveBench `0.8.22`
> 目标版本：未排期

## 摘要

现有 WaveBench Scope API 已能覆盖模拟通道波形、一次采集、截图、测量统计和部分分析
信息，但插件开发中反复出现四类无法在单一 driver 内可靠解决的问题：

1. transport 只公开 IEEE 488.2 definite block，无法表达由 VISA message END 确定边界的
   原始图片或文件；
2. screenshot 使用固定的菜单和颜色参数，没有能力 profile，部分仪器无法满足这些参数；
3. capture 能表达「采集并读取」，但没有独立 RUN、STOP、ARM SINGLE 和运行阶段接口；
4. waveform 以模拟通道整数为中心，无法统一表示 math、reference、digital 和频率轴轨迹。

这些问题并非 SDS800X HD 独有。现有 DS1000Z 与 RTM2000 插件使用 definite block 截图，
SDS800X HD 实机返回 message-bounded raw PNG；不同示波器的 trigger status、single acquisition
完成条件和 math metadata 也不一致。因此，RFC 只提出跨仪器合同，不包含厂商 SCPI 命令或
型号例外。

## 当前证据

| 功能 | 已有实现或实机行为 | 公共接口缺口 |
| --- | --- | --- |
| DS1000Z screenshot | definite block PNG | 现有 `query_bin_block()` 足够 |
| RTM2000 screenshot | definite block PNG，可控制菜单和颜色 | 现有 screenshot 参数可映射 |
| SDS800X HD screenshot | raw PNG message，无 IEEE block；菜单不可独立控制 | transport framing 和 screenshot 参数均不足 |
| Scope capture | 多个插件均实现单次采集后读取 | 没有独立采集控制与通用运行状态 |
| Acquisition status | 当前模型描述平均和分段状态 | 不能表达 Arm、Ready、Stop、Roll 等运行阶段 |
| Math/FFT | RTM2000 可提供完整元数据和 FFT 状态 | 其他仪器只提供函数、source、scale 或 display 状态 |
| Errors | 核心已有 `scope.errors` | 部分仪器手册没有错误队列，布尔开关只能 required/disabled |

测量统计已有 query-only 公共合同，SDS800X HD 已使用该合同完成实机验收。本 RFC 不重做
`ScopeMeasurementStatistics`。

## 目标

- 让 definite block 和 message-bounded binary 使用相同的 replay、session health、access
  policy 和审计合同。
- 阻止插件访问 `transport.session` 或直接调用 PyVISA、RsInstrument 等 backend。
- 让截图请求只使用仪器明确声明支持的格式、菜单和颜色选项。
- 区分采集运行阶段、触发模式、平均/分段状态和完整 capture 事务。
- 让模拟、数字、数学、参考和频域轨迹使用同一 source 与坐标轴模型。
- 保留现有 capability，通过新增 capability 和核心版本门逐步迁移。
- 每项公共合同至少由两个独立仪器族或两种不同协议行为验证。

## 非目标

- 不在 transport 中解析 PNG、波形 preamble 或厂商文件格式。
- 不开放 raw SCPI、backend session、插件回调 parser 或任意 terminator。
- 不把 `*OPC?` 定义为物理触发完成条件。
- 不在本 RFC 中设计数学表达式写入、FFT 配置或通用运算 AST。
- 不废弃现有 `scope.fetch_waveform`、`scope.capture_waveform(s)`、`scope.screenshot` 或
  `ScopeAcquisitionStatus`。
- 不为没有文档化错误队列的仪器猜测命令。
- 不因本插件仓库存在 Draft 就提高任何插件的核心版本下限。

## 安全不变量

1. binary query 默认使用 `ReplayPolicy.NO_REPLAY`，部分响应后不得重新发送完整命令。
2. message 边界必须由 backend 能力证明，不能以超时、换行或 `rstrip()` 推断成功结束。
3. message-bounded binary 必须设置正整数 `max_bytes`；超过上限按结构化 transport 失败处理。
4. transport 返回完整字节，不解释媒体内容，也不删除尾部空白。
5. 插件只能调用公共 transport 方法，不能取得 backend session。
6. 采集控制写入后必须 query-back；未知状态不得当作 Stop 或完成。
7. capture 超时必须尝试进入安全停止状态，且不能覆盖原始超时异常。
8. 频率轴不能伪装成时间轴，math/reference 不能伪装成模拟 channel。
9. 「支持时检查」必须在 artifact 中记录未支持，不能伪装成已完成错误检查。
10. 日志只记录 framing、长度、媒体类型和短状态 token，不记录 payload。

## 一、binary framing

### 建议类型

首版只接受两种可证明的响应边界：

```python
class BinaryResponseFraming(str, Enum):
    DEFINITE_BLOCK = "definite_block"
    MESSAGE = "message"
```

- `DEFINITE_BLOCK`：由 `#N<length>` 声明 payload 长度；
- `MESSAGE`：由 backend 的 message END、EOI 或等价机制确定边界。

首版不提供 `UNTIL_TIMEOUT`、任意 terminator 或插件提供的解析回调。TCPIP `SOCKET`、串口和
其他无法证明 message 边界的 backend，收到 `MESSAGE` 请求时必须在发送前拒绝。

### 建议方法

```python
def query_binary(
    self,
    command: str,
    *,
    framing: BinaryResponseFraming,
    max_bytes: int,
    replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
) -> bytes: ...
```

现有 `query_bin_block()` 保留，并作为 `DEFINITE_BLOCK` 的兼容入口。`max_bytes` 对两种 framing
均生效；兼容入口的上限来自核心配置或稳定常量，不允许无限读取。

backend 分别声明：

```text
binary.definite_block
binary.message_boundary
```

PyVISA `INSTR` resource 只有在具体资源类型能报告 message END 时，才能声明
`binary.message_boundary`。暴露 `read_raw()` 本身不能证明边界。`MESSAGE` 交换应在同一锁内
临时关闭文本 read termination，完成读取后恢复；恢复失败进入 transport/session 健康状态机。

PNG signature、chunk、IEND、尺寸和允许的尾部字节由 scope driver 校验。若完整 PNG 后存在
一个文档化终止字节，driver 只能在解析 IEND 后精确删除该字节，不得使用 `rstrip()`。

## 二、截图 profile

当前 `screenshot_png(include_menu=False, color_scheme="COL")` 假设每台仪器都能显式排除菜单。
忽略参数会让结果与请求不一致。建议新增：

```python
ScreenshotMenuMode = Literal["device", "include", "exclude"]
ScreenshotColorMode = Literal["device", "color", "monochrome", "inverted"]

@dataclass(frozen=True)
class ScopeScreenshotProfile:
    formats: tuple[str, ...]
    menu_modes: tuple[ScreenshotMenuMode, ...]
    color_modes: tuple[ScreenshotColorMode, ...]

@dataclass(frozen=True)
class ScopeScreenshotRequest:
    format: str = "png"
    menu_mode: ScreenshotMenuMode = "device"
    color_mode: ScreenshotColorMode = "device"

@dataclass(frozen=True)
class ScopeScreenshot:
    data: bytes
    media_type: str
    width_px: int | None = None
    height_px: int | None = None
```

建议新增 `scope.screenshot_profile` 和 `scope.screenshot_v2`。driver 在任何 I/O 前验证请求属于
profile。`device` 表示保留仪器当前行为，不发送对应设置；它不等于 include 或 exclude。

现有 `scope.screenshot` 保持兼容。核心只有在 profile 明确支持旧参数时才能提供适配器，不能
把 `device` 自动解释为 `exclude`。

## 三、采集运行状态与控制

现有 `ScopeAcquisitionStatus` 继续表示平均与分段采集信息。运行阶段使用独立模型：

```python
ScopeAcquisitionPhase = Literal[
    "stopped",
    "arming",
    "waiting",
    "acquiring",
    "rolling",
    "unknown",
]

ScopeTriggerMode = Literal[
    "auto",
    "normal",
    "single",
    "forced",
    "roll",
    "unknown",
]

@dataclass(frozen=True)
class ScopeAcquisitionRunState:
    phase: ScopeAcquisitionPhase
    trigger_mode: ScopeTriggerMode
    raw_state: str
    acquisition_count: int | None = None
```

`raw_state` 只允许短、可打印、无换行 token。无法无损映射时使用 `unknown` 并保留原 token，
不能把相近文字状态硬映射成完成。

建议协议：

```python
class ScopeAcquisitionRunStateDriver(InstrumentDriver, Protocol):
    def get_acquisition_run_state(self) -> ScopeAcquisitionRunState: ...

class ScopeAcquisitionControlDriver(ScopeAcquisitionRunStateDriver, Protocol):
    def start_continuous(self) -> ScopeAcquisitionRunState: ...
    def stop_acquisition(self) -> ScopeAcquisitionRunState: ...
    def arm_single(self) -> ScopeAcquisitionRunState: ...
```

对应 capability 建议为 `scope.acquisition_run_state` 和 `scope.acquisition_control`。控制能力必须
同时实现只读状态能力，且要求 `read_write` access。

`arm_single()` 只证明单次采集已发起并完成写后回读，不证明物理触发已经完成。Service 使用
acquisition deadline 轮询状态；完成条件至少为 `phase == "stopped"`。若仪器提供采集计数，
还应证明 count 相对基线变化。

现有 `capture_waveform(s)` 继续作为 vendor transaction。核心不能默认用三项控制方法重新
拼装 capture，因为 channel 配置、分块读取、恢复和多通道同次采集仍属于 driver 合同。

## 四、类型化 trace source

建议新增明确 source，避免用模拟 channel 整数承载其他轨迹：

```python
ScopeTraceKind = Literal["analog", "digital", "math", "reference"]

@dataclass(frozen=True)
class ScopeTraceRef:
    kind: ScopeTraceKind
    index: int | None = None
    name: str | None = None
```

`index` 和 `name` 必须恰有一个有效值。driver 把通用引用映射为厂商 token，厂商 token 不进入
核心模型。

```python
ScopeAxisKind = Literal["time", "frequency", "index", "unknown"]

@dataclass(frozen=True)
class ScopeAxisMetadata:
    kind: ScopeAxisKind
    unit: str
    start: float
    increment: float
    points: int

@dataclass(frozen=True)
class ScopeTraceMetadata:
    source: ScopeTraceRef
    x_axis: ScopeAxisMetadata
    y_unit: str
    y_increment: float | None = None
    y_origin: float | None = None
    y_resolution_bits: int | None = None
    operation: str | None = None
    inputs: tuple[ScopeTraceRef, ...] = ()

@dataclass(frozen=True)
class ScopeTraceData:
    metadata: ScopeTraceMetadata
    values: np.ndarray
```

首版单位使用受限 token，至少包括 `s`、`Hz`、`V`、`A`、`dB`、`dBm`、`degree`、`percent`、
`1` 和 `unknown`。`unknown` 不能与未经证明的精确换算同时出现。

建议新增 `scope.trace_metadata` 和 `scope.fetch_trace`：

```python
def get_trace_metadata(self, source: ScopeTraceRef) -> ScopeTraceMetadata: ...

def fetch_trace(
    self,
    source: ScopeTraceRef,
    points: str = "dmax",
    check_errors: bool = True,
) -> ScopeTraceData: ...
```

现有 `fetch_waveform(channel=n)` 只适配为 `ScopeTraceRef(kind="analog", index=n)`。反向适配只
允许 analog source。`scope.math_metadata`、`scope.fft_status` 和 `scope.reference_metadata`
首版不删除；至少完成两个厂商的 trace 映射后再决定兼容策略。

## 五、错误检查策略

`scope.errors` 已经是可复用接口。没有文档化错误队列的仪器不应实现空列表假接口。建议把
布尔配置扩展为：

```text
required
if_supported
disabled
```

| 策略 | 有 `scope.errors` | 无 `scope.errors` |
| --- | --- | --- |
| `required` | 执行检查 | 仪器 I/O 前拒绝 |
| `if_supported` | 执行检查 | 继续操作并记录 `skipped_unsupported` |
| `disabled` | 不检查 | 不检查 |

旧 `check_errors=true` 映射为 `required`，`false` 映射为 `disabled`。默认策略是否改为
`if_supported` 属于兼容性决定，R0 不冻结。高风险写操作仍可由 OperationSpec 强制
`required`。

## capability 与版本门

建议新增：

```text
scope.screenshot_profile
scope.screenshot_v2
scope.acquisition_run_state
scope.acquisition_control
scope.trace_metadata
scope.fetch_trace
```

兼容要求：

1. 现有 capability、方法和模型不删除、不改名；
2. 新核心 + 旧插件保持现状；
3. 使用新 transport 或 capability 的插件提高 wheel 和 descriptor 核心下限；
4. 旧核心 + 新插件在 factory 和仪器 I/O 前拒绝；
5. 新增可选 capability 本身不自动要求升级 `wavebench.instrument.v2`。

## 测试矩阵

| 层级 | 必测内容 | 默认连接仪器 |
| --- | --- | --- |
| binary model | framing、`max_bytes`、不支持能力时零发送 | 否 |
| backend | definite block、message END、termination 恢复、部分响应、超限 | 否 |
| guarded transport | access、计数、session health、结构化失败 | 否 |
| screenshot | profile 前置、PNG signature/IEND、尾部字节、无 `rstrip()` | 否 |
| acquisition | 规范状态、unknown/raw、写后回读、超时 STOP、发送次数 | 否 |
| trace | source 验证、时间/频率轴、单位、analog 兼容 | 否 |
| plugin compatibility | 新旧核心/插件四组合、descriptor 版本门 | 否 |
| opt-in hardware | 至少两种 framing、两个厂商状态机、两种 trace axis | 是 |

实机证据只保留 framing、长度、状态迁移和数值摘要。图片、原始波形、真实资源串和序列号不
进入仓库。

## 里程碑

| 里程碑 | 范围 | 退出条件 |
| --- | --- | --- |
| M1 | binary framing 与 backend capability | 两个 backend fake、超限和 termination 恢复测试通过 |
| M2 | PyVISA message boundary 与 guarded transport | definite/message 都进入 replay/session health 合同 |
| M3 | screenshot profile/v2 | definite-block 和 raw-message 两种 fixture 通过 |
| M4 | acquisition run state/control | 两个厂商映射、unknown、超时 STOP 测试通过 |
| M5 | trace source/axis | analog、math time axis、FFT frequency axis 的跨厂商 fixture 通过 |
| M6 | 版本门、文档与 opt-in 实机 | 全量离线通过；实机范围另行授权 |

M1–M6 应分别提交，不把 transport、scope 模型和插件迁移压成一个不可回滚改动。

## 已否决方案

- 插件直接访问 `transport.session`；
- 给 `query_bin_block()` 增加含义模糊的 `raw=True`；
- 使用换行或 timeout 读取 PNG；
- 在 transport 内置 PNG parser；
- 忽略 screenshot 的 menu 参数；
- 把 trigger status 填入现有 `ScopeAcquisitionStatus`；
- 用 `*OPC?` 统一判断物理触发完成；
- 把 math/reference 编成负数或大号 channel；
- 扩宽 `WaveformData.channel` 为任意字符串；
- 为没有错误队列的仪器返回空列表。

## R0 待决问题

1. 哪些 PyVISA resource class 能稳定证明 message END。
2. `query_binary()` 的兼容上限放在 connection 配置还是 operation spec。
3. screenshot v2 使用新 capability，还是扩展旧方法并提供 profile。
4. reference source 使用数字 index 还是受限字符串名称。
5. 单位使用简单枚举还是 UCUM 子集。
6. acquisition count 不可用时，哪些状态迁移足以证明新采集。
7. `if_supported` 是否允许用于 capture，还是只允许只读操作。

上述问题解决并取得跨厂商 fixture 前，RFC 保持 Draft。主仓库未接受本文时，插件不得声明
这些新 capability 已由核心提供。
