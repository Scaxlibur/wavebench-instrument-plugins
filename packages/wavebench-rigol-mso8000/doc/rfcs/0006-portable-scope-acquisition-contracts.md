# RFC-0006：可移植的示波器采集状态与平均采集合同

状态：core R1 已实现（未发布）；MSO8104 受控开发采用 acquisition status V2 静态读取子集

目标仓库：WaveBench core

## 问题

当前 `ScopeAcquisitionStatus` 强制要求：

```text
average_count, average_complete, segmented_option_installed,
segmented_enabled, segmented_maximum_enabled,
segment_capacity, segments_available
```

该模型把平均状态和分段采集状态绑定在一起。RIGOL MSO8000 可以查询全局 acquisition type、平均次数、存储深度与采样率，但手册没有平均完成位，也没有与上述字段对应的 segmented acquisition 查询。`:TRIGger:STATus?` 报告触发系统的 `TD/WAIT/RUN/AUTO/STOP`，不能证明平均累积是否完成，更不能报告分段容量。

当前平均采集模型也绑定了另一种厂商机制。`ScopeAverageConfiguration` 强制要求：

```text
average_count, single_count, channel_arithmetic
```

MSO8000 使用全局 `:ACQuire:TYPE AVERages` 和 `:ACQuire:AVERages <count>`，没有 `single_count` 或逐通道 arithmetic 查询。现有模型还没有字段保存 acquisition type，因此即使插件把缺失字段伪装成 `1` 和 `AVERAGE`，`configuration_before == configuration_after` 也不能证明真正被修改的全局类型已经恢复。

此外，核心 request 把平均次数固定为 2～1024 的 2 次幂；MSO8000 手册声明 2～65536。插件可以只支持公共子集，但通用上限更适合作为 driver/descriptor 约束，而不是写死在跨厂商模型中。

## 建议接口

### 采集状态

把平均与分段状态拆成可选子模型，并允许报告设备实际具备的普通采集状态：

```python
@dataclass(frozen=True)
class ScopeAverageStatusV2:
    configured_count: int
    complete: bool | None = None


@dataclass(frozen=True)
class ScopeSegmentedStatusV2:
    option_installed: bool | None = None
    enabled: bool | None = None
    maximum_enabled: bool | None = None
    capacity: int | None = None
    available: int | None = None


@dataclass(frozen=True)
class ScopeAcquisitionStatusV2:
    acquisition_type: str | None = None
    running_state: str | None = None
    sample_rate_hz: float | None = None
    memory_depth: int | None = None
    average: ScopeAverageStatusV2 | None = None
    segmented: ScopeSegmentedStatusV2 | None = None
```

`complete=None` 表示设备没有完成位，不得由 trigger STOP、OPC 或已配置次数自动推导。具体名称和枚举由 core 决定，关键是不能要求每台示波器同时实现平均和分段采集。

### 平均采集配置

平均事务应表达实际机制和所有被修改的字段：

```python
@dataclass(frozen=True)
class ScopeAverageConfigurationV2:
    mechanism: Literal["global_acquisition", "channel_arithmetic", "combined"]
    acquisition_type: str | None
    average_count: int
    single_count: int | None = None
    channel_arithmetic: tuple[tuple[int, str], ...] | None = None


@dataclass(frozen=True)
class ScopeAverageCaptureResultV2:
    request: ScopeAverageCaptureRequestV2
    waveforms: tuple[WaveformData, ...]
    configuration_before: ScopeAverageConfigurationV2
    configuration_after: ScopeAverageConfigurationV2
    completion_evidence: Literal[
        "device_average_complete",
        "documented_single_completion",
        "unknown",
    ]
    restored_fields: tuple[str, ...]
```

成功结果不得使用 `completion_evidence="unknown"`。设备若没有平均完成位，driver 必须依赖厂商明确声明的另一种完成合同；仅观察到触发 STOP 不足以自动升级为平均完成证据。

平均次数范围应由 capability 元数据、descriptor option 或 driver 严格校验表达。Service 可以保留一个安全公共上限，但不应把某一设备的 1024 上限当作所有示波器的协议事实。

## 事务规则

无论具体模型如何命名，平均采集都应满足：

- 调用前显式确认 acquisition 已停止；
- 保存所有将被修改的 acquisition、平均和 channel arithmetic 字段；
- 每个写入必须回读，不能依赖设备自动取整；
- acquisition trigger 不重放；
- 完成证据不明确时锁存对应写域；
- 成功返回前恢复全部配置并再次回读；
- 配置恢复不等于 acquisition 运行状态恢复，二者分别报告。

## capability 影响

core 当前开发分支已实现 acquisition status V2。MSO8104 在受控开发中声明 `scope.acquisition_status_v2`：读取 type、sample rate、memory depth，并仅在 AVER 模式下读取 configured count；average complete、run state 与 segmented 分区保持 unavailable 或 not applicable。legacy `scope.acquisition_status` 与 `scope.capture_average` 仍不声明。当前 `0.9.0` 开发版本已受控声明普通 waveform/capture；这不提供平均采集完成条件，也不会设置或声称验证平均次数。

核心发布 V2 后，`scope.capture_average` 仍需 RIGOL 官方文档或后续获批的实机证据证明平均采集的完成条件，才能离线加实机 fixture 后启用。接口可表达不等于设备语义已经得到证明。

## 替代方案

- 把 trigger STOP 当成 `average_complete=True`：触发状态与平均累积状态不是同一合同。
- 固定 `segmented_option_installed=False`：手册没有查询不等于已证明未安装。
- 用 `single_count=1` 和每通道 `AVERAGE` 补齐配置：MSO8000 没有报告这些状态。
- 只恢复平均次数、不恢复 acquisition type：会留下可见且影响后续采集的状态变化。
