# Conformance and hardware evidence

在修改 conformance manifest、实机验收 harness、证据升级规则、脱敏、恢复或安全写入时读取本页。本页不授权连接仪器。

## Evidence levels

根据 capability 风险与现有 Core 合同选择证据，不把所有包强制套进同一层级：

| 级别 | 证明内容 | 默认环境 |
| --- | --- | --- |
| 静态合同 | metadata、descriptor、profile 与 Core 类型一致 | 纯离线 |
| 离线行为 | FakeTransport、parser、失败和恢复请求符合合同 | 纯离线 |
| 查询证据 | 型号、固件、transport 下的只读行为 | 明确授权的实机只读 |
| 受控写入 | 输出、配置、触发或采集及其读回和恢复 | 明确授权的受控实机 |
| 量值证据 | 外部仪器观测、误差与适用条件 | 经确认接线和量程的实机 |

只有 Core 合同或当前包的 promotion gate 要求时才生成正式 conformance。Acceptance、诊断日志和历史记录各有用途，不能因为存在一份实机文件就提升 production capability。

## Before live work

实时操作必须另有明确授权，并服从 WaveBench Core 的安全与恢复规则。宿主提供 `$wavebench` 时同时加载；未提供时停止在离线阶段并报告依赖。开始前：

1. 确认目标型号、资源、固件、transport、当前接线、负载／终端和允许的写入范围。
2. 先完成静态、FakeTransport、包检查和 harness 离线测试。
3. 找到当前包已有的 evidence 工具、setup template、测试和记录格式；禁止临时拼接裸 SCPI 代替受审阅 harness。
4. 确认初始输出、保护、耦合、量程和 session 状态，并定义失败时立即停止的条件。
5. 明确哪些状态可恢复、哪些不可回读或不可恢复，以及最终必须验证的安全状态。

任何信息不清楚时停止在离线阶段，不猜测实验室资源或仪器状态。

## Harness contract

实机 harness 应把安全合同做成可离线测试的代码：

- setup 采用严格 schema，拒绝未知字段、越界值和示例占位符。
- 默认诊断模式不写入；写入模式需要显式开关和独立确认。
- 使用 WaveBench lease、session、driver 和 capability gate，不绕过为裸 transport 命令串。
- 在写前记录必要快照，并为每次 query、write、trigger、capture 设置硬上限。
- 不盲目重试。写入结果不明时停止后续操作，锁停受影响输出，并按 Core 合同请求恢复。
- 恢复后新建或重新确认 session，实际读回输出和关键状态；进程退出码不代表设备已安全。
- 即使证据序列化、审计或关闭失败，也优先执行确定性的安全停止路径。

离线测试必须覆盖初始状态拒绝、未知写入结果、恢复失败、额外 I/O、超限、脱敏和 session 关闭。

## Evidence privacy and scope

正式证据只保留审计所需最小信息，并限定：

- 插件 distribution 与版本、driver ID、descriptor digest 或既有 binding。
- 经脱敏的型号、固件范围与 transport 类别。
- capability、操作模式、条件、预期、观察结果和失败代码。
- harness 版本、时间和适用的 Core 合同版本。

禁止写入仓库或发行物：真实 IP、串口、VISA resource、序列号、账户与 token、未脱敏 IDN、原始波形、截图、完整 SCPI transcript 和本地文件路径。示例使用保留地址或明确的占位值。

文件权限、证据目录和保留策略按当前 harness 既有合同执行。某个包要求私有 `0600` 文件不代表所有 conformance manifest 都采用相同权限。

## Promotion gate

准备把实验证据用于 production capability 前逐项确认：

1. production driver 和 descriptor 已实现待验证合同，harness 没有临时扩充 descriptor 来伪造当前能力。
2. 证据与实际 wheel、descriptor 和 Core 版本绑定，digest 由既有工具生成并验证。
3. 适用型号、固件、transport、接线和限制足够具体，不外推到未验证系列。
4. 失败、恢复与最终状态都有证据，不只保存正常路径截图或日志。
5. 包内测试验证 manifest schema、脱敏、binding 和发行物包含范围。
6. 生成式目录从 production descriptor 得到 capability，而不是反向读取验收文档。

证据不足时准确保留为 Experimental、Historical、unsupported 或 unavailable，不复制整个开发过程到用户 Reference。

## Live completion report

实时交接必须写明：

- 实际访问的仪器类别、型号／固件范围与 transport 类别，不暴露私有标识。
- 执行的 read、write、trigger 或 capture 范围和计数上限。
- 初始状态、恢复动作、最终读回状态和不可恢复设置。
- 证据文件位置、脱敏结果、绑定状态和失败代码。
- 未运行、被拒绝或结果不明的步骤。

只要最终安全状态没有读回确认，就不能把验收报告为完整通过。
