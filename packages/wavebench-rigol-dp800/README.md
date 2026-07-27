# WaveBench RIGOL DP800 插件

[English](README_EN.md)

面向 RIGOL DP800 系列、当前以 DP832/DP832A 为公开兼容范围的 WaveBench 可执行仪器插件。

## 身份与开发基线

- distribution：`wavebench-rigol-dp800`
- canonical driver ID：`rigol.dp800`
- 开发基线：WaveBench `a3e13fd`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

本插件对齐 WaveBench `v0.8.0` release，不维护旧核心兼容矩阵，不能与 `v0.7.0` 配套运行，也不自动声明兼容未来 `0.9`。安装后，显式 canonical
ID `rigol.dp800` 选择外置实现；短 alias `dp800` 始终选择 WaveBench 内建 fallback。
卸载插件后，canonical ID 也回退内建实现。

## 能力

- `*IDN?`、错误队列；
- 通道设置值、输出状态、CV/CC 模式和电压/电流/功率测量；
- 电压、电流限值设置；
- 显式输出开关；
- OVP/OCP 阈值、启用状态和触发状态。

插件只负责 DP800 厂商 SCPI、解析和读回。WaveBench 核心继续负责安全上限、保护阈值与
设定值关系、输出开启前检查、Service、run plan 和实验级状态恢复。写命令失败不盲目重试。

## 配置示例

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.50::INSTR"

[safety_limits]
max_power_voltage_v = 5.0
max_power_current_limit_a = 0.2

[power]
driver = "rigol.dp800"
default_channel = 1
check_errors = true
settle_ms_after_set = 2000
settle_ms_after_output = 500
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 验收状态

0.3.0 完成 M2 现有写路径事务化：同一驱动实例的全部 transport I/O 使用统一可重入锁；
`APPLy`、输出和 OVP/OCP 写入均保存写前快照、逐步回读，并在失败时执行保守恢复。写命令
结果不明、恢复无法确认或出现新 trip 时，当前实例锁停后续配置写；输出失败统一收敛到 OFF，
保护恢复不发送 `CLEAR`。回读比较按 DP832/DP832A 手册分辨率使用半 LSB 容差。
2026-07-27 已在 DP832A CH1 完成不同目标值的正常回读/恢复和空载 ON→OFF，并通过受控
故障注入验收首次输出写结果不明、保护事务第二/第三写失败、`APPLy` 回读不一致和
`APPLy` 恢复结果不明；每轮均在独立会话复核最终状态。该证据只覆盖 DP832A 的协议和
恢复语义，不代表其他型号、带载瞬态或测量准确度验收。

0.2.0 完成 M1 只读路径收紧：首次通道访问通过 `*IDN?` 识别受支持型号和通道数；
`APPLy?`、`MEASure:ALL?` 与 OVP/OCP 阈值拒绝非有限数；输出、模式、保护使能和 trip
使用严格枚举；聚合快照任一查询失败即整体失败。2026-07-27 在 DP832A 三个通道完成
31 条查询、零写入的实机验收，最终三个输出均为 OFF。该证据不外推到其他型号，也不代表
测量准确度验收。驱动可识别 DP811/821/831/832 及 A 型通道数并 fail closed，但在对应写路径
逐型号验收前，公开兼容范围不扩大到 DP811/821/831。

0.1.0 已于 2026-07-24 完成真实 wheel 的受控 DP832A LAN 验收：受管安装、healthy/load、
canonical 与短 alias 路由、三通道只读状态和保护快照、CH1 保守电压/限流写入、OVP/OCP
写入与读回、空载输出 ON/OFF，以及卸载 fallback、重新安装均通过。写入前保存了三通道
状态；验收结束后在独立会话逐字段确认三个通道均恢复到原快照、输出为 OFF，错误队列为空。
验收未修改真实 `wavebench.toml`，未提交真实地址、序列号、快照、测量值或命令日志。

编程手册命令域、当前公开 API、证据等级、未覆盖项和默认拒绝项见
[DP800 编程手册功能覆盖矩阵](doc/DP800_COVERAGE_MATRIX.md)；逐阶段的目标、精确指令、
安全边界和验收门槛见 [DP800 指令覆盖开发里程碑](doc/DP800_COVERAGE_MILESTONES.md)。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dp800/tests
python -m ruff check packages/wavebench-rigol-dp800
python -m wavebench plugin package check packages/wavebench-rigol-dp800
```

真实地址、序列号、设定值快照、测量值和命令日志不得提交。本插件采用
[MIT License](LICENSE)。

## 来源

0.1.0 从 WaveBench 主仓库 `a3e13fd` 的内建 DP800 协议实现迁移，只把厂商驱动、
descriptor、entry point 和 FakeTransport 测试外置。
