# SDS3000 对 WaveBench 核心的影响评估

[English](WAVEBENCH_CORE_RFC_EN.md)

## 结论

当前 SDS3054 插件不需要修改 WaveBench 核心即可完成 M0–M6。VICP 文本与二进制波形已通过现有 `PyVisaTransport` 和 `query_bin_block()` 实机验证；`scope.fetch_waveform` 与 `scope.capture_waveform(s)` 使用现有 `acquire` effect，已经要求 `read_write` 权限。

本评估只形成两个增量 RFC，不改上一目录的 WaveBench 仓库。两项建议都同时适用于 SIGLENT/LeCroy SDS3000、RIGOL DS1000Z 和 Rohde & Schwarz RTM2000，机器可读影响矩阵见 [`wavebench-core-rfc.json`](wavebench-core-rfc.json)。

## RFC 1：示波器配置状态与受控 patch

### 现有缺口

WaveBench 目前只有窄的 `scope.channel_coupling` 只读能力。三类驱动都在 capture 内部直接写垂直比例和时基，却没有通用配置 capability：

| 驱动 | 已有事实 | 当前缺口 |
| --- | --- | --- |
| `siglent.sds3000` | `CPL/TRA/VDIV/TDIV/TRMD` 已用于受控采集；手册另有 `OFST/TRSE/TRSL/TRCP/TRLV` | 无阻抗或耦合 setter；本次 CH1 从 50 Ω 改到 1 MΩ 只能人工操作 |
| `rigol.ds1000z` | 驱动内部已有 `set_vertical_scale()`、`set_time_range()`，capture 使用当前触发 | setter 不属于 capability，没有统一快照、回读和失败恢复契约 |
| `rohde-schwarz.rtm2032` | 已有完整 analog/timebase/edge-trigger 快照和内部 setter；另有 CH2 专用 trigger 方法 | CH2 专用方法无法成为通用公共接口，写失败锁存也未抽成跨驱动契约 |

### 建议接口

读取与写入必须拆开声明，避免只有读能力的驱动被迫提供 setter：

```text
scope.analog_channel_state       -> get_analog_channel_state(channel)
scope.analog_channel_configure   -> patch_analog_channel(channel, patch)
scope.timebase_state             -> get_timebase_state()
scope.timebase_configure         -> patch_timebase(patch)
scope.edge_trigger_state         -> get_edge_trigger_state()
scope.edge_trigger_configure     -> patch_edge_trigger(patch)
```

模拟通道公共字段建议包括 `enabled`、`coupling`、`termination_ohm`、`scale_v_per_div`、`offset_v`、`bandwidth_limit_hz` 和 `probe_ratio`。时基公共字段建议包括 `scale_s_per_div`、`range_s`、`position_s` 和 `reference`。边沿触发公共字段建议包括 `source`、`mode`、`slope`、`coupling`、`level_v` 和 `holdoff_s`。

状态对象必须带 `supported_fields`。patch 使用显式 `UNSET` 表示「不修改」，不能让 `None` 同时表示「不修改」「自动」和「未知」。厂商 token、SCPI 字符串和 VBS 路径不得进入公共模型。

### 操作契约

- 状态读取沿用 `stateful_read`，允许 `read_only` 与 `read_write`。
- patch 使用 `write`，只允许 `read_write`；unsupported field 必须在 I/O 前拒绝。
- 写入前读取所有将修改字段；写后精确回读；失败时逆序恢复。
- write、`*OPC?` 和已经收到部分响应的请求不得自动重试。
- 恢复失败返回 `StateDriftError`，并将当前 session 锁存为不可继续写；关闭后才能重新建立会话。
- timeout 使用现有 connection budget；只有厂商操作确实需要时才使用独立 operation-complete budget。

### 兼容影响

这是纯增量能力。现有 `scope.channel_coupling` 保留，后续可作为 `analog_channel_state` 的兼容视图；现有 capture 参数和返回模型不变。DS1000Z 的固定高阻可把 `termination_ohm` 标为只读，RTM2000 与 SDS3000 可声明可写支持，不要求所有厂商支持同一字段集合。

## RFC 2：可部分表达的状态模型 v2

### 现有缺口

当前 `ScopeSnapshot` 强制返回 identity、health、模拟通道、时基、probe、waveform metadata 和完整 edge trigger。当前 `ScopeAcquisitionStatus` 又强制包含 average 与 segmented 选件字段。

RTM2000 能填满这些模型，不代表所有示波器都应被迫照填。SDS3054 已能安全读取身份、耦合、触发模式和部分波形元数据；DS1000Z 也能读取身份、耦合和波形状态，但两个插件都不能诚实声明全量 v1 snapshot。

### 建议接口

新增版本化 capability，不原地放宽 v1：

```text
scope.snapshot_v2
scope.acquisition_status_v2
```

建议模型：

```text
ScopeSnapshotV2(
    components: Mapping[component_name, typed_component],
    unavailable: Mapping[component_name, unavailable_reason],
    complete: bool,
)

ScopeAcquisitionStatusV2(
    run_state,
    trigger_state?,
    average_count?,
    average_complete?,
    segmented_enabled?,
    segment_capacity?,
    segments_available?,
    supported_fields,
)
```

`unavailable_reason` 必须是封闭枚举，例如 `unsupported`、`option_missing`、`not_configured`、`firmware_unverified` 和 `query_failed`；不得放入可执行厂商文本。调用失败与字段不可用必须区分，不能用默认值冒充真实状态。

### 操作契约与兼容影响

- 两项均为 `stateful_read`，允许只读访问。
- 非消费型查询可按现有 read retry 执行；读后清除寄存器不得自动重放。
- 每个 component 使用明确 timeout；单个字段不可用不应让其他已验证字段消失。
- v1 capability 和数据类型保持原样，RTM2000 无需迁移；新驱动可优先声明 v2。
- v2 成熟后再单独决定 v1 的弃用窗口，不在 `0.8.x` 内破坏客户端。

## 不建议修改核心的项目

- **VICP transport**：现有 PyVISA 路径配合插件依赖 `PyVICP` 已通过文本与二进制实机验收。
- **波形二进制接口**：现有 `query_bin_block()` 足够读取 SDS3054 `WAVEDESC` 与 `DAT1`。
- **新的 transactional effect**：当前 `acquire` 已要求 `read_write`。应先把恢复覆盖与失败锁存写入具体 capability 契约，不急着增加一个语义重叠的 effect。
- **SDS3000 raw screenshot**：手册中的 `SCDP` 把画面发送到当前 hardcopy 设备，`SCDP?` 只返回状态，并非图片 payload；不能据此增加 raw-byte transport。
- **动态 descriptor 探测**：descriptor 加载必须保持零 I/O。数字通道或历史选件应在类型化操作内查询并失败关闭。

## 永久拒绝

不新增任意 raw SCPI、任意 VBS、MAUI `app` 对象反射、用户自定义恢复命令或绕过 identity/access/audit 的 transport 句柄。手册目录是审计台账，不是命令执行器。

## 若进入核心实现

核心修改应在 WaveBench 仓库使用独立规范分支和独立提交，并至少包含：三厂商 FakeTransport 合同测试、unsupported field 零 I/O、write 不重试、精确回读、逆序恢复、恢复失败锁存、v1 回归和 descriptor 零 I/O。核心发布新版本后，插件才提高最低版本；本分支不提前依赖未发布接口。
