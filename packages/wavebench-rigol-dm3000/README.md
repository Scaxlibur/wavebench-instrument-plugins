# WaveBench RIGOL DM3000 插件

[English](README_EN.md)

面向 RIGOL DM3000/DM3058 数字万用表的 WaveBench 可执行仪器插件。本包仅支持经
PyVISA 访问的 LAN/VXI-11 连接。

## 身份与迁移边界

- distribution：`wavebench-rigol-dm3000`
- canonical driver ID：`rigol.dm3000`
- WaveBench：`>=0.7,<1`
- Python：`>=3.11`
- transport backend：`pyvisa`（LAN-only）
- VISA resource scheme：`TCPIP`；拒绝 `ASRL`、`USB` 和 `GPIB`

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
- `dmm.set_function`：切换测量功能并回读确认。

插件复用 WaveBench 公共 `DmmReading`、`DmmDriver` 和 `DmmService` 契约。Service 继续
负责会话生命周期和读取前等待；插件只包含厂商 SCPI 协议与 descriptor。

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

迁移前内建驱动已有 DM3058 LAN `*IDN?` 20/20 稳定查询和 DCV 实机读取证据。该证据只
作为迁移基线；外置 wheel 的独立安装/卸载和迁移后的 LAN 实机回归需单独通过后，才可
宣称第三批验收完成。

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
