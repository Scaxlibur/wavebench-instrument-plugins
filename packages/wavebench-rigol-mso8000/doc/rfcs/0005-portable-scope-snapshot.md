# RFC-0005：可组合的示波器状态快照

状态：提议

目标仓库：WaveBench core

## 问题

当前 `scope.snapshot` 必须一次返回完整 `ScopeSnapshot`。以下七个分区及其非空字段全部属于强制合同：

```text
identity, health, channel, timebase, probe, waveform, trigger
```

该模型能表达 R&S RTM2000 的查询面，但不能移植到 RIGOL MSO8000。MSO8000 可以查询身份、模拟通道显示与垂直设置、采样率、主时基、部分探头设置、波形 preamble 和触发设置，却不能证明下列必填字段：

- operation/questionable condition；
- acquisition available/count；
- 通道 overload；
- 探头名称、类型、电容和实际输入阻抗；
- 部分 trigger hysteresis/holdoff 语义。

手册中的 `*STB?` 也不是普通幂等状态读取：执行后寄存器值清零。现有 replayable `query()` 不能安全读取该值，具体 transport 缺口见 [RFC-0001](0001-nonreplayable-text-query.md)。

用 `0`、`False`、空字符串、默认探头类型或触发状态补齐这些字段，会把「设备没有报告」伪装成确定状态。插件也不能为了填满快照而改变通道、trigger 或 waveform 配置。

## 建议接口

把「可取得的状态」和「完整厂商快照」分开。可新增 V2 快照，允许每个字段明确表示未知，并保留缺失路径：

```python
@dataclass(frozen=True)
class ScopeHealthSnapshotV2:
    status_byte: int | None = None
    operation_condition: int | None = None
    questionable_condition: int | None = None
    acquisition_available: int | None = None
    acquisition_count: int | None = None
    sample_rate_hz: float | None = None
    error_queue_nonempty: bool | None = None
    waiting_for_trigger: bool | None = None


@dataclass(frozen=True)
class ScopeSnapshotV2:
    identity: ScopeIdentitySnapshot
    health: ScopeHealthSnapshotV2 | None = None
    channel: ScopeAnalogChannelSnapshotV2 | None = None
    timebase: ScopeTimebaseSnapshotV2 | None = None
    probe: ScopeProbeSnapshotV2 | None = None
    waveform: ScopeWaveformMetadataSnapshotV2 | None = None
    trigger: ScopeTriggerSnapshotV2 | None = None
    unavailable_fields: tuple[str, ...] = ()
```

示例只说明可空语义，具体类型名和迁移方式由 core 决定。各子模型同样需要把设备不一定具备的字段设为可空；仅把整个分区设为 `None` 会丢失 MSO8000 已能可靠查询的部分状态。

建议满足以下规则：

- `None` 表示当前设备没有可证明的查询合同，不等于默认值；
- `unavailable_fields` 使用稳定字段路径，例如 `probe.probe_type`；
- 每个返回字段必须来自只读查询或可证明恢复的状态事务；
- 消费型寄存器必须通过非重放接口读取，否则保持未知；
- CLI 和序列化输出保留 unknown，不把它格式化成具体数值；
- 现有完整 `ScopeSnapshot` 可保留给能填满全部字段的 driver。

核心已有的 `status_summary()` partial fallback 可以作为迁移入口，但目前只返回 identity 与 coupling。V2 应允许逐步增加类型化分区，而不要求某一家仪器先补齐所有 RTM 字段。

## capability 影响

核心发布可组合快照前，MSO8104 descriptor 不声明 `scope.snapshot`。Service 继续使用现有 partial summary，只返回已实现的 `scope.idn` 与 `scope.channel_coupling`。

核心发布新合同后，插件仍须逐字段严格解析，并把未查询字段保留为未知。截图、波形数据和错误队列不能为了快照便利被隐式消费。

## 替代方案

- 用零值或空字符串构造完整 `ScopeSnapshot`：返回内容不是设备状态。
- 把 `:TRIGger:STATus?` 当作 acquisition available/count：两者语义不同。
- 为每个厂商定义私有快照类型：绕过统一 Service、CLI 和序列化合同。
- 只返回 identity 与 coupling 并称为完整快照：现有 partial summary 已能表达该结果，不应错误声明 `scope.snapshot`。
