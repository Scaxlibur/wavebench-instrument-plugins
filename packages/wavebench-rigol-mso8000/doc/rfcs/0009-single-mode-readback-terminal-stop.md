# RFC-0009：已验证 SINGLE 模式下的即时 STOP 完成合同

状态：Core R1 已在当前开发分支实现；MSO8104 已完成受限实机验收

目标仓库：WaveBench Core

替代：已撤回的「SINGLE arm-only」草案。本文保留既有完成式
`scope.acquisition_control`，不新增 arm-only capability。

## 问题

现有 `scope.acquisition_control` 将连续启动、停止和完成式 SINGLE 采集放在同一 capability。这个边界是合理的：成功返回 SINGLE 结果意味着调用方可以把它当作本次操作完成，后续才可能读取本次采集的波形。因此，不能把任意一次 `STOP`、固定等待时间、`*OPC?` 或屏幕既有波形当作完成证据。

MSO8104 的 `:SINGle` 同时选择 SINGLE sweep 并 arm。手册说明，仪器在满足触发条件后采集一次并停止；`:TRIGger:SWEep?` 可读回 `SING`，`:TRIGger:STATus?` 则只报告 `TD/WAIT/RUN/AUTO/STOP`。在 LAN 轮询中，触发可能发生得足够快，以至于 arm 后的第一条状态查询已是 `STOP`。这不是失败，也不是连续采集的 `RUN` 语义。

现有 Core `state_transition` proof 要求先观察非终态再观察 `STOP`。它对无法读出记录 ID、采集计数或完成事件的仪器保持严格，但也拒绝了上述可被设备模式读回约束的即时终态路径。

MSO8104 的三份编程手册转换全文未发现可查询的新记录 ID、采集计数、记录世代、时间戳或可用采集完成事件：

- `:WAVeform:PREamble?` 的 count 是平均次数，不是采集记录计数；
- `:RECord:CURRent?` 是回放帧，且 record/replay 时 SINGLE 不适用；
- `:WAVeform:STATus?` 没有可用功能；
- `*ESR?`、`*STB?` 不提供采集事件语义。

两次 source 输出关闭的 SINGLE 探测还确认：`*OPC?` 返回成功后，独立状态读取仍可为 `WAIT`。因此 `*OPC?` 只表示命令处理完成，不能作为物理触发、采集完成或新波形证据。

## 决策

在不放宽默认状态迁移规则的前提下，为明确 opt-in 的设备增加一种完成 proof：

```text
single_mode_readback_then_stopped
```

它只在以下严格序列完整成立时表示 SINGLE 已完成：

```text
write SINGLE（不可重放）
        ↓
query-back trigger sweep == SINGLE
        ↓
第一条 acquisition-state query == STOP
```

该 proof 不是「首条状态恰好为 STOP」的泛化，也不是把 trigger-mode 字段由 driver 猜成 `single`。它要求设备模式 query-back 的显式回包，且回包必须发生在 SINGLE 写入之后、首条终态状态读取之前。

若 query-back 后先得到 `WAIT`，driver 继续轮询并沿用既有 `state_transition` proof；不使用本文的新 proof。对 MSO8104，query-back 后的 `TD` 仅在本次已确认的 SINGLE 上下文中保守表示为非终态 arming，后续必须读到 STOP；TD 本身不构成完成。`RUN`、`AUTO`、未知 token、错误或超时均不满足合同，必须 fail closed 并进入既有恢复路径。

## Core R1 实现模型

### Completion proof

扩展现有字面量：

```python
ScopeCompletionProof = Literal[
    "count_delta_with_epoch",
    "identity_delta",
    "state_transition",
    "single_mode_readback_then_stopped",
]
```

### Descriptor profile gate

在 `ScopeAcquisitionControlProfile` 的末尾增加兼容默认值：

```python
single_mode_readback_allows_terminal_stop: bool = False
```

Core 验证该字段为 `bool`。默认 `False` 保持所有既有仪器和 descriptor 的行为不变。MSO8104 在手册语义、driver conformance 与受控实机验收完成后设为 `True`。

该标志不替代 `single_arm_semantics`、计数/identity 语义或 failure restore order；它只授权一种额外的终态 proof。设备若未明确 opt-in，首条 `STOP` 仍按当前规则拒绝。

### Completion 的模式读回字段

在 `ScopeAcquisitionCompletion` 的末尾增加可选字段，以免改变现有位置参数：

```python
post_arm_trigger_mode: ScopeTriggerMode | None = None
```

模型构造时必须校验该字段为 `None` 或合法 `ScopeTriggerMode`。该字段表达 driver 在本次 SINGLE 写入之后实际读回的模式，不是由 `ScopeAcquisitionRunState.trigger_mode` 反推得到的推测值。

### 验证规则

`validate_acquisition_completion()` 对
`proof="single_mode_readback_then_stopped"` 必须额外要求：

1. `profile.single_mode_readback_allows_terminal_stop is True`；
2. `completion.post_arm_trigger_mode == "single"`；
3. `completion.state.phase == "stopped"`，且 `completion.state.trigger_mode == "single"`；
4. `completion.observed_states == (completion.state,)`；这明确表示首条状态读取已是 STOP；
5. `baseline_count`、`completed_count`、`baseline_identity`、`completed_identity` 均为 `None`；该 proof 不得伪装成 count 或 identity 证据；
6. 既有的 original-state、baseline-stage 与 atomic-arm baseline 一致性检查仍然全部通过。

新分支不要求 `state_transition`，也不检查 `transition_seen`。其余三种既有 proof 的验证逻辑完全不变；它们不需要填写 `post_arm_trigger_mode`。

Core 的模型无法仅凭 dataclass 证明 transport query 顺序。因此 driver conformance test 必须验证：SINGLE 写入后先执行 trigger-sweep query，确认 `SING` 后才执行第一条 trigger-status query。Core operation 继续使用 exclusive lease，避免同一受管会话内的控制操作交错；会话外的前面板/第三方写入不构成可免除 query-back 的理由。

## Driver 事务

完成式 `acquire_single()` 的适配顺序如下：

1. Core 照常建立 acquisition baseline、operation context 与 failure cleanup；
2. driver 发送不可重放的 SINGLE 写入；
3. driver 查询设备的 trigger sweep，并将明确 `SING` token 映射为 `post_arm_trigger_mode="single"`；
4. driver 查询第一条 acquisition state；
5. 若该状态是 `STOP`，按本文的新 proof 返回 completion；
6. 若该状态是 `WAIT` 或受限上下文中的 `TD`，继续在同一 deadline 内轮询，按既有 `state_transition` 返回 completion；
7. 任一模式读回不匹配、状态 token 不适用、after-error、deadline、transport 或模型错误，都执行既有 STOP、trigger/acquisition restore 与 fresh verification。

对于 MSO8104，第 3、4 步的命令序列为：

```text
:SINGle
:TRIGger:SWEep?
:TRIGger:STATus?
```

只有 sweep 回包为 `SING` 且第一条 status 回包为 `STOP` 时，才可构造本 proof。不得发送 `*OPC?`，不得借用 SINGLE 写入前读取的 STOP，也不得以 sleep 替代 query-back。

本文不改变完成后的设备状态：成功的 SINGLE 仍停在 SINGLE/STOP。失败恢复保持现有 failure-cleanup-only 合同。

## MSO8104 适配结果

Core 已实现该合同；MSO8104 插件已将 profile flag 设为 `True`、在 `acquire_single()` 内实现上述 trace，并声明 `scope.acquisition_control`。

该 control proof 本身不自动开放 capture、运行态 MAX/DMAX、平均采集或 record/replay。capture 需要独立证明波形新鲜性、完整 capture 事务及 13 字段恢复/新鲜验证。MSO8104 已另行完成受限 `DEF + BYTE` 单／多通道 capture 验收：capture 保持「非终态到 STOP」的严格保护，不接受本文的即时 STOP proof。

## 兼容性与拒绝行为

- 新 profile 字段默认为 `False`，旧 descriptor 构造不变；
- 新 completion 字段置于现有可选字段末尾，旧 driver 返回不变；
- 不新增 capability、Service 入口或 CLI 命令；现有 `scope.acquisition_control` 的 capability gate 保持不变；
- 缺少 profile opt-in、`post_arm_trigger_mode`、合法状态或精确单项 observed state 的任何一个条件时，Core 拒绝 completion 并启动既有恢复；
- `*OPC?` 成功、固定延时、单独 STOP、当前 waveform、preamble count、record frame、状态寄存器读数均不能满足本 proof。

## 已完成验收

Core R1 已覆盖以下模型与服务测试：

1. opt-in profile 与精确 legal completion 通过；
2. 默认 profile、`post_arm_trigger_mode != "single"`、终态非 STOP、state trigger mode 非 SINGLE、多个 observed state、任何 count/identity 字段非空均被拒绝；
3. 三种既有 proof 与所有既有 descriptor fixture 无行为变化；
4. Service 在新 proof 合法时返回成功，在模型/after-error/transport 失败时仍执行 failure restore 和 fresh verification；
5. capability validation、read-only access、poisoned session 与 exclusive lease 行为保持原有边界。

MSO8104 已完成以下低压实机验收：

1. `:SINGle → :TRIGger:SWEep? = SING → :TRIGger:STATus? = STOP` 的 terminal-proof 成功路径；
2. `WAIT → STOP` 与 `TD → STOP` 的状态迁移路径；
3. sweep/status 不匹配、超时和 transport 失败的离线恢复与 fresh verification；
4. 每轮结束后的 source 双路 OFF、scope STOP、CH1/CH2 high_z 复核；
5. 与 control 分开的 bounded `DEF + BYTE` 单／双通道 capture 新鲜性和 13 字段恢复验收。

## 不采用的方案

- 新增 arm-only capability：它只会把控制请求和完成式 SINGLE 分裂成两套语义，且不能满足当前需要的完成操作；
- 将任意首条 STOP 视为完成：无法区分命令前就已停止、模式不匹配、外部控制或读取错误；
- 用 `*OPC?`、固定延时、屏幕变化、preamble count 或 record frame 推断完成：它们没有本次物理触发/新记录的证明力；
- 把 `RUN` 作为 SINGLE 的必要中间态：MSO8104 的连续 NORMAL/AUTO 行为与 SINGLE 不同，SINGLE 的 WAIT 或即时 STOP 已有更精确的设备语义；
- 让控制 proof 自动开放 capture：控制完成与波形新鲜性、二进制读取和恢复覆盖是不同合同。
