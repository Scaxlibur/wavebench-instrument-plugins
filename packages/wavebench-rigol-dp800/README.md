# WaveBench RIGOL DP800 插件

[English](README_EN.md)

面向 RIGOL DP800、DP832 和 DP832A 可编程直流电源的 WaveBench 可执行仪器插件。

## 身份与 HEAD 基线

- distribution：`wavebench-rigol-dp800`
- canonical driver ID：`rigol.dp800`
- 开发基线：WaveBench `a3e13fd`
- Python：`>=3.11`
- transport backend：`pyvisa`

本插件只对齐 WaveBench 主仓库当前 HEAD，不维护旧核心兼容矩阵。安装后，显式 canonical
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

0.1.0 已于 2026-07-24 完成真实 wheel 的受控 DP832A LAN 验收：受管安装、healthy/load、
canonical 与短 alias 路由、三通道只读状态和保护快照、CH1 保守电压/限流写入、OVP/OCP
写入与读回、空载输出 ON/OFF，以及卸载 fallback、重新安装均通过。写入前保存了三通道
状态；验收结束后在独立会话逐字段确认三个通道均恢复到原快照、输出为 OFF，错误队列为空。
验收未修改真实 `wavebench.toml`，未提交真实地址、序列号、快照、测量值或命令日志。

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
