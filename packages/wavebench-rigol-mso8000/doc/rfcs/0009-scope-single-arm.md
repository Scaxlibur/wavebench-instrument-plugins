# RFC-0009：可验证的示波器 SINGLE arm 合同

状态：提议

目标仓库：WaveBench Core

## 问题

现有 `scope.acquisition_control` 把连续启动、停止和「已证明完成」的 SINGLE 采集放在同一 capability 中。完成式 SINGLE 的返回模型要求记录标识变化、采集计数变化或可观察的非终态到终态迁移；这是获取新波形的必要边界，不能放宽。

MSO8104 的 `:SINGle` 可能在首次 LAN 状态查询前已经触发并回到 STOP。此时不能由 STOP 推断本次采集完成，也不能将当前屏幕波形标记为新记录。

手册审计未发现可查询的新记录 ID、采集计数、记录世代、时间戳或可用的采集事件寄存器：

- `:TRIGger:STATus?` 只返回 `TD/WAIT/RUN/AUTO/STOP`；
- `:WAVeform:PREamble?` 的 count 是平均次数，非记录计数；
- `:RECord:CURRent?` 是播放帧，且录制/回放时 SINGLE 无效；
- `:WAVeform:STATus?` 明确无实际作用；
- 两次 source 双路 OFF 的受控 SINGLE 探测中，`*OPC?` 均返回 `1`，但随后 run-state 仍为 waiting。

因此 `*OPC?` 只能证明命令处理，不能作为物理触发、采集完成或新波形的证据。

然而，开发者仍需要一个安全的公共操作来请求 SINGLE。这个操作必须允许「命令已发送但状态已瞬时终止」的情况，同时明确不返回完成或新波形结论。

## 目标与非目标

本 RFC 新增一个 arm-only 操作：

- 请求设备进入 SINGLE 模式；
- 读取并返回一次 arm 后状态观察；
- 成功时保留设备的 SINGLE 状态，不恢复原始 trigger/acquisition 配置；
- 失败或状态不符合合同时执行既有 acquisition recovery 与新鲜验证。

本 RFC 不做以下事情：

- 不证明触发已经发生；
- 不证明采集已经完成；
- 不返回或读取 `WaveformData`；
- 不允许 capture/fetch 将 arm-only 结果当作新记录证明；
- 不改变既有 `scope.acquisition_control`、`scope.acquisition_single` 或 CLI `single` 的完成式语义。

## 建议接口

### 新 capability 与 operation

新增可选 capability：

```text
scope.acquisition_single_arm
```

新增 operation：

```text
scope.acquisition_single_arm
```

Service 的公开入口建议为：

```python
ScopeExtensionService.arm_single(
    *,
    error_check: ErrorCheckSpec | None = None,
    deadline: float | None = None,
) -> ScopeExtensionOperationResult

ScopeService.arm_single(
    *,
    error_check: ErrorCheckSpec | None = None,
    deadline: float | None = None,
) -> ScopeExtensionOperationResult
```

首版不新增 CLI 子命令。现有 `scope acquisition single` 保持「获取一条已证明完成的记录」语义，不能改为 arm-only。

### 返回模型

```python
ScopeSingleArmObservation = Literal[
    "nonterminal_observed",
    "terminal_unproven",
]


@dataclass(frozen=True, slots=True)
class ScopeAcquisitionSingleArmResult:
    original_state: ScopeAcquisitionRunState
    observed_state: ScopeAcquisitionRunState
    observation: ScopeSingleArmObservation
```

Core 必须验证：

```python
result.original_state == baseline.snapshot.run_state
result.observed_state.trigger_mode == "single"
```

`observation="nonterminal_observed"` 时，`observed_state.phase` 只能是：

```text
ready | arming | waiting | acquiring
```

该结果表示设备已在本次请求后报告 SINGLE 的非终态。它仍不是「新波形已产生」。

`observation="terminal_unproven"` 时，`observed_state.phase` 只能是：

```text
stopped | complete
```

该结果表示 SINGLE 命令已成功发送，且设备仍报告 SINGLE trigger mode，但首次可见状态已经终止。它不表示本次请求已经触发、完成，或产生了新记录。调用方不得据此调用 capture 或给波形附加新鲜性结论。

任何 `unknown`、非 SINGLE trigger mode、模型类型错误、写入结果不确定或读回失败都必须失败并进入 recovery；不得用 `terminal_unproven` 吸收这些错误。

### Driver Protocol 与 descriptor gate

新增独立 Protocol：

```python
@runtime_checkable
class ScopeAcquisitionSingleArmDriver(
    ScopeAcquisitionRunStateDriver,
    ScopeAcquisitionControlRecoveryDriver,
    Protocol,
):
    def arm_single(
        self,
        *,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeAcquisitionSingleArmResult: ...
```

`SCOPE_CAPABILITY_METHODS` 的新条目应为：

```python
"scope.acquisition_single_arm": (
    "get_acquisition_run_state",
    "arm_single",
    "snapshot_acquisition_control",
    "restore_acquisition_control",
    "verify_acquisition_control_restored",
)
```

它只依赖 `scope.acquisition_run_state`，并要求 `scope_extensions.acquisition_control_profile`。它不得依赖 `scope.acquisition_control`：后者要求 `start_continuous()`、`stop_acquisition()` 和完成式 `acquire_single()`，会迫使 arm-only 驱动错误声明完整 control capability。

`ScopeAcquisitionControlProfile` 已包含 SINGLE arm 语义和 recovery 的静态事实，本 RFC 复用该 profile，不新建第二套 acquisition recovery 配置。

## 事务与恢复规则

Core 应复用现有 acquisition baseline、operation context、access guard 和 recovery 结构：

1. preflight 读取 identity 与 acquisition baseline；原始 phase 仅接受 `stopped`、`ready` 或 `complete`；
2. main phase 调用 `driver.arm_single(baseline=...)`；
3. 成功时消费 baseline，不恢复设备状态；
4. main、after-error、模型验证或 query-back 失败时，执行 STOP、trigger/acquisition 恢复和新鲜验证；
5. recovery verification 仍要求最终 phase 为 stopped，并逐项比较 trigger 与 acquisition token；
6. session 为 poisoned 时不得继续恢复 I/O。

建议的 operation metadata：

```python
_scope_operation(
    "scope.acquisition_single_arm",
    required_capabilities=(
        "scope.acquisition_single_arm",
        "scope.acquisition_run_state",
    ),
    effect="acquire",
    timeout_ms=SCOPE_ACQUISITION_OPERATION_TIMEOUT_MS,
    changed_fields=(
        "scope.run_state",
        "scope.trigger",
        "scope.acquisition",
        "scope.error_queue",
    ),
    restore_coverage="failure-cleanup-only",
    verification_fields=("scope.trigger", "scope.acquisition"),
    postcondition_fields=("scope.run_state", "scope.trigger"),
    cleanup_verification_fields=(
        "scope.run_state",
        "scope.trigger",
        "scope.acquisition",
    ),
    risk_flags=("trigger", "acquisition_state", "recovery_required"),
    error_check_minimum="disabled",
)
```

这里的 postcondition 只表示 SINGLE 请求后的状态观察，不表示完成或数据新鲜性。

## MSO8104 适配方式

Core 接受接口后，MSO8104 driver 可按以下顺序实现 `arm_single()`：

1. 使用 Core 提供的 baseline；
2. 发送 `:SINGle`，不重放；
3. 查询 `:TRIGger:SWEep?`，要求 `SING`；
4. 查询 `:TRIGger:STATus?`；
5. `WAIT/RUN` 映射为 `nonterminal_observed`；`STOP` 映射为 `terminal_unproven`；`TD` 或未知值失败并 recovery。

该实现不查询 `*OPC?`，不读取 waveform，也不声明 `scope.acquisition_control`、`scope.capture_waveform` 或 `scope.capture_waveforms`。

## 兼容性

- 不修改 `scope.acquisition_control` 的 required method 集；
- 不修改 `ScopeAcquisitionCompletion` 的终态与 proof 规则；
- 旧 Core 遇到声明新 capability 的插件，必须在 factory 和第一次仪器 I/O 前拒绝；
- 新 Core 与旧插件保持现状；
- 插件只有在 Core 发布该 capability 后，才提高最低 WaveBench 版本并声明它。

## 验收要求

Core 至少应覆盖：

- descriptor 缺 profile、缺 recovery 方法、缺 run-state capability 时的零 I/O 拒绝；
- 非终态与 terminal-unproven 两类合法结果；
- `unknown`、非 SINGLE trigger mode 与非法 phase 的拒绝；
- 写入、query-back、after-error 与模型校验失败后的 restore/fresh verification；
- read-only access 拒绝；
- 既有 `scope.acquisition_control` 和完成式 `acquire_single()` 的兼容回归；
- arm-only 结果不能作为 capture 或 waveform freshness 的输入。

MSO8104 插件声明该 capability 前，还必须完成低压实机验收：验证 `WAIT` 的非终态结果、瞬时触发的 `terminal_unproven` 结果、失败 recovery 以及最终 source 双路 OFF、scope stopped、CH1/CH2 高阻。该验收不等同于完成式 SINGLE 或 capture 验收。

## 不采用的方案

- 把 `single` 加入 `ScopeContinuousAcquisitionRequest`：会改变连续采集的请求和 postcondition 语义；
- 向 `scope.acquisition_control` 追加 `arm_single()`：会破坏现有驱动的 capability validation；
- 让 `ScopeAcquisitionCompletion` 接受 unknown/armed：会把完成式 SINGLE 与请求 SINGLE 混为同一结果；
- 用 `*OPC?`、固定等待时间、首次 STOP 或当前波形变化作为完成证据；
- 让 arm-only 成功自动开放 waveform capture。
