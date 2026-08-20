# WaveBench scope 通用扩展接口 RFC

> 状态：`Draft`（核心预审后修订，未接受）
> 修订：`R1`
> 证据仓库：WaveBench Instrument Plugins
> 核心评审基线：WaveBench `0.8.22`，`origin/master@006c431`
> 目标版本：未排期

## 摘要与状态边界

本文是供 WaveBench 核心团队预审的候选合同，不是已接受的公共 API。本文中的 `MUST`、
`SHOULD` 和 `MAY` 只表示候选合同的规范强度，不表示当前核心已经实现。

本修订吸收了核心团队对 `R0` 的审阅意见，重点补齐四类此前不完整的内容：

1. 公共操作如何进入核心 `OperationSpec`、Service、访问策略、资源租约、会话健康和 artifact；
2. `MESSAGE` binary 的边界、上限、超限、部分响应和失步处理；
3. 采集运行状态的状态机、单次采集完成证据、超时和恢复事务；
4. 类型化 trace 与三态错误检查的字段不变量和结果语义。

核心仓库未因本文修改，当前核心没有注册下文新增的 operation 或 capability。SDS800X HD
插件也不因本文声明这些能力；当前已声明能力仍只有 `scope.idn`、
`scope.channel_coupling`、`scope.fetch_waveform`、`scope.capture_waveform`、
`scope.capture_waveforms` 和 `scope.measurement_statistics`。

本文把内容分为三类：

- **现状证据**：已有核心代码、插件离线测试或受控实机观察；
- **候选合同**：核心接受后才能实现的公共接口；
- **待决问题**：需要核心团队冻结的选择，未解决前不得开始插件迁移。

## 术语与分层

| 术语 | 含义 | 不应混淆的对象 |
| --- | --- | --- |
| transport message | 一次 transport 交换，由 backend 证明起止边界 | TCP `recv()` 的物理分片 |
| application chunk | 一个波形或文件协议定义的逻辑分块 | transport message；一次 query 的任意重试 |
| operation | 由核心注册并受 `OperationSpec` 约束的公共动作 | driver 私有辅助函数 |
| capability | descriptor 声明的可发现能力 | 方法存在但未声明的偶然实现 |
| session health | 当前连接 epoch 的健康状态 | 仪器前面板显示的运行状态 |
| artifact | Service 产生的可审计结果和诊断元数据 | 原始二进制 payload 或完整命令日志 |

transport 只负责可靠地交付字节和结构化 I/O 状态；PNG、波形 preamble、样本字节序和数学
结果属于更高层的 driver/model。应用分块属于波形协议层，不能因为一次 `DATA?` 返回分成
多次底层 read 就自动生成多个 application chunk。

## 当前证据

| 证据编号 | 功能 | 证据 | 当前结论 |
| --- | --- | --- | --- |
| `E-BLOCK-DS` | definite block 截图 | DS1000Z [driver 测试](../../packages/wavebench-rigol-ds1000z/tests/test_driver.py)，离线 fake transport | 现有 `query_bin_block()` 可覆盖该类仪器，尚不是 backend EOM 实机证据 |
| `E-BLOCK-RTM` | definite block 截图、菜单和颜色控制 | RTM2000 [driver 测试](../../packages/wavebench-rohde-schwarz-rtm2000/tests/test_driver.py)，离线 fake transport | 旧 screenshot 参数只对部分设备可映射 |
| `E-MESSAGE-SDS` | raw PNG message | SDS804X HD 固件 `4.8.12.1.1.6.5`、PyVISA TCPIP `INSTR` / VXI-11 受控观察，见[硬件验收](../../packages/wavebench-siglent-sds800x-hd/doc/SDS800X_HD_HARDWARE_ACCEPTANCE.md) | 只有一个仪器族的一次完整 raw PNG 观察，尚未证明通用 backend EOM 合同 |
| `E-CAPTURE` | SINGLE、Stop 轮询、同次多通道读取 | 同一 SDS804X HD 实机记录和[插件测试](../../packages/wavebench-siglent-sds800x-hd/tests/test_driver.py) | 证明 vendor transaction 可行，不证明核心已有独立控制 API |
| `E-TRACE-RTM` | math/FFT 元数据 | RTM2000 [覆盖矩阵](../../packages/wavebench-rohde-schwarz-rtm2000/doc/RTM2000_COVERAGE_MATRIX.md)与离线测试 | 只有一类可复用 trace 证据 |
| `E-TRACE-SDS` | SDS math 函数关闭 | SDS804X HD 受控探测 | 不能为 SDS 构造通用 math/FFT trace |
| `E-ERROR-SDS` | 无文档化错误队列 | CN11G 手册审计和实机边界 | 不能发送猜测命令，也不能返回伪造空队列 |

当前证据只支持继续保持 `Draft`。特别是 `MESSAGE`、数字/reference trace、失败恢复和
跨 backend conformance fixture 都还没有第二个独立证据族。

## 目标

- 让 definite block 和 message-bounded binary 使用同一套 replay、session health、access
  policy、租约和审计合同。
- 让核心公共合同不暴露 backend session；当前 Python 插件仍是受信任代码，本文不声称提供
  进程级或运行时沙箱隔离。
- 让截图请求只使用仪器明确声明支持的 request tuple，并记录实际生效请求。
- 区分采集运行阶段、触发模式、平均/分段进度和完整 capture 事务。
- 让模拟、数字、数学、参考和频域轨迹使用同一套 source、坐标轴、单位和数组不变量。
- 让错误检查策略区分「能力明确不支持」「能力未知」「查询失败」和「设备返回错误」。
- 保留现有 capability，通过新增 capability 和核心版本门逐步迁移。

## 非目标

- 不在 transport 中解析 PNG、波形 preamble 或厂商文件格式。
- 不开放 raw SCPI、backend session、插件 parser 回调或任意 terminator。
- 不把 `*OPC?` 定义为物理触发完成条件。
- 不在本文设计数学表达式写入、FFT 配置或通用运算 AST。
- 不废弃现有 `scope.fetch_waveform`、`scope.capture_waveform(s)`、`scope.screenshot` 或
  `ScopeAcquisitionStatus`。
- 不为没有文档化错误队列的仪器猜测命令。
- 不因本文是 `Draft` 就提高任何插件的核心版本下限。

## 插件信任边界

当前 `DriverContext.open_transport()` 返回公共 Protocol，但运行时
`GuardedAuditedTransport.inner` 仍可被受信任 Python 插件访问。因此 R1 只规定「公共合同
不提供 backend session，插件代码不得依赖它」，不声称存在安全隔离。真正的 opaque facade、
进程隔离、运行时属性拒绝和负向沙箱测试应由单独的安全设计处理，不能借本 RFC 的措辞假装
已经实现。

## 规范用语与兼容边界

候选合同中的 `MUST` 表示互操作所需的不变量，`SHOULD` 表示默认实现，`MAY` 表示可选能力。
核心接受前，插件不得把候选 operation 放入 descriptor，也不得以 capability 名称存在为由
绕过核心 Service 或 transport gate。

旧核心 + 新插件、新核心 + 旧插件、旧核心 + 旧插件和新核心 + 新插件四种组合都必须在
factory、能力发现和第一次仪器 I/O 前得到确定结果；未知 capability 不能静默降级为已支持。

## 一、核心集成合同：OperationSpec、Service 与 artifact

### 1.1 现有核心字段与候选扩展

当前核心 `OperationSpec` 已有以下安全字段：
`effect`、`lease_mode`、`changed_fields`、`restore_coverage`、`required_verified_fields`、
`verification_fields`、`risk_flags`、`timeout_source`、access policy 和 capability 要求。
候选 operation MUST 先使用这些字段进入中央 registry；不能只在 driver Protocol 中声明方法。

当前核心的 `_session_preflight()` 只内建 `scope.identity` verifier；表中其余
`scope.run_state`、`scope.waveform_*`、`scope.display_*` 和 `scope.trace_configuration` 都是
待核心实现的验证器，不是插件可以自行写入 `verified_fields` 的旁路。

输入/输出 schema、取消、幂等性、并发策略和错误策略可以作为后续核心扩展，但在 R1 中不把
任意 Python 回调塞入公共合同。前置条件、恢复覆盖和验证字段必须可序列化、可审计。

### 1.2 候选 operation 映射

下表是 R1 的最小候选映射，字段完整不等于合同已经冻结。Service 和 CLI 项都是候选入口，
当前不存在，不能在插件侧自行模拟。所有 operation 的 `session_purpose` 为 `normal`；超时后的安全停止由核心另行签发
有界 `recovery` transaction。R1 保守地为所有仪器 operation 使用 `exclusive` lease，因为
当前 `ScopeService` 的 session lease 不会按 `OperationSpec.lease_mode` 动态切换。以后若开放
共享只读 session，需要单独证明 backend、仪器和 transaction lock 的并发语义。

| operation | capability | effect / lease | changed_fields | restore_coverage | required_verified_fields | verification_fields | risk_flags | timeout_source | 最低 access | Service / CLI / artifact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `scope.screenshot_profile` | `scope.screenshot_profile` | `stateful_read` / `exclusive` | `none` | `none` | `scope.identity` | `scope.identity`, `scope.screenshot_profile` | `profile_query` | `connection.timeout_ms` | `read_only` | `ScopeService.screenshot_profile()` / `wavebench scope screenshot profile` / `screenshot.profile` |
| `scope.screenshot_v2` | `scope.screenshot_v2` | `write` / `exclusive` | `scope.display_menu`, `scope.display_color`, `output.screenshot` | `screenshot-baseline-only` | `scope.identity` | `scope.identity`, `scope.display_menu`, `scope.display_color` | `front_panel_state`, `binary_response`, `temporary_display_setup` | `connection.timeout_ms` | `read_write` | `ScopeService.screenshot_v2(request)` / `wavebench scope screenshot capture` / `screenshot`、`effective_request`、`media_type`、`dimensions`、`framing` |
| `scope.acquisition_run_state` | `scope.acquisition_run_state` | `stateful_read` / `exclusive` | `none` | `none` | `scope.identity` | `scope.identity`, `scope.run_state` | `state_observation` | `connection.timeout_ms` | `read_only` | `ScopeService.acquisition_run_state()` / `wavebench scope acquisition status` / `acquisition.run_state` |
| `scope.acquisition_control` | `scope.acquisition_control`、同时要求 `scope.acquisition_run_state` | `write` / `exclusive` | `scope.run_state`, `scope.trigger`, `scope.acquisition` | `control-state-best-effort` | `scope.identity` | `scope.identity`, `scope.run_state`, `scope.trigger`, `scope.acquisition` | `trigger`, `acquisition_state`, `recovery_required` | `operation.deadline`（候选；当前核心 Service 尚不识别） | `read_write` | `ScopeService.acquisition_control(action)` / `wavebench scope acquisition start\|single\|stop` / `acquisition.control`、`observed_state`、`cleanup` |
| `scope.trace_metadata` | `scope.trace_metadata` | `stateful_read` / `exclusive` | `none` | `none` | `scope.identity` | `scope.identity`, `scope.trace_configuration` | `analysis_state` | `connection.timeout_ms` | `read_only` | `ScopeService.trace_metadata(source)` / `wavebench scope trace metadata` / `trace.metadata` |
| `scope.fetch_trace` | `scope.fetch_trace` | `acquire` / `exclusive` | `scope.run_state`, `scope.waveform_source`, `scope.waveform_mode`, `scope.waveform_transfer_window`, `output.trace` | `trace-baseline-only` | `scope.identity` | `scope.identity`, `scope.run_state`, `scope.waveform_source`, `scope.waveform_mode`, `scope.waveform_transfer_window` | `acquisition_state`, `temporary_transfer_setup`, `binary_response` | `operation.deadline`（候选；每次传输取剩余 deadline 与 connection timeout 的较小值） | `read_write` | `ScopeService.fetch_trace(source)` / `wavebench scope trace fetch` / `trace`、`metadata`、`integrity`、`error_check` |

`scope.screenshot_v2` 采用保守的 `write` effect，因为某些设备需要临时写菜单或颜色设置；
只支持 `device` 行为的设备仍可在 profile 中把该 operation 标为无状态副作用，但不能让
核心根据调用参数动态绕过 access policy。`scope.fetch_trace` 同理，默认按可能修改 transfer
选择处理。

`scope.screenshot_v2`、`scope.acquisition_control` 和 `scope.fetch_trace` 应把
`scope.errors` 放入 `optional_capabilities`，是否变成当前请求的必需能力由第六节的错误策略
和 `OperationSpec` 最低策略共同决定。profile、运行状态和 metadata 查询默认不触发错误队列，
避免一个只读观测产生额外的 consumptive read。

### 1.3 输入、前置条件与输出

为避免只有 operation 名称而没有可执行边界，R1 规定以下最小 schema；具体 Python 类型和
序列化格式仍待核心冻结：

| operation | 输入 | 零 I/O 前置条件 | 成功输出 |
| --- | --- | --- | --- |
| `scope.screenshot_profile` | 无 | identity 已验证；profile source 可用 | `ScopeScreenshotProfile` |
| `scope.screenshot_v2` | `ScopeScreenshotRequest` | profile 精确匹配；access 允许写入；必要的 baseline 可读 | `ScopeScreenshot` + effective request |
| `scope.acquisition_run_state` | 无 | identity 已验证；session healthy | `ScopeAcquisitionRunState` |
| `scope.acquisition_control` | `action ∈ {continuous, single, stop}` | identity 已验证；phase 不是 `unknown`（STOP recovery 另行授权） | `ScopeAcquisitionRunState` + cleanup/result diagnostics |
| `scope.trace_metadata` | 有效 `ScopeTraceRef` | source/index/name 不变量通过；identity 已验证 | `ScopeTraceMetadata` |
| `scope.fetch_trace` | `ScopeTraceRef`、points profile、error policy | source 已配置；sequence/segmentation 与 profile 兼容；必要时 acquisition stopped | `ScopeTraceData` + integrity/error artifact |

参数错误、能力不支持和前置条件失败 MUST 在任何仪器写入或 binary query 前返回；设备返回
错误、传输失败和完成证据不足则归入对应 operation result/exception，不得伪装成参数错误。

### 1.4 请求、结果和异常边界

候选核心应为每个 operation 生成可审计的请求和结果，至少包含：

```python
OperationRequest(
    operation_id: str,
    arguments: Mapping[str, Any],
    deadline: float | None,
    correlation_id: str,
)

OperationResult(
    value: object,
    diagnostics: Mapping[str, Any],
    observed_state: Mapping[str, Any] | None,
)
```

`OperationRequest.deadline` 使用单调时钟的绝对 deadline；artifact 只记录剩余时长或
`deadline_source`，不记录进程时间戳。`correlation_id` 在一次 Service operation 及其
recovery/verification 子事务中保持不变，便于把 cleanup 和错误检查归到同一操作。

`operation_id` MUST 使用稳定的小写点分隔名称；版本变化通过 capability/core version gate
处理，不在同一名称下改变输入或输出语义。异常至少区分：

- `unsupported_capability`：descriptor 明确没有能力；
- `unknown_capability`：核心或插件没有完成能力发现；
- `precondition_failed`：前置条件在任何写入和 binary 查询前失败；
- `access_denied`：访问策略不允许；
- `transport_io_error`：传输阶段失败，沿用现有结构化 framing、同步和 retry 字段；
- `completion_unproven`：操作可能已执行，但没有足够证据证明完成；
- `instrument_error`：设备明确返回错误。

### 1.5 恢复与 artifact 规则

所有可能写入仪器的候选 operation MUST 在 `OperationSpec` 中声明改变字段、恢复覆盖和
验证字段。主异常不得被恢复异常覆盖；结果或失败 artifact 应记录：

```text
operation
correlation_id
requested_arguments（去除敏感值）
observed_state_before / observed_state_after
session_health_before / session_health_after
cleanup.attempted / cleanup.succeeded / cleanup.error_code
error_check
```

artifact 只记录 framing、长度、媒体类型、状态 token 和摘要，不记录图片、原始波形、真实
resource、序列号或完整命令 payload。

## 二、binary framing 与 message 语义

### 2.1 两层 framing

首版只接受两种可证明的 transport response framing：

```python
class BinaryResponseFraming(str, Enum):
    DEFINITE_BLOCK = "definite_block"
    MESSAGE = "message"
```

- `DEFINITE_BLOCK`：应用层响应以 IEEE 488.2 `#N` 头声明 payload 长度；
- `MESSAGE`：backend 通过 EOI、VISA message END 或等价的明确事件报告一次响应结束。

底层 socket 的多次 `recv()`、串口暂时没有数据、读取 timeout 和换行都不是通用 message
边界。transport 不解析 PNG、波形或其他媒体；内容校验由 driver 完成。

### 2.2 definite block 的精确语法

候选 transport MUST 按以下语法解析：

```text
response := '#' + N + length_field + payload
N        := ASCII digit '1'..'9'
length_field := exactly N ASCII decimal digits
payload  := exactly the declared number of bytes
```

`#0`（indefinite block）、缺失长度位、非 ASCII 数字、长度溢出、声明长度与已消费字节不一致
都必须结构化失败。`#10` 表示零长度 payload 的语义是否允许由 operation profile 决定；不允许
把 `#0` 当作零长度 definite block。解析前必须校验长度上限，不能先按声明长度分配无限内存。

### 2.3 `query_binary` 与上限

候选公共方法为：

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

`max_bytes` MUST 是调用方或 `OperationSpec` 明确提供的正整数；公共方法不提供无限读取的
默认值。Service 计算的有效上限为 operation/profile 上限与 connection 上限的较小值；如果
当前 connection 配置尚无 binary 上限，`OperationSpec` 必须提供稳定正整数，不能退回无限
读取。现有 `query_bin_block()` 保留为 definite block 兼容入口，并在核心冻结兼容上限前
保持原有调用语义。

实现时必须同时修改 `InstrumentTransport` Protocol、全部 backend、
`GuardedAuditedTransport`、session `_AUTHORIZED_IO` / `_VERIFICATION_IO`、审计计数器和
结构化错误映射。只给某个 backend 增加方法会绕过核心会话授权，不符合候选合同。

### 2.4 message boundary 的能力证明

`binary.message_boundary` 是「backend 类型 + 具体 resource/session 能力」的联合声明：

| backend | 可声明条件 | 不能作为证据的行为 |
| --- | --- | --- |
| PyVISA | 具体 resource 能报告 EOI/message END，且同一锁内可恢复 read termination | 仅有 `read_raw()` 或一次成功的 timeout 读取 |
| RsInstrument | API 明确报告完整 message/EOI，并能在异常后报告同步状态 | 任意 `query_bin_block()` 成功 |
| TCP socket | 协议本身声明长度、EOM 或受控 message API | `recv()` 返回短块、idle timeout |
| serial | 只有设备和 backend 共同声明可证明的 EOM 才能提供 | 暂时没有数据、换行或固定延迟 |

R1 暂不批准任何现有 backend 声明 `binary.message_boundary`；上表是进入 conformance fixture
前必须满足的条件，不是能力白名单。

能力可在 open 时由 backend 静态类型和 resource 属性共同确定；若 backend 无法提供证明，
必须在发送命令前拒绝 `MESSAGE`，不得通过探测命令猜测。`MESSAGE` 交换应在同一资源锁内
临时关闭文本 read termination，完成或失败后恢复原设置；恢复失败必须进入 session health
状态机，不能当作普通 driver 解析错误。

### 2.5 超限、部分响应和失步

每个 backend MUST 在返回前给出同步结论。规则如下：

1. definite block 头声明的长度超过 `max_bytes` 时，backend 必须选择一种确定行为：安全地
   流式消费完整声明 payload 后抛出 `BinaryLimitExceeded`，或立即关闭/毒化 session；不能在
   healthy session 中留下未消费 payload。
2. message 读取超过上限时，只有在 backend 能继续消费到已证明的 message END 时才允许
   「消费后失败」；否则必须终止资源并把 session 标为 `poisoned`。
3. timeout、部分响应、终止符恢复失败和 malformed header 必须映射到现有
   `TransportIOError` 的 `phase`、`response_progress`、`synchronization`、`attempts` 和
   `replay_policy` 字段；不得重试已经发送且同步未知的完整 query。
4. 建议的细分错误码为 `binary_framing_error`、`binary_limit_exceeded`、
   `binary_truncated`、`binary_timeout` 和 `binary_trailing_data_error`；它们是候选稳定码，
   在核心接受前不能由插件自行定义同名公共异常。
5. R1 的 `query_binary(command=...)` 不接受 `ReplayPolicy.READ_CONTINUATION_ONLY`，因为该
   签名必然携带一个可能被发送的 command；必须在 `BEFORE_SEND` 阶段以 `NOT_SENT` 拒绝。
   未来若需要 continuation，应设计只接受 core-issued response token 的独立
   `read_binary_continuation(token, max_bytes=...)`，只消费同一响应且绝不重发 command。

definite block 已消费声明 payload 后发现额外字节时，额外字节不得被当作本次 payload，也
不得静默丢弃：若 backend 能证明它们属于同一 message 的文档化 terminator，应按 variant
规则保留或报告；否则同步状态为 `LOST`，session 进入 `poisoned`。下一次 query 只有在
backend 明确保留并授权 continuation token 时才可继续。

`BinaryMessage` 是否需要作为带 `declared_length`、`consumed_bytes`、`trailing_bytes` 的
metadata 返回对象，而不是只返回 `bytes`，列为 `[OPEN]`。无论最终返回类型如何，尾随字节
都不能用 `rstrip()` 静默删除。

### 2.6 内容校验与应用层分块

PNG driver 负责 signature、chunk、IEND、尺寸、MIME type 和 profile 允许的尾部字节校验。
SDS800X HD 的实测 raw PNG 在 IEND 后有一个尾字节；driver 只能在确认 IEND 后按 profile
精确处理，不能把它当作 transport terminator。

波形多块读取另行携带：

```text
record_id / acquisition_id
chunk_index
offset_samples
points
total_points（可选）
is_last
```

只有同一 `record_id`、连续 offset、唯一 chunk index 且最终点数一致时才允许拼接。不同
query 的结果不得无条件拼接；样本格式、字节序和 preamble 解码仍属于 waveform decoder。

## 三、screenshot profile

### 3.1 明确 request tuple

格式、菜单和颜色不是独立笛卡尔积。候选 profile 使用明确支持的 request tuple：

```python
ScreenshotMenuMode = Literal["device", "include", "exclude"]
ScreenshotColorMode = Literal["device", "color", "monochrome", "inverted"]

@dataclass(frozen=True)
class ScopeScreenshotRequest:
    format: str = "png"
    menu_mode: ScreenshotMenuMode = "device"
    color_mode: ScreenshotColorMode = "device"

@dataclass(frozen=True)
class ScopeScreenshotVariant:
    request: ScopeScreenshotRequest
    media_type: str
    framing: BinaryResponseFraming
    max_bytes: int
    width_px: tuple[int, int] | None = None
    height_px: tuple[int, int] | None = None
    changed_fields: tuple[str, ...] = ()

@dataclass(frozen=True)
class ScopeScreenshotProfile:
    variants: tuple[ScopeScreenshotVariant, ...]
    source: Literal["descriptor", "queried", "combined"] = "descriptor"

@dataclass(frozen=True)
class ScopeScreenshot:
    data: bytes
    media_type: str
    width_px: int | None
    height_px: int | None
    requested: ScopeScreenshotRequest
    effective: ScopeScreenshotRequest
    framing: BinaryResponseFraming
```

`variants` MUST 非空，每个 request 只能出现一次，`media_type` 必须与格式对应，`max_bytes`
MUST 为正数，尺寸范围的上下界必须为正数且递增。请求未精确匹配一个 variant 时在任何 I/O
前拒绝。这样不会把 format、menu、color、framing 和 media type 错当成独立笛卡尔积。
`device` 表示保留仪器当前行为，不等于 `include` 或 `exclude`。profile 可以是静态
descriptor、仪器查询结果或两者交集；查询结果不得扩大 descriptor 未声明的安全上限，
结果中的 `effective` 和 variant 必须一致。

driver 负责格式签名和媒体类型一致性，核心负责上限、artifact 字段和 transport framing。
非 PNG 格式的完整校验由对应 format handler 定义，不能默认为「任意 bytes 都合法」。

### 3.2 状态副作用与旧接口

若 menu/color 设置会写入前面板状态，`scope.screenshot_v2` 必须记录对应 changed fields、
恢复覆盖和有效 request。恢复失败时主截图结果不得伪装为成功。

现有 `scope.screenshot` 仅在 profile 明确包含等价旧参数时适配；旧 driver 忽略
`include_menu` 的行为不能由通用 adapter 静默继承。无法证明参数已生效时必须报告
`unsupported_capability` 或 `precondition_failed`。

现有 DS1000Z driver 会丢弃 `include_menu`，因此不能宣称满足 `exclude`；RTM2000 driver
会写入菜单和颜色设置，因此迁移时必须把这两个字段纳入 changed/restore/verification。
两者不能共享一个不检查 effective request 的旧接口 adapter。

## 四、采集运行状态与控制

### 4.1 组合状态模型

`ScopeAcquisitionStatus` 继续表示平均和分段信息。运行状态使用独立模型，`AUTO/NORMAL/SINGLE`
是 trigger mode，不是 phase：

```python
ScopeAcquisitionPhase = Literal[
    "unknown",
    "stopped",
    "ready",
    "arming",
    "waiting",
    "acquiring",
    "rolling",
    "stopping",
    "complete",
    "error",
]

ScopeTriggerMode = Literal[
    "auto",
    "normal",
    "single",
    "forced",
    "roll",
    "unknown",
]

ScopeCompletionProof = Literal[
    "count_delta",
    "identity_delta",
    "state_transition",
    "unavailable",
]

@dataclass(frozen=True)
class ScopeAcquisitionRunState:
    phase: ScopeAcquisitionPhase
    trigger_mode: ScopeTriggerMode
    raw_state: str
    acquisition_count: int | None = None
    acquisition_identity: str | None = None
    completion_proof: ScopeCompletionProof = "unavailable"
```

`raw_state` MUST 是短、可打印、无换行 token；无法无损映射时使用 `unknown`，不能把相近
文字硬映射成 `stopped` 或 `complete`。`acquisition_count` 必须是非负整数；
`acquisition_identity` 只能是经 driver 校验的短 token，不能包含 resource 或序列号。

### 4.2 状态迁移与操作语义

候选状态迁移至少包括：

| 操作/事件 | 允许起始 phase | 预期观察 | 失败语义 |
| --- | --- | --- | --- |
| `start_continuous` | `stopped`、`ready`、`complete` | 写入后回读 `ready`/`acquiring`/`rolling` | 写后回读失败，保留 session health 和 cleanup 结果 |
| `arm_single` | `stopped`、`ready`、`complete` | 记录基线后回读 `arming`/`waiting`/`ready` | 只证明发起，不证明物理触发完成 |
| trigger accepted | `arming`、`waiting`、`ready` | `acquiring` 或 `complete` | 外部变化时回读为 `unknown` |
| acquisition complete | `acquiring` | `complete` 或 `stopped` 且有 completion proof | 只有原本已 `stopped` 不足以证明新采集完成 |
| `stop_acquisition` | 任意非 `unknown` phase | 回读 `stopped` | 幂等；回读失败时保留 `uncertain`/`poisoned` |
| 外部/设备错误 | 任意 | `error` 或 `unknown` | 必须重新查询确认，不能继续普通 I/O |

控制协议建议为：

```python
class ScopeAcquisitionRunStateDriver(InstrumentDriver, Protocol):
    def get_acquisition_run_state(self) -> ScopeAcquisitionRunState: ...

class ScopeAcquisitionControlDriver(ScopeAcquisitionRunStateDriver, Protocol):
    def start_continuous(self) -> ScopeAcquisitionRunState: ...
    def stop_acquisition(self) -> ScopeAcquisitionRunState: ...
    def arm_single(self) -> ScopeAcquisitionRunState: ...
```

`arm_single()` MUST 在写入前读取 baseline token：优先使用 `acquisition_count`，否则使用
`acquisition_identity`，再否则记录可证明的状态迁移。等待完成时必须看到 count/identity
变化，或观察到明确的 `arming/waiting/acquiring -> complete/stopped` 迁移；调用前本来就是
`stopped` 不能单独作为完成条件。没有任何 completion proof 时返回 `completion_unproven`，
不得返回成功 waveform。

count 比较使用写入前的同一 acquisition mode 基线。新 count 大于基线才构成 `count_delta`；
count 下降或归零只在 profile 明确声明「arm 会重置计数」且同时观察到有效状态迁移时成立。
计数器回绕只有在 profile 声明 modulus 后才能比较。mode 改变、仪器重启或前面板重置会使
原 baseline 失效，必须改用新的 identity/state-transition 证据，不能沿用旧 count。

`stop_acquisition()` MUST 幂等：已经 `stopped` 时可直接成功，但仍应返回观察到的状态；非
`stopped` 时必须写入并 query-back。一个 session 同时只允许一个 control operation，且控制
操作使用 exclusive lease。

### 4.3 deadline、取消和恢复

等待 deadline 来自 operation request；若调用方未给出，候选默认使用
`connection.opc_timeout_ms`，但当前核心 `_operation_timeout_ms()` 只接受既有 timeout source，
因此这是必须先冻结的核心变更，不是插件可自行假定的字段。

超时或取消时：

1. 保留主异常和最后一次观察状态；
2. 在 session `healthy` 或 `uncertain` 且核心已授权 recovery transaction 时，best-effort
   执行 `STOP` 并 query-back；
3. 若 session 已 `poisoned`，普通 STOP I/O 必须继续被 gate 拒绝，应关闭并重新建立连接，
   不得从插件直接访问 backend session；
4. cleanup 的成功、失败和最终 `SessionHealth` 写入 artifact，但不能覆盖原始 timeout/cancel
   异常。

现有 `capture_waveform(s)` 仍是 vendor transaction。核心不能仅凭三项控制方法重新拼装它，
因为通道配置、一次 acquisition 的多通道一致性、transfer 临时状态和恢复仍属于 driver
合同。

多通道 capture MUST 返回同一 `acquisition_identity`；部分通道失败时 artifact 应记录
`completed_channels`、`failed_channel`、`acquisition_identity` 和是否发生重采集，禁止为了
补齐缺失通道而隐式重新触发。

## 五、类型化 trace source 与数据不变量

### 5.1 source、轴和 operation

候选 source kind 增加 `spectrum`，用受限的 FFT operation 描述产生方式；这比把 FFT
伪装成模拟 channel 更明确。是否最终采用 `spectrum` 或独立 `fft` kind 列为 `[OPEN]`，但
无论选择哪一种，频率轴都不能声明为时间轴。

```python
ScopeTraceKind = Literal["analog", "digital", "math", "reference", "spectrum"]
ScopeAxisKind = Literal["time", "frequency", "index", "unknown"]
ScopeAxisUnit = Literal["s", "Hz", "1", "unknown"]
ScopeTraceUnit = Literal[
    "v",
    "mv",
    "a",
    "db",
    "dbm",
    "degree",
    "percent",
    "1",
    "unknown",
]
ScopeTraceMagnitudeSemantics = Literal["absolute", "relative", "linear", "unknown"]
ScopeTraceOperation = Literal[
    "identity",
    "add",
    "subtract",
    "multiply",
    "divide",
    "differentiate",
    "integrate",
    "fft_magnitude",
    "fft_phase",
    "reference_copy",
    "device_other",
    "unknown",
]

@dataclass(frozen=True)
class ScopeTraceRef:
    kind: ScopeTraceKind
    index: int | None = None
    name: str | None = None
```

`index` 和 `name` MUST 恰有一个有效值；`index` 必须是 `0..65535` 的整数且不能是 `bool`，
具体仪器 profile 再收紧范围。`name` 必须包含 `1..64` 个 Unicode code point、去除首尾空格
后不变、全部可打印且不得含控制字符。厂商 token 只存在于 driver，不进入公共模型。

```python
@dataclass(frozen=True)
class ScopeAxisMetadata:
    kind: ScopeAxisKind
    unit: ScopeAxisUnit
    start: float | None
    increment: float | None
    points: int

@dataclass(frozen=True)
class ScopeTraceMetadata:
    source: ScopeTraceRef
    x_axis: ScopeAxisMetadata
    y_unit: ScopeTraceUnit
    y_semantics: ScopeTraceMagnitudeSemantics
    value_encoding: Literal["real", "digital_bitmask"]
    y_increment: float | None = None
    y_origin: float | None = None
    y_resolution_bits: int | None = None
    operation: ScopeTraceOperation = "unknown"
    inputs: tuple[ScopeTraceRef, ...] = ()
    digital_channels: tuple[int, ...] = ()

@dataclass(frozen=True)
class ScopeTraceData:
    metadata: ScopeTraceMetadata
    values: np.ndarray
```

### 5.2 数组、单位和语义约束

- `points` MUST 等于 `len(values)`；values MUST 是一维、非空数组。
- axis 的 `points >= 1`。`time`、`frequency` 和 `index` 的 `start`、`increment` 必须
  finite，`increment > 0`，计算出的最后一个坐标也必须 finite；`unknown` 的 `start` 和
  `increment` 必须为 `None`。
- `analog`、`math`、`reference` 和 `spectrum` 使用 finite、real、`float64` 值；核心应复制
  并设置只读，不能把 driver 的可变数组直接暴露给调用方。首版明确拒绝 complex dtype，
  FFT 的复数结果必须选择 magnitude 或 phase 语义后再进入模型。
- `digital` 使用无符号整数 bitmask（首版上限 `uint16`），并在 metadata 中说明有效 bit
  与 `digital_channels` 的映射；`digital_channels` 必须非空、唯一且位于 `0..15`，bit N 对应
  digital channel N。非 digital trace 的 `digital_channels` 必须为空，不把数字值编码成
  浮点电压。
- `time` 轴使用 `s`，`frequency` 轴使用 `Hz`，`index` 轴使用 `1`；未知轴只能使用
  `unknown`，不能同时声称精确的 start/increment 换算。`kind` 与 unit 不匹配时必须拒绝，
  不能把 `Hz` 当作任意显示标签。
- `y_unit` 使用核心已有单位校验和语义组合；候选 token 包括 `v`、`mv`、`a`、`db`、`dbm`、
  `degree`、`percent`、`1` 和 `unknown`。适用的组合沿用核心
  `MagnitudeUnit` / `MagnitudeSemantics` 规则：`dbm/absolute`、`db/relative`、
  `v|mv/linear`；`a` 等新增维度需要核心先扩展单位模型。无法证明时使用 `unknown/unknown`，不能用任意字符串绕过现有
  `FrequencyResponseTrace` 等模型的单位/语义校验。
- `digital_bitmask` 的 y unit 固定为 `1`，semantics 为 `unknown`；`spectrum` 的 dB/dBm
  结果必须明确 absolute/relative，不能只给一个 dB 字符串。
- `analog` 和 `digital` 的 `operation` MUST 为 `identity` 且 `inputs` 为空；`reference_copy`
  恰有一个 input；`differentiate`、`integrate`、`fft_magnitude` 和 `fft_phase` 恰有一个 input；
  `add`、`subtract`、`multiply` 和 `divide` 恰有两个 input。
- `spectrum` 的 operation MUST 为 `fft_magnitude` 或 `fft_phase`，且 x 轴 MUST 为
  `frequency`。`device_other` 和 `unknown` 可以用于只读 metadata，但在 operation catalog
  和单位语义冻结前不能声称结果可跨仪器比较。

### 5.3 迁移和读取前置条件

现有模型的单向迁移建议如下：

| 现有模型 | 候选 trace 映射 | 约束 |
| --- | --- | --- |
| `WaveformData` | `analog` | 保留原 `fetch_waveform`；反向适配只允许 analog |
| `ScopeDigitalWaveform` | `digital` | 保留 bitmask、通道集合和时间轴校验 |
| `ScopeDerivedWaveformMetadata` | `math` 或 `reference` metadata | 不把 `source_kind` 丢失 |
| `ScopeFftStatus` + 频域数据 | `spectrum` | `ScopeFftStatus` 继续兼容，频率轴单独表达 |

`fetch_trace()` 是 query/read operation，但若需要临时改变 source、transfer window 或停止
采集，必须声明相应 `changed_fields` 和恢复覆盖。默认前置条件为：source 已配置、必要时
acquisition 已停止、sequence/segmentation 状态与 source 合同一致、points 属于 profile、
错误检查策略已解析。前置条件失败必须发生在任何 transfer 写入或 binary query 前。
对只声明普通非分段记录的 `fetch_trace` 和现有 `fetch_waveform`，sequence ON 必须返回
`precondition_failed` 或 `unsupported_state`；SDS804X HD 已提供零 waveform 写入、零 binary
query 的实机拒绝证据，但该规则仍需第二个厂商 fixture。

建议接口：

```python
def get_trace_metadata(self, source: ScopeTraceRef) -> ScopeTraceMetadata: ...

def fetch_trace(
    self,
    source: ScopeTraceRef,
    points: str = "dmax",
    check_errors: bool = True,
) -> ScopeTraceData: ...
```

## 六、错误检查策略与 artifact

### 6.1 策略模型

现有 `scope.check_errors: bool` 保持兼容。候选配置扩展为：

```python
ErrorCheckPolicy = Literal["required", "if_supported", "disabled"]
ErrorCheckTiming = Literal["before", "after", "before_and_after"]
DrainMode = Literal["none", "one", "all"]
ClearMode = Literal["never", "explicit_only"]
UnavailablePolicy = Literal["reject", "skip_unsupported", "skip_unknown"]
InstrumentErrorPolicy = Literal["fail", "record_and_continue"]

@dataclass(frozen=True)
class ErrorCheckSpec:
    policy: ErrorCheckPolicy
    timing: ErrorCheckTiming = "before_and_after"
    max_records: int = 16
    drain: DrainMode = "all"
    clear: ClearMode = "never"
    on_unavailable: UnavailablePolicy = "reject"
    on_instrument_error: InstrumentErrorPolicy = "fail"
```

候选 `ErrorCheckSpec` 至少包含 `policy`、`timing`、`max_records`、`drain`、`clear` 和
`on_unavailable`；上面的默认值是 R1 建议，不是当前核心配置。`max_records` MUST 为正数；
`drain="none"` 不发送队列读取，`one` 最多读取一条，`all` 读取至终止 token 或上限。
自动 clear 不进入首版合同。

| 策略 | capability 明确支持 | capability 明确不支持 | capability 未知 |
| --- | --- | --- | --- |
| `required` | 按 timing 执行；空队列是成功 | 在 I/O 前拒绝 | 在能力发现完成前拒绝 |
| `if_supported` | 实际执行检查 | 不发送探测命令，记录 `skipped_unsupported` | 在 I/O 前以 `unknown_capability` 拒绝，并记录 `skipped_unknown` |
| `disabled` | 不发送错误队列查询 | 不发送 | 不发送 |

`check_errors=true` 映射为 `required`，`false` 映射为 `disabled`。`if_supported` 不能简单
等价于 `false`：有 capability 时必须查询，查询失败也必须报告真实 failure，而不是
`unsupported`。普通 transport/protocol/instrument response error 不因 `disabled` 而被吞掉。

配置优先级从强到弱为：`OperationSpec` 最低策略、单 operation 显式覆盖、仪器全局策略、
旧布尔配置映射。策略强度为 `required > if_supported > disabled`；低优先级或调用方参数不能
削弱 `OperationSpec` 的最低要求。未配置新字段时继续使用旧布尔映射，默认行为不改变。

`on_unavailable="reject"` 只适用于 `required` 或 OperationSpec 强制规则；
`if_supported` 的未知能力固定使用 `unknown_capability`，不得由插件选择性试探。失败的
错误队列查询遵循 `on_instrument_error`，但 transport/session/protocol failure 始终中止当前
operation，不得被 `record_and_continue` 吞掉。

### 6.2 错误记录与生命周期

候选错误记录为：

```python
@dataclass(frozen=True)
class ErrorRecord:
    code: str | int | None
    message: str
    severity: str | None
    raw: str
    source: str
    observed_at: str
    correlation_id: str | None
```

核心必须明确查询是 peek 还是 drain；R1 建议默认最多读取 `max_records`，不自动 clear，
并区分空队列、队列不可用和查询本身失败。首版 `scope.errors` 视为 consumptive drain：
读取到「无错误」终止 token 或达到 `max_records`。达到上限仍未看到终止 token 时以
`error_queue_incomplete` 失败，不能把截断列表当作完整检查。

before 阶段发现已有记录时，主 operation 不发送并报告 `preexisting_instrument_error`；这些
记录不归属于新的 `correlation_id`。after 阶段发现记录时，operation 报告
`instrument_error`，并保留已经发生的副作用和 cleanup 状态。错误队列查询本身失败时始终
是 `failed`，不能降级成 unsupported。批量通道共享一次 operation correlation，不把同一组
设备错误任意复制到每个通道。

### 6.3 固定 artifact 结构

每个使用错误策略的 operation 至少写入：

```json
{
  "policy": "if_supported",
  "capability": "scope.errors",
  "supported": false,
  "status": "skipped_unsupported",
  "timing": "before_and_after",
  "records": [],
  "drained": false,
  "cleared": false
}
```

`status` 的候选值为 `performed_empty`、`performed_records`、`skipped_unsupported`、
`skipped_unknown`、`disabled`、`failed`。当前 SDS800X HD 没有文档化错误队列，插件继续
要求显式 `check_errors=false`，不声明 `scope.errors`。

artifact 中的 `supported` 使用 `true`、`false` 或 `null`；`null` 只用于能力未知并导致操作
拒绝的情况。错误记录的 `raw` 字段只能进入受控本地诊断；公开 artifact 使用结构化 code、
经过长度限制的 message、时间和 correlation，不复制可能包含资源或设备私有内容的原文。

## 七、能力发现、版本门与旧接口

建议新增 capability：

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
3. 使用新 transport 或新 capability 的插件提高 wheel 和 descriptor 的核心下限；
4. 旧核心 + 新插件在 factory 和第一次仪器 I/O 前明确拒绝；
5. 新增可选 capability 不自动要求升级 `wavebench.instrument.v2`；
6. 在 operation registry、Service、CLI 和 artifact schema 未同时冻结前，插件不得声明新能力。

## 八、conformance 测试矩阵与证据要求

| 层级 | 必测内容 | 当前状态 |
| --- | --- | --- |
| OperationSpec/Service | capability、access、lease、changed/restore/verification、artifact | 核心尚无候选 operation，待实现 |
| binary model | `#N` 精确语法、`#0` 拒绝、长度溢出、`max_bytes`、尾部和 continuation | 需要新增 fake vectors |
| backend | PyVISA/RsInstrument/TCP/serial 的 message 能力证明、终止设置恢复 | 只有 SDS raw PNG 一次实机观察 |
| guarded transport | access、计数、healthy/uncertain/poisoned、超限后失步 | 需要失败恢复测试 |
| plugin trust boundary | 公共 Protocol 不暴露 session；禁止插件依赖 `.inner` 的代码审计 | 当前不是沙箱；opaque facade 不在 R1 范围 |
| screenshot | request tuple、PNG signature/IEND、媒体类型、尺寸、尾部字节 | 仅 SDS raw PNG 探测 |
| acquisition | baseline count/identity、READY、状态转移、幂等 STOP、超时 recovery | SDS vendor capture 已验收，公共控制未实现 |
| trace | source/index/name、dtype、只读数组、points、单位和 time/frequency 轴 | RTM2000 有部分证据，需第二族 fixture |
| errors | 支持/不支持/未知 × 空队列/有错误/查询失败 | 当前仅布尔兼容路径 |
| compatibility | 新旧核心/插件四组合、factory 拒绝、CLI/artifact | 待核心合同冻结 |
| opt-in hardware | 至少两种 framing、两个厂商状态机、两种 trace axis | 当前证据不足 |

### 8.1 必备 fixture 与失败向量

在 RFC 进入 `Proposed` 前，至少需要带有 backend、resource class、固件版本和证据文件
链接的 fixture：

- definite block：合法 `#N`、`#0`、非法长度位、截断、超限和尾部数据；
- message：分片读取、EOM、超限后 drain/poison、termination 恢复失败和下一次 query；
- acquisition：调用前已 stopped、count 不变、外部前面板改状态、timeout 后 STOP 失败；
- trace：analog/digital/math/reference/spectrum、空 name、控制字符、非 finite 数值、
  只读数组和 points 不一致；
- errors：三种 policy、能力未知、空队列、查询失败、drain 上限和 correlation；
- compatibility：旧核心 + 新插件与新核心 + 旧插件的能力发现和第一次 I/O 行为。

图片、原始波形、真实 resource、序列号和完整命令日志不进入仓库；只保留 framing、长度、
状态迁移、固件版本和数值摘要。

## 九、里程碑

| 里程碑 | 范围 | 退出条件 |
| --- | --- | --- |
| M1 | OperationSpec 与 artifact schema | 六项候选 operation 进入 registry，Service/access/lease 测试通过 |
| M2 | binary framing 与 backend capability | definite/message fake、超限、失步、termination 恢复测试通过 |
| M3 | screenshot profile/v2 | definite block 和 raw message 两种 fixture 通过 |
| M4 | acquisition run state/control | 两个厂商状态机、READY、baseline proof、幂等 STOP、timeout recovery 通过 |
| M5 | trace source/axis | analog、digital、math、reference、spectrum 的跨厂商 fixture 通过 |
| M6 | error policy、版本门和迁移 | 三态 artifact、四组合兼容和 CLI/Service 入口冻结 |
| M7 | opt-in 实机 | 核心离线回归通过，实机范围另行授权 |

各里程碑应分别提交；不得把 transport、scope model、Service 和插件迁移压成一个不可回滚
改动。

## 十、已否决方案

- 插件直接访问 `transport.session` 或 backend；当前只能以「公共合同不提供」约束，不能声称
  Python 运行时沙箱隔离；
- 给 `query_bin_block()` 增加含义模糊的 `raw=True`；
- 使用换行、idle timeout 或 `rstrip()` 推断 PNG 成功结束；
- 在 transport 内置 PNG parser；
- 忽略 screenshot 的 menu 参数；
- 把 trigger status 填入现有 `ScopeAcquisitionStatus`；
- 用 `*OPC?` 统一判断物理触发完成；
- 把 math/reference/FFT 编成负数或大号 channel；
- 扩宽 `WaveformData.channel` 为任意字符串；
- 为没有错误队列的仪器返回空列表；
- 超过 `max_bytes` 后在 healthy session 中留下未消费响应。

## 十一、R1 待决问题

1. `OperationSpec` 是否增加输入/输出 schema、取消、幂等性、并发和 error policy 字段，还是
   先以现有字段冻结第一版。
2. `query_binary()` 的兼容上限放在 connection 配置、operation spec 还是二者的最小值。
3. 超限后各 backend 是否都能安全 drain；不能 drain 时统一 close 还是显式 `poisoned`。
4. 哪些 PyVISA resource class 和 RsInstrument API 能稳定证明 message END。
5. `BinaryMessage` 是否返回 consumed/trailing metadata；`READ_CONTINUATION_ONLY` 如何授权。
6. screenshot profile 使用 descriptor、查询结果还是两者交集；旧 screenshot adapter 的拒绝码。
7. acquisition deadline 是否引入 `operation.deadline`，以及 poisoned session 的 recovery/reopen API。
8. completion proof 在 count/identity 均不可用时是否允许 `state_transition`，其最小观察序列是什么。
9. `spectrum` 是否作为独立 `ScopeTraceKind`，以及单位校验复用哪些现有核心模型。
10. error queue 的 peek/drain/clear 生命周期、默认 timing 和 `if_supported` 对 acquire 的适用范围。

上述问题解决、取得跨厂商 fixture，并完成 Service/CLI/artifact 评审前，RFC 必须保持 `Draft`。
主仓库未接受本文时，插件不得声明这些新 capability 已由核心提供。
