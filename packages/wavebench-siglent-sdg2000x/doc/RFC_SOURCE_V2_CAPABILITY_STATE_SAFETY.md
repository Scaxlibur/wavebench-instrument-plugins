# RFC：Source V2 能力、状态与复合输出安全模型

状态：Draft

范围：WaveBench 核心接口提案；本仓库只保存草案，不修改核心

目标版本：未定
关联实现：SDG2000X 插件、DG4000 驱动及后续第三方 Source 插件

## 摘要

现有 Source 基础接口适合身份、固定波状态和输出开关，但在谐波、调制、Sweep、Burst、Pulse、Noise、DC、ARB、Counter 与 Coupling 场景下，单纯增加更多必填字段会制造错误状态：设备不支持、当前模式不适用、未查询、查询失败和固件语义未知都会被压成同一个 `None` 或伪默认值。

本 RFC 提议增加一套可与现有接口并存的 Source V2 模型：

- 结构化描述型号、通道、读写方向和模式约束；
- 明确区分字段可用性，不用假值填补缺失状态；
- 将高级功能组织为按状态激活的 facet；
- 使用变长、稀疏的谐波分量，不固定 H2–H16；
- 在输出开启前计算包含谐波、AM、Noise、Combine、负载和偏置的保守安全预算；
- 将软件、协议、仪器回读、波形闭环和真实触发接线分层记录。

该提案不是为 SDG2000X 增加专用字段。设计至少同时覆盖：

1. 组合响应、状态依赖查询且可能没有错误队列的 Source；
2. 具有独立标量查询和错误队列的 DG4000 类 Source；
3. 只实现通用 SCPI 基础子集、完全不支持高级功能的第三方 Source。

## 背景与现有证据

### 字段缺失不是同一种状态

以下状态不能继续全部表示为 `None`：

- 当前型号明确不支持该字段；
- 功能存在，但在当前函数或模式下不适用；
- 查询计划为避免副作用而主动跳过；
- 查询失败，值本应存在但不可用；
- 固件或手册证据不足，是否支持未知。

实际例子：

- Noise 与 DC 的 `SourceStatus.amplitude` 合理地为 `None`，但当前 `SourceService.set_output` 会直接对它调用 `isfinite()`，产生 `TypeError`；
- SDG Harmonic Command 只在 SINE 下可用。非 SINE 时发送 `HARM?` 会超时，不能把所有查询都当成无条件只读；
- SDG 的 `MDWV?`、`BTWV?` 和 `FCNT?` 在关闭时只返回状态字段，无法填满当前 profile 的全部必填项；
- DG4000 类设备可通过独立查询得到更多字段，也不能反过来要求所有厂商都伪装成同一查询形态。

### 当前高级模型的不可逆映射

| 功能 | 当前模型约束 | 多厂商阻塞点 |
| --- | --- | --- |
| Harmonic | 固定 H2–H16、恰好 15 个组件；无 `enabled` | 部分设备只支持 H2–H10；部分查询只返回当前槽位；读取其它槽位需要写选择状态 |
| Modulation | 关闭时仍要求内部源频率、函数和深度/偏差 | 多数设备关闭时只返回 `STATE,OFF`，旧参数可能不可读或无意义 |
| Pulse | 必须给出 `hold=WIDTH/DUTY` | 部分设备同时返回 WIDTH 与 DUTY，但不返回哪个参数是保持量 |
| Sweep | 强制 `steps` 等完整字段 | 有的组合查询没有步数，或只在特定 spacing 下适用 |
| Burst | 关闭、Gate、Infinity 仍需统一 cycles/period/trigger 字段 | 关闭时字段缺失；Infinity 没有有限 cycles；Gate 不使用部分触发字段 |
| Counter | 固定阻抗、衰减、门时间、统计等完整配置 | 一些设备只提供频率、脉宽、占空比、参考频率和触发电平 |
| Coupling | 固定 base channel 与 deviation 模型 | 另一些设备提供 ratio、tracking direction，且不公开 base channel |

### 输出幅度不是安全预算

基础 `Vpp` 无法覆盖：

- 谐波分量叠加；
- AM 最大包络；
- Noise 的随机峰值；
- DC 的绝对电平；
- Combine 或通道跟踪后的总波形；
- 50 Ω 显示参考负载接到高阻端时可能出现的电压倍增；
- Sweep 路径上的频率相关幅度降额；
- 多通道共享功率限制。

因此 `status.amplitude <= max_source_vpp` 只能是基础检查，不能成为高级模式输出使能的充分条件。

## 目标

- 保持现有 `source.idn`、`source.status`、基础 setter 和 `source.output` 兼容。
- 允许驱动诚实表达部分支持、模式不适用和未知状态。
- 让输出安全判断基于端口总波形的保守上界。
- 让 profile 查询计划适配状态依赖与消费型查询。
- 让插件只声明实际可无损实现的读写方向。
- 让同一模型可被不同厂商、型号和固件复用。
- 将验收证据与 capability 声明绑定，但不把单台仪器证据外推到整个系列。

## 非目标

- 不统一厂商 SCPI 助记符。
- 不把所有私有功能压成最低公分母命令。
- 不允许通过发送未知命令并读取错误来自动探测能力。
- 不把示波器闭环结果当成校准证书。
- 不要求 V1 驱动一次性迁移。

## 提案

### 1. 结构化能力描述

粗粒度 capability ID 继续用于路由，细节由描述对象提供：

```python
class SupportState(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SourceOperation(str, Enum):
    READ = "read"
    WRITE = "write"
    ARM = "arm"
    FIRE = "fire"


@dataclass(frozen=True)
class SourceFeatureCapability:
    feature: str
    support: SupportState
    operations: frozenset[SourceOperation]
    channels: frozenset[int]
    modes: frozenset[str]
    constraints: Mapping[str, object]
    evidence_ref: str | None = None
```

`source.harmonics` 支持 READ 不代表支持 WRITE；`source.burst` 支持内部触发不代表外部 Gate 已接线验收。

### 2. 可用性而非裸 `Optional`

```python
class Availability(str, Enum):
    VALUE = "value"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    NOT_QUERIED = "not_queried"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Observed(Generic[T]):
    availability: Availability
    value: T | None = None
    reason_code: str | None = None
    evidence: tuple[str, ...] = ()
```

约束：

- 只有 `VALUE` 可以参与数值安全运算；
- `NOT_APPLICABLE` 不等于 0；
- `UNAVAILABLE` 参与安全预算时必须导致输出失败关闭；
- V1 适配器可将非 `VALUE` 展平为 `None`，但 V2 安全逻辑不得使用该有损视图。

### 3. Facet 状态模型

```python
@dataclass(frozen=True)
class SourceStatusV2:
    channel: int
    basic: BasicWaveFacet
    output: OutputFacet
    harmonics: Observed[HarmonicFacet]
    modulation: Observed[ModulationFacet]
    sweep: Observed[SweepFacet]
    burst: Observed[BurstFacet]
    pulse: Observed[PulseFacet]
    arbitrary: Observed[ArbitraryFacet]
    consistent: bool
    revision_token: str | None
```

状态查询使用两阶段计划：

1. 查询身份、输出、基础函数和主模式；
2. 根据锚点状态选择合法 facet 查询；
3. 查询结束时重新读取锚点；
4. 若期间状态变化，将 `consistent=False`，不得用于写事务快照。

建议声明查询激活规则：

```python
@dataclass(frozen=True)
class FacetQuerySpec:
    facet: str
    activation: tuple[ActivationRule, ...]
    query_when_inactive: bool
    consumes_error_state: bool
    side_effect_free: bool
```

Harmonic 仅在 SINE 下查询是该机制的一个实例，而不是写进核心的 SIGLENT 特例。

### 4. 变长谐波模型

```python
class ComponentAmplitudeKind(str, Enum):
    ABSOLUTE_VPP = "absolute_vpp"
    RELATIVE_LINEAR = "relative_linear"
    RELATIVE_DB = "relative_db"


@dataclass(frozen=True)
class HarmonicComponent:
    order: int
    enabled: Observed[bool]
    amplitude: Observed[ComponentAmplitude]
    phase_deg: Observed[float]


@dataclass(frozen=True)
class HarmonicFacet:
    enabled: bool
    selection: str
    components: tuple[HarmonicComponent, ...]
    maximum_supported_order: int | None
    completeness: str  # complete / active_only / selected_only / partial
    amplitude_semantics: str
```

要求：

- 组件按 `order` 唯一，可稀疏；
- 不要求所有设备支持相同最高阶次；
- 必须显式标记查询完整性；
- 当前只返回选中槽位的设备不得伪造其它阶次为 0；
- 写请求必须声明 `patch` 或 `replace_all`；
- 任一已启用但幅度未知的分量都会使安全预算为 UNKNOWN。

### 5. 请求使用补丁语义

`None` 不能同时表示「保持不变」「清除」和「不适用」。建议：

```python
class PatchAction(str, Enum):
    KEEP = "keep"
    SET = "set"
    RESET_DEFAULT = "reset_default"


@dataclass(frozen=True)
class PatchValue(Generic[T]):
    action: PatchAction
    value: T | None = None
```

驱动必须在 I/O 前拒绝当前模式不适用的 `SET`，不能静默忽略。

### 6. 复合输出安全预算

```python
class BudgetConfidence(str, Enum):
    PROVEN_CONSERVATIVE = "proven_conservative"
    DEVICE_DECLARED = "device_declared"
    MEASURED_ONLY = "measured_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompositeOutputBudget:
    dc_offset_v: float
    ac_peak_upper_v: float
    minimum_v_lower: float
    maximum_v_upper: float
    vpp_upper_v: float
    rms_upper_v: float | None
    display_load_ohm: float | None
    actual_termination_ohm: Observed[float]
    confidence: BudgetConfidence
    contributors: tuple[SafetyContributor, ...]
```

独立正弦分量的保守上界：

```text
A_ac,max <= sum(abs(A_k))
V_min >= offset - A_ac,max
V_max <= offset + A_ac,max
Vpp_max <= 2 * A_ac,max
```

AM 还需乘最大包络因子；Combine 按通道分量保守求和；Sweep 取完整路径最大值；Noise 没有确定峰值上界时不得声称 `PROVEN_CONSERVATIVE`。

输出使能至少检查：

- `vpp_upper_v <= configured max_source_vpp`；
- 最小/最大绝对电压；
- 负载参考与实际端接一致性；
- 频率相关幅度降额；
- 多通道共享功率限制；
- 所有参与预算的 facet 为可信 `VALUE`。

### 7. 统一写事务

V2 写事务应统一遵循：

1. 读取一致、可恢复的完整前状态；
2. 在任何 I/O 前验证类型、范围、能力与安全预算；
3. 每个目标字段只写一次；未知结果不得重试；
4. 独立回读目标字段和未修改闭包；
5. 写后异常立即请求 OFF；
6. 独立确认 OFF，失败则标记 `state_uncertain=True`；
7. 歧义或恢复失败锁止会话后续 mutation；
8. 只有重新建立并验证会话后才能解除锁止。

错误队列是可选证据。支持错误队列的驱动可附加 drain/assert；没有已认证错误队列的驱动仍可依靠单写、回读、OFF 与锁止形成安全事务。

### 8. 实机验收层级

| 层级 | 证据 | 可证明事项 |
| --- | --- | --- |
| A0 | 离线 fixture 与故障注入 | 命令格式、解析与失败关闭分支 |
| A1 | 实机只读 | 查询合法性、响应形态、型号/固件 |
| A2 | 安全输出开关 | ON/OFF 回读与恢复 |
| A3 | 示波器通道环回 | 基础频率、Vpp、偏置、函数、占空比 |
| A4 | 高级波形 | 谐波频谱、调制包络、Sweep 路径、Burst 周期数 |
| A5 | 真实触发/同步接线 | 外部触发、Gate、Sync、通道间时序 |

每项证据还应记录型号、固件、端口映射、终端阻抗、安全预算、设置值、测量值、容差、最终 OFF 与未覆盖项。

## 多厂商映射示例

| 维度 | 组合响应 Source | DG4000 类 Source | 通用 SCPI 基础 Source |
| --- | --- | --- | --- |
| 基础状态 | 单次查询返回多字段 | 多个独立标量查询 | 只实现函数/频率/幅度/输出 |
| 高级查询 | 按主模式激活，关闭时可能只返回 STATE | 通常可分别读取更多字段 | 明确 UNSUPPORTED，不发送探测命令 |
| 错误检查 | 可能没有已认证错误队列 | 可使用错误队列增强事务 | 由能力描述决定，不作默认假设 |
| Harmonic | 可能只返回当前槽位 | 若可逐阶只读，则返回 COMPLETE | 不支持时为 UNSUPPORTED |
| 负载 | 组合在输出查询中 | 独立 LOAD 查询 | 未知实际端接时预算为 UNKNOWN |
| 写事务 | 单写、组合回读、OFF、锁止 | 单写、标量回读、错误检查、恢复 | 只开放有完整证据的基础子集 |

核心只消费统一语义，不接收厂商助记符、私有槽位或特定响应格式。

## 兼容与迁移

1. V1 接口保持不变。
2. 新 capability 使用 V2 ID 或 descriptor schema 版本显式选择。
3. V1 驱动可通过适配器生成最小 V2 basic/output facet。
4. V2 → V1 展平允许丢失可用性信息，但不得用于高级输出安全判断。
5. 新高级 capability 优先使用 V2；旧模型进入维护模式，不继续增加厂商特例字段。
6. 驱动只有在无损映射时才声明旧高级 capability。

## 被拒绝的替代方案

### 固定增加更多 `Optional` 字段

无法区分不支持、不适用、未查询和失败，安全逻辑仍会误判。

### 为每个厂商增加核心专用字段

会把核心变成厂商协议集合，无法被后续驱动复用。

### 用 0 或默认值补齐 profile

会制造虚假的谐波分量、Burst 周期或调制参数，直接污染安全预算。

### 让 profile 查询临时写选择状态

破坏 query-only 语义，也会在只读会话中失败。若设备只能通过写选择状态读取完整 profile，应明确提供受控 snapshot transaction，而不是伪装成普通查询。

## 分阶段实现建议

1. 增加 `Observed`、facet 与 capability descriptor，不改变 V1。
2. 修正基础安全服务对 `None`/非 `VALUE` 的处理，返回类型化 `ConfigError`。
3. 增加状态依赖查询计划和一致性复核。
4. 增加复合输出安全预算与负载证据。
5. 迁移 Harmonic、Modulation、Pulse、Sweep、Burst。
6. 迁移 Counter、Coupling、ARB 和多通道预算。
7. 增加验收证据 schema 与报告聚合。

## 接受标准

- 至少两个现有不同协议形态的 Source 驱动完成试迁移。
- 不支持高级功能的第三方基础驱动无需实现假字段。
- Harmonic 可表达不同最大阶次、稀疏组件、selected-only 与 enabled。
- Noise/DC/关闭状态不会触发裸 `TypeError`。
- 任一安全相关字段 UNKNOWN/UNAVAILABLE 时输出失败关闭。
- 50 Ω 显示参考接高阻端的倍增风险可被模型表达并阻止错误放行。
- 外部触发未接线时，报告不能显示 A5 已通过。
- V1 基础命令与现有配置继续工作。

## 开放问题

- `Observed` 是否进入所有仪器模型，还是先限制在 Source V2。
- revision token 由驱动生成，还是由核心基于 canonical snapshot 计算。
- query-only 但会消费错误队列的操作如何在访问策略中单独标记。
- Noise 的统计安全预算应采用 crest-factor 配置、测量窗口证据，还是始终要求人工风险确认。
- 多通道共享功率限制应由驱动提供函数，还是由 descriptor 约束表达式描述。
