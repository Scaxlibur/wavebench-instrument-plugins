# WaveBench 核心 RFC：SDS3000 影响评估

[English](WAVEBENCH_CORE_RFC_EN.md)

> 状态：`Draft / Needs revision`
> 修订：`R1`
> 核心基线：WaveBench `0.8.22`
> API 状态：transport/session R1 已冻结；typed scope 未冻结
> 核心实现：`M1–M7 implemented-unreleased`（核心开发分支）

## 结论

SDS3054 插件的 M0–M8 功能已完成，插件侧 P0 安全加固仍待处理。WaveBench 核心的 transport replay/session R1 已在开发分支完成 M1–M7，但尚未发布；插件当前不能把该分支当作运行时依赖。当前声明的身份、错误寄存器、通道耦合、波形读取、单通道采集和同次 acquisition 多通道采集，不以本 RFC 的新接口为前提。VICP 文本与二进制波形已通过现有 `PyVisaTransport`、`PyVICP` 和 `query_bin_block()` 实机验证；这些结果不表示插件已经完成结构化异常迁移或共享 session health 采用。

本文件继续作为插件影响评估和采用门槛，不是 typed scope 的公共 API 规范。首稿把只读状态、通用 patch 和部分状态 v2 放得过近；R1 已将 transport/session 基础问题升为 P0，并把通用写入与 `ScopeSnapshotV2` 延后。核心 transport/session RFC 已接受并在开发分支实现，typed scope RFC 仍须独立冻结；插件只有在包含 R1 的核心版本发布后才能进入采用阶段。

机器可读版本见 [`wavebench-core-rfc.json`](wavebench-core-rfc.json)。本插件分支不修改 WaveBench 核心，也不提前依赖未发布接口。

## 阶段标记

插件里程碑和 RFC 修订使用不同编号，避免把插件完成状态误写成核心 API 已冻结：

| 对象 | 当前状态 | 含义 |
| --- | --- | --- |
| SDS3000 插件 | `M8-functional-complete` | 当前 6 项 capability 已通过既定离线与实机门禁；P0 安全加固待处理 |
| 本插件影响评估 | `R1-draft-needs-revision` | typed scope 提案仍可修订；核心 transport/session R1 以独立 Accepted RFC 为准 |
| WaveBench 核心实现 | `M1–M7-implemented-unreleased` | 核心开发分支已完成离线实现，但尚未发布；插件最低版本保持不变 |

## 规范拆分与当前状态

本影响评估把公共合同拆为两份独立规范。transport/session RFC 已完成冻结和开发分支实现；typed scope RFC 仍是 P1 编码的前置条件：

| 独立规范 | 必须冻结的内容 | 进入条件 |
| --- | --- | --- |
| transport replay/session RFC | 现有 `query()` 的默认策略、旧调用迁移清单、结构化传输错误、命令发送次数、部分响应、通信失步、session health 所有者、恢复授权、状态验证范围，以及 backend 不支持 `read_continuation_only` 时的失败行为 | 已完成核心冻结与开发分支离线实现；插件采用仍等待正式发布 |
| typed scope state RFC | 精确字段、`Protocol` 签名、静态与运行时字段支持、`OperationSpec`、Service/CLI/run plan 消费矩阵、v1 共存优先级、错误包络和三厂商映射 | 任何 P1 capability 冻结前 |

transport RFC 必须明确区分源码兼容与可观察行为兼容。把消费型读取从自动重试迁移到 `no_replay`，以及让 poisoned session 在 `on_failure=continue` 下停止后续仪器 I/O，都会改变可观察行为，不能笼统表述为「全部增量兼容」。

transport RFC 还必须冻结三个 session 合同：唯一权威 health 状态由哪个共享对象持有及其生命周期；`uncertain` 状态下哪个事务协调者可以在持锁条件下执行插件声明的有界恢复与验证；退出 `uncertain` 或重连后需要验证通信同步、身份连续性、受影响字段闭包和插件声明不变量中的哪些内容。普通 Service 调用不能获得恢复授权，也不能把未验证配置视为健康配置。

## 已确认的核心事实

| 接口或模型 | 当前结论 | 后续处理 |
| --- | --- | --- |
| `InstrumentTransport.query_bin_block()` | 当前 SDS3054 二进制路径足够，失败时不在同一 session 重放 | 保留不可重放语义并纳入统一 transport contract |
| `PyVisaTransport.query()` / `query_opc()` | 核心开发分支已要求显式 replay policy，未声明调用默认 `no_replay` | 插件在核心正式发布后迁移读后清除和 acquisition-bound `*OPC?`，并保留结构化异常 |
| `OperationSpec.effect=acquire` | 已能要求 `read_write`，无需为访问控制新增 effect；核心 M7 已补 capture/fetch 字段闭包、验证字段和恢复覆盖 | 插件采用 R1 时核对 SDS3000 实际临时设置与核心字段闭包，并补故障注入断言 |
| `ScopeStatusSummary` | 已能返回 IDN、coupling 和缺失能力 | 优先复用现有部分状态路径，不急于增加大而泛的 snapshot v2 |
| `PyVisaTransport` + `PyVICP` | 已满足当前 VICP 文本和二进制连接；核心 R1 不新增 SDS3000 专用后端 | 插件只需完成调用点分类和结构化异常采用，不改变 VICP 传输实现 |

## P0-1：不可重放查询契约

### 问题

R1 实施前，`InstrumentTransport` 没有 replay policy 或统一的 `query_once()` 契约。核心开发分支现在已冻结并实现显式 `replay` 关键字、默认 `no_replay` 和结构化传输错误；SDS3000 的 `CMR?`、`EXR?`、`DDR?` 仍需在插件采用阶段迁移并验证异常优先级。

R1 实施前，`RsInstrumentTransport` 和 `SerialTransport` 没有相同的显式自动重试；核心开发分支现在已提供跨 backend 的 replay contract，插件仍需在正式发布后完成采用。`GuardedAuditedTransport` 的健康门禁由核心负责，插件不能绕过。

### 最低行为契约

R1 不冻结最终方法名，但核心实现至少需要三类明确策略：

```text
safe_to_replay
no_replay
read_continuation_only
```

- `safe_to_replay`：只有调用方明确声明查询可重发时使用；transport 不解析 SCPI 文本推断安全性。
- `no_replay`：命令最多发送一次。超时、部分响应或结果不明确后不得再次发送命令。
- `read_continuation_only`：命令已经发送后，可以继续读取同一响应，但不得重新发送命令。

`query_once()` 可以作为便捷入口，但不能代替底层契约。所有后端都必须能证明命令发送次数、是否只继续读取、是否出现部分响应，以及通信状态是否仍可信。

以下调用默认使用 `no_replay`：

- 读后清除寄存器；
- 与一次 acquisition 绑定的 `*OPC?`；
- 已接收任意响应字节的请求；
- transport 无法证明重发安全的状态读取。

独立状态轮询是否允许重发，由上层 operation contract 明确声明，不能把所有 `*OPC?` 场景混成同一种行为。

### P0 退出门（核心已完成；插件采用仍待发布门）

- PyVISA、RsInstrument、Serial、`GuardedAuditedTransport` 和 FakeTransport 使用同一 replay contract。
- `no_replay` 故障注入测试证明命令最多发送一次。
- `read_continuation_only` 测试证明可以继续读当前响应，但不会再次写命令。
- telemetry 记录 replay policy、部分响应和不确定状态，不记录敏感 payload。
- SDS3000 的 `CMR?`、`EXR?`、`DDR?` 只有在核心原语发布后才迁移；迁移前插件保持当前最低版本和旧调用语法。
- 插件 `_acquire_once`、`query_opc()` 包装和临时恢复 contextmanager 必须原样保留 `TransportIOError` / `SessionHealthError`，不得降级成普通超时或继续发送第二条恢复命令。

## P0-2：共享 session 健康状态与锁存

### 状态模型

```text
healthy -> uncertain -> poisoned -> closed
```

该状态轴表示通信 session 是否可信；仪器配置是否已经验证使用独立的 `verified/unverified` 标记。新建或重连成功后，通信 session 可以是 `healthy`，但配置必须从 `unverified` 开始，只有显式只读基线复核通过后才能成为 `verified`。

允许跳过中间状态。写入结果未知但 transport 仍能证明通信同步时，session 进入 `uncertain`，仅允许有界恢复与验证；通信可能失步时直接进入 `poisoned`。`uncertain` 只有在通信仍同步且原配置恢复并回读验证通过后才能回到 `healthy`。`poisoned` 在原 session 内不可恢复。

| 阶段 | 结果 | session 行为 |
| --- | --- | --- |
| 预检拒绝 | 尚未发生 I/O | 保持 `healthy` |
| 新建或重连 | 通信通道重新建立 | `healthy + unverified`；只允许执行显式基线复核，不能假定仪器配置已恢复 |
| 写入结果未知 | 设备可能已经改变 | 通信同步可证明时进入 `uncertain`；否则立即 `poisoned` |
| 写后回读失败 | 当前值无法证明 | 进入 `uncertain`；只允许恢复与验证 I/O |
| 恢复失败 | 原状态未知 | `poisoned` |
| 恢复成功 | 通信同步且原状态经容差验证 | 从 `uncertain` 回到 `healthy + verified`，记录实际量化值 |
| close | session 不再可用 | `closed` |

### 责任边界

- 核心负责：replay policy、统一错误分类、共享 session health、操作前门禁和 `on_failure=continue` 的停止规则。
- 插件负责：受影响字段闭包、快照内容、恢复顺序、厂商合法组合和量化容差。
- transport 负责：命令是否发送、响应是否部分到达、通信通道是否可能失步。

核心开发分支已把锁存放在共享 `InstrumentSessionState`，不能只存在于临时 `ScopeService` 对象。run plan 会复用同一 scope session；当某一步标记 `on_failure=continue` 时，poisoned session 上的全部后续仪器操作都必须在 transport I/O 前拒绝。只允许本地审计、关闭旧 session 和建立新 session 等生命周期动作；重新创建 Service 不能清除锁存。插件在采用 R1 时必须覆盖这一门禁，而不是在 driver 内部自行重置 health。

### 需要区分的错误

- 预检或参数错误：零 I/O，session 健康；
- 写入失败且确认未发送：操作失败，session 可继续；
- 写入结果未知且通信仍同步：session uncertain，只允许恢复与验证；
- 通信失步或无法证明同步：session poisoned；
- 回读不一致：事务失败，尝试恢复；
- 恢复失败：`StateDriftError` 加 session poisoned；
- poisoned session 上的后续操作：稳定的 session-health 错误，零 I/O。

## P1-1：类型化只读状态

P0 完成后，第一批 scope capability 只提供读取：

```text
scope.analog_channel_state
scope.timebase_state
scope.edge_trigger_state
```

每项能力都必须同时定义：

1. 公共 `Protocol` 和不可变 typed model；
2. `OperationSpec`、effect、风险、timeout 和 `changed_fields`；
3. `ScopeService` 消费入口；
4. 稳定 JSON 表示和 strict 行为；
5. capability 与 v1 接口共存时的优先级。

仅有 capability 字符串和 driver 方法不构成可用的核心接口。CLI 与 run plan 可以分阶段接入，但 RFC 必须明确首版包含哪些消费入口，不能声明一个核心没有调用路径的能力。

### 字段元数据

`supported_fields` 不能表达「可读但不可写」。首版至少需要以下字段级信息：

```text
readable
writable
type
unit
enum
minimum
maximum
quantization
```

patch 使用 `UNSET` 表示「保持不变」。`None` 只有在具体字段定义了「自动」「清除」或其他显式语义时才允许使用，不能兼任「未知」或「未提供」。序列化时省略 `UNSET`，不得把它写成 JSON `null`。

字段 availability 只区分成功返回中的设备状态：

```text
unsupported
supported_but_not_readable
stale_or_unknown
valid_value
```

`query_failed` 不是 availability 成员。查询失败必须通过结构化 operation error 包络返回，不能伪装成设备不支持，也不能静默返回成功的部分状态。

### 模拟输入复合语义

SDS3000 的 `A1M/D1M/D50/GND` 同时编码 coupling 和 termination，不能视为两个完全独立的可写字段。首版状态模型可以返回归一化的 coupling、termination 和原始组合的类型化结果，但 termination 保持只读，并定义合法组合与不可表示状态。

## P1-2：采集状态轴候选

`scope.acquisition_run_state` 目前只是候选名称，不进入实施队列，也不冻结 `run/stop/wait/armed` 单枚举。连续运行状态与触发阶段不是同一语义轴，至少需要分别评估：

- execution state：running、stopped 和 unknown；
- trigger phase：idle、waiting、armed、triggered 和 unknown；
- trigger mode：auto、normal、single 和 unknown。

这些名称和取值仍是设计输入，不是公共 API。average、segmented、option inventory 和历史帧数量继续使用独立能力，不进入同一个状态袋。

| 厂商 | 当前证据 | 可映射内容 | 未解决问题 |
| --- | --- | --- | --- |
| SDS3000 | `TRMD?` 返回 `AUTO/NORM/SINGLE/STOP` | `STOP` 只能证明 stopped；其余 token 更接近 trigger mode | 无法区分 running、waiting 与 armed；`SEQ` 仍是 `firmware-unverified`，不得作为证据 |
| DS1000Z | 当前驱动只有 `:STOP`、`:SINGle` 和 `*OPC?` 同步 | 只有动作与完成同步，没有只读状态映射 | 需要核对手册并增加受控只读证据，不能从最近一次写命令推断当前状态 |
| RTM2000 | `STATUS:OPERation:CONDITION?` bit 3 和 `TRIGger:A:MODE?` | 可证明 waiting-for-trigger 与已支持的 trigger mode 子集 | 当前驱动没有通用 running/stopped 读回 |

typed scope RFC 必须给出三厂商逐值映射、不可映射值、静态支持与运行时不可用规则。查询失败仍是 operation error；`unknown` 只表示设备成功返回但无法映射。至少一个状态轴在三家均有可验证读回前，不冻结公共 capability。

## P2：窄范围配置 patch

只有 P0、typed read-only state、核心消费入口和合同测试完成后，才评审写入能力：

```text
scope.analog_channel_configure
scope.timebase_configure
```

第一版候选字段仅包括：

- `enabled`；
- `scale_v_per_div`；
- `offset_v`；
- `scale_s_per_div`；
- `position_s`。

以下字段不进入第一版：

- termination；
- coupling 与 termination 的复合写入；
- `scope.edge_trigger_configure`；
- 任意厂商字段或厂商 token。

空 patch、unsupported/read-only 字段、非法值和字段冲突必须在 I/O 前拒绝。成功事务执行写前快照、写入、量化回读；失败事务按插件声明逆序恢复，并由核心维护 session health。

审计至少区分：

```text
declared_changed_fields
observed_changed_fields
restored_fields
state_uncertain
session_poisoned
```

`changed_fields` 表示「事务期间可能触碰的仪器字段」，不能只表示最终保留的变化。现有 `scope.capture`、`scope.capture_waveforms`、`scope.capture_multiple` 和 `scope.fetch_waveform` 也需要重新审计时基、垂直比例、trace、trigger mode 与波形传输状态。

## 终端阻抗安全边界

`read_write` 只表示访问策略允许写，不证明接线、电源输出、信号幅度和负载适合切换到 50 Ω。WaveBench 项目边界不允许普通自动化流程改变示波器输入阻抗，因此 R1 作出以下裁决：

- 首版公共状态只读 termination；
- 首版通用 patch 不包含 termination；
- 50 Ω → 高阻也不作为默认自动行为；
- 未来若增加独立能力，必须要求显式安全确认、零写入预检、信号源状态证明、写后独立回读、失败锁存和实机证据；
- 高阻 → 50 Ω 需要单独、更严格的风险评审，不能由普通 `read_write` 授权代替。

## `ScopeSnapshotV2` 与 acquisition status

### `ScopeSnapshotV2`

当前不冻结 `ScopeSnapshotV2`。现有 `ScopeStatusSummary` 已能返回 IDN、coupling 和缺失能力，足够为缺少完整 `scope.snapshot` 的驱动提供安全摘要。

若后续仍需 v2，必须使用封闭、版本化 component 类型和字段级 `Availability[T]`。不接受 `Mapping[str, typed_component]` 作为稳定公共类型，也不允许把运行时 `query_failed` 降级成普通 unavailable reason。

### `ScopeAcquisitionStatusV2`

当前方案拆分并延期。`scope.acquisition_run_state` 也不在 R1 中冻结；先由 typed scope RFC 解决 execution、trigger phase 与 trigger mode 的三厂商映射。average、segmented 和 option status 后续按独立 typed capability 设计。现有 v1 模型保持不变。

## 核心消费与兼容契约

新增 capability 至少需要：

- `Protocol` 与 typed model；
- `OperationSpec`、effect、风险、timeout、`changed_fields` 和恢复覆盖；
- `ScopeService` 方法；
- JSON 与错误包络；
- strict 行为和 v1/v2 优先级；
- CLI/run plan 是否首版支持的明确说明。

新增符号应保持源码层面的增量兼容：现有 `scope.channel_coupling`、capture 参数、v1 snapshot 和 acquisition status 不原地改型。核心 R1 已冻结 `query()` 默认 `no_replay`、结构化错误和 poisoned session 门禁；消费型读取迁移、`on_failure=continue` 后续 I/O 阻断等都是有意的可观察行为变化。插件仍须在采用阶段补齐调用点迁移、版本说明和回归测试，只有核心发布新版本后才提高最低 WaveBench 版本。

## 发布与版本门

当前插件同时使用三道版本门：wheel metadata 声明 `wavebench>=0.8.22,<0.9`；descriptor 声明 `wavebench_min_version="0.8.22"` 与 `wavebench_max_version="0.9.0"`；descriptor 显式声明 `api_version="wavebench.instrument.v2"`。三者分别约束安装解析、运行时核心版本和可执行插件 API，不能互相替代。

插件采用 P0 核心能力前必须满足：

1. P0 已进入正式 WaveBench 版本，不能依赖未发布提交；
2. wheel 下限与 descriptor 下限在同一提交中提高到首个包含 P0 的核心版本，并重新评审上限；
3. 只有 `wavebench.instrument.v2` 合同保持兼容时才能保留当前 `api_version`；若可执行插件合同不兼容，核心常量与插件 descriptor 必须使用新的 API 版本；
4. registry 必须在 driver factory 和 transport I/O 前拒绝 API 或核心版本不匹配；
5. 隔离 wheel 安装测试必须同时核对 `Requires-Dist`、descriptor 版本范围、`api_version` 和 entry point。

本 R1 不提高任何版本门。

### 插件 P0 采用清单

核心 R1 目前是「开发分支已实现、正式版本未发布」。插件在提高版本门之前必须完成以下动作：

1. 等待首个包含 R1 的 WaveBench 正式版本，并在同一提交中提高 wheel `Requires-Dist`、descriptor `wavebench_min_version`，重新评审 `wavebench_max_version` 和 `api_version`。
2. 将 driver 中所有 transport query 显式标为 `no_replay` 或经专项审计批准的 `safe_to_replay`；`CMR?`、`EXR?`、`DDR?` 和 acquisition-bound `*OPC?` 固定使用 `no_replay`。
3. 在 `_acquire_once`、OPC 等待和临时恢复路径中原样传播 `TransportIOError`、`SessionHealthError`；结构化异常发生后不执行未经授权的第二次恢复/验证 I/O。
4. 增加故障注入测试，断言发送次数、`uncertain`/`poisoned` 转移、`on_failure=continue` 的零二次 I/O，以及关闭/重连后的新 `epoch_id`。
5. 通过隔离 wheel、descriptor、entry point 和 API 版本联合测试后，才把本 RFC 的插件状态改为 adopted。

## 验收测试矩阵

当前插件中的 `test_core_rfc.py` 只验证本文件与 JSON 的结构，不证明核心契约已经实现。真实行为测试必须进入 WaveBench 核心仓库。

| 层级 | 必测内容 | 默认 CI 是否连接仪器 |
| --- | --- | --- |
| transport contract | 三种 replay policy、部分响应、单次发送、各 backend 与 Guarded 一致性 | 否 |
| session transaction | 预检零 I/O、unknown write outcome 在通信同步可证明时进入 uncertain、通信失步或无法证明同步时进入 poisoned、回读失败、逆序恢复、共享锁存、`on_failure=continue` | 否 |
| typed read-only state | read-only/unsupported、availability、结构化查询错误、termination patch 在 I/O 前拒绝 | 否 |
| Service / CLI / run plan | capability 消费、OperationSpec、JSON、strict、仅现有 v1 回归和 session-health 诊断 | 否 |
| plugin version gate | wheel `Requires-Dist`、descriptor min/max、`api_version`、entry point 和零 I/O 拒绝 | 否 |
| 三厂商 fake driver | 只测试 typed scope RFC 已冻结且有证据的逐值映射，不补造公共语义 | 否 |
| opt-in hardware | 已发布 P0/P1 操作的真实 transport、批准仪器上的只读状态映射和重连后的配置复核 | 是 |

termination 写入和 `ScopeSnapshotV2` 的安全门、v1/v2 共存及实机验收移入各自未来独立 RFC，不作为 R1 当前验收项。P2 patch 的空 patch、非法值、字段冲突、量化回读与恢复矩阵也在 P2 重新进入实施范围时单独冻结。

## 跨厂商适用性

| 公共问题 | SDS3000 | DS1000Z | RTM2000 |
| --- | --- | --- | --- |
| 不可重放状态/同步查询 | 读后清除寄存器与 acquisition-bound `*OPC?` | 错误与采集同步查询需明确策略 | RsInstrument 后端同样需要公共契约 |
| 共享 session 锁存 | capture 会临时修改多类状态 | capture 内部 setter 可能失败 | 已有较完整恢复逻辑，但不是核心契约 |
| 只读通道/时基/触发状态 | 手册和实机已有部分证据 | 驱动已有耦合与设置路径 | 已有完整 snapshot，可作为合同基线 |
| 采集与触发状态轴 | `TRMD?` 混合 mode 与 stopped | 当前驱动没有只读状态 query | 可读 waiting 位与 trigger mode，但没有通用 run/stop 读回 |
| 窄范围 patch | VDIV/TDIV/OFST | vertical scale/time range | 现有 setter 和回读可作为参考 |

P0 基础设施适用于所有仪器类型，不是 SDS3000 专用接口；P1/P2 的 scope 能力至少有三个示波器系列的共同语义。

## 不修改或永久拒绝的项目

- 不新增 SDS3000 专用 VICP 核心后端；现有 PyVISA 路径配合插件依赖 `PyVICP` 已足够。
- 不替换现有 `query_bin_block()`；当前 SDS3054 二进制路径已经通过实机验收。
- 不因 SDS3000 增加 raw screenshot transport；`SCDP?` 返回状态而非图片 payload。
- 不允许 descriptor 加载时探测仪器或选件。
- 不原地放宽 v1 数据模型的必填字段。
- 永久拒绝任意 raw SCPI、任意 VBS、MAUI `app` 反射、调用方提供的恢复命令和绕过 identity/access/audit 的 transport 句柄。

## 建议实施顺序

1. 保留本文件作为插件影响评估，区分「M8 功能完成、插件 P0 采用待处理」、RFC R1 和「核心已实现但未发布」三类状态。
2. 核对已接受的 transport replay/session RFC、核心开发分支实现和稳定 reference 文档，不把未发布提交写入插件版本门。
3. 在核心正式发布后完成上面的插件 P0 采用清单和合同测试。
4. 核对核心 M7 已审计的 `scope.capture`、`scope.capture_waveforms`、`scope.capture_multiple` 和 `scope.fetch_waveform` `OperationSpec` 是否覆盖 SDS3000 的实际临时设置；差异必须在插件采用测试中显式记录。
5. 单独冻结 typed scope state RFC，明确 channel/timebase/edge-trigger 字段、核心消费矩阵、v1 优先级和三厂商映射。
6. 实现已冻结的类型化只读状态；采集状态轴继续收集三厂商证据，不预先承诺 `scope.acquisition_run_state`。
7. 只有 P0 核心正式发布且采用清单通过后，才同时提高 wheel/descriptor 版本门并复核 `api_version`。
8. 在安全证据充分后另立 RFC 评审窄范围 scale/offset/timebase patch。
9. 最后分别重新评审 termination 写入、通用触发写入和 snapshot v2。

前两项 P0 退出门全部通过前，不冻结任何通用 scope 写入 API。
