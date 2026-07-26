# WaveBench RIGOL DM3000 插件

[English](README_EN.md)

面向 RIGOL DM3000/DM3058 数字万用表的 WaveBench 可执行仪器插件。本包仅支持经
PyVISA 访问的 LAN/VXI-11 连接。

## 身份与迁移边界

- distribution：`wavebench-rigol-dm3000`
- canonical driver ID：`rigol.dm3000`
- WaveBench：`>=0.8.9,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`（LAN-only）
- VISA resource scheme：`TCPIP`；拒绝 `ASRL`、`USB` 和 `GPIB`

当前包面向 WaveBench `v0.8.9` release，不自动声明兼容未来 `0.9`。

本插件不声明 alias。安装后，显式 canonical ID `rigol.dm3000` 选择外置 LAN 实现；
短 alias `dm3000` 和 `dm3058` 始终选择 WaveBench 内建 fallback，继续保留 serial 与
pyvisa 双 backend。卸载插件后，canonical ID 也回退到内建实现。

若 canonical ID 配置了 `backend = "serial"`，或给 `lan` / `visa` / `pyvisa` backend
提供 `ASRL`、`USB`、`GPIB` 等非 TCPIP VISA resource，WaveBench 都会在打开 transport
前明确拒绝。需要 RS-232 时应显式使用短 alias。

## 能力

- `dmm.idn`：查询 `*IDN?`；
- `dmm.read`：读取 DCV、ACV、DCI、ACI、二线/四线电阻、频率、周期、通断、二极管和
  电容；
- `dmm.function_status`：读取并规范化当前测量功能；
- `dmm.set_function`：切换测量功能并回读确认；
- `dmm.measurement_profile`：只读当前功能、离散量程码和 DCV 输入阻抗；
- `dmm.set_voltage_range`：仅为当前已激活的 DCV/ACV 设置 `0..4` 离散档位码并回读；
- `dmm.set_dcv_impedance`：仅在 DCV 下设置 `10M`/`10G` 并回读，其中 `10G` 只允许档位码 `0..2`。

`wavebench dmm profile` 不切换功能、不写量程、不读取错误队列。手册中的档位码 `0`
表示最小量程，不是自动量程；仪器没有对应的自动/手动只读查询，因此
`auto_range=n/a`。通断和二极管没有可验收的量程查询，相应字段也返回 `n/a`。

配置命令不会隐式切换测量功能。范围写入失败时会尝试恢复原档位；由于手册说明任何范围
写入都会把测量方式切到手动，失败路径即使恢复了档位也无法证明原自动/手动方式已恢复，
因此该实例会锁停后续配置写入。阻抗写入失败时同样执行恢复；首写结果不明或恢复失败也会
锁停。CLI 入口为 `wavebench dmm range set dcv|acv 0..4` 和
`wavebench dmm impedance set 10M|10G`。

插件复用 WaveBench 公共 `DmmReading`、`DmmDriver` 和 `DmmService` 契约。Service 继续
负责会话生命周期和读取前等待；插件只包含厂商 SCPI 协议与 descriptor。

厂商编程手册各命令域、当前七项 capability、逐测量类型离线/实机证据和默认拒绝的
高风险操作见 [DM3000 功能覆盖矩阵](doc/DM3000_COVERAGE_MATRIX.md)。本地厂商手册保存在
被忽略的 `doc/vendor-local/`，不进入发行包。

分阶段可实施能力、精确实机命令清单、协议验收口径及 2026-07-26 的通过/失败边界见
[DM3000 功能覆盖里程碑](doc/DM3000_COVERAGE_MILESTONES.md)。诊断探针不等于公开 capability，
本轮也不构成测量准确度或校准验收。

## 配置示例

示例使用 RFC 5737 文档地址，不是实验室真实地址：

```toml
[dmm]
driver = "rigol.dm3000"
backend = "lan"
resource = "TCPIP::192.0.2.40::INSTR"
timeout_ms = 3000
settle_ms_before_read = 0
settle_ms_after_function_change = 500
```

## 安全与验收边界

descriptor 导入不连接仪器。factory 只通过 `DriverContext` 打开当前配置的一个 transport。
默认测试不扫描资源、不连接仪器，也不会发送真实 SCPI。

2026-07-24 已完成外置 wheel 的第三批 LAN 验收：受管安装与 healthy/load、canonical
与短 alias 路由、20/20 DCV 有限值读取、当前功能查询、跨电压功能切换与原状态恢复、
受管卸载后的内建 fallback，以及重装后的 canonical IDN/DCV smoke 均通过。验收未修改
真实 `wavebench.toml`，未提交真实地址、序列号、读数或命令日志。RS-232 不属于此外置
包边界，继续由短 alias 对应的内建实现承载。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dm3000/tests
python -m ruff check packages/wavebench-rigol-dm3000
python -m wavebench plugin package check packages/wavebench-rigol-dm3000
python -m wavebench plugin install packages/wavebench-rigol-dm3000 --dry-run
```

真实仪器地址、序列号、读数、截图和命令日志不得提交。

## 来源与许可证

0.1.0 从 WaveBench 内建 DM3000/DM3058 协议实现迁移而来，保留原有 SCPI、解析与异常
语义。插件采用 [MIT License](LICENSE)。

0.2.0 增加只读当前测量 profile，不改变仪器配置。

0.3.0 增加功能门控、回读和失败恢复的 DCV/ACV 档位与 DCV 输入阻抗设置，并纠正
`range_code=0` 被误标为自动量程的问题。
