# WaveBench RIGOL DS1000Z 插件

[English](README_EN.md)

面向四通道 RIGOL DS1104Z、DS1104Z Plus、DS1104Z-S Plus 和兼容 DS1000Z 系列的 WaveBench 可执行仪器插件。

## 身份与兼容范围

- distribution：`wavebench-rigol-ds1000z`
- canonical driver ID：`rigol.ds1000z`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件不声明 alias。WaveBench 内建的 `ds1104` / `ds1000z` 兼容 alias 仍选择内建 fallback；要显式选择本插件，请在配置中使用 `driver = "rigol.ds1000z"`。

## 能力

- `*IDN?` 和错误队列；
- CH1–CH4 coupling 查询和显式 autoscale；
- NORM/RAW/DMAX BYTE 波形读取；
- RAW 长记录按最多 250000 点分块；
- CH1–CH4 单通道采集，以及“一次 acquisition、一次 OPC、逐通道读取”的四通道采集；
- PNG 截图；
- 分块、总传输和转换 telemetry。

## 安全边界

插件只通过 WaveBench 提供的 `DriverContext` 打开当前配置的 transport。导入 descriptor 不连接仪器。Python 插件是可信代码，不是安全沙箱。

示例配置使用文档保留地址：

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.20::INSTR"

[scope]
driver = "rigol.ds1000z"
model_hint = "DS1104Z Plus"
default_channel = 1
check_errors = true

[scope.options]
max_chunk_points = 250000
```

## 许可证

本插件采用 [MIT License](LICENSE)。

## 开发验证

在已安装匹配的 WaveBench `v0.8.0` release 环境中：

```bash
python -m pytest -q packages/wavebench-rigol-ds1000z/tests
python -m ruff check packages/wavebench-rigol-ds1000z
python -m wavebench plugin package check packages/wavebench-rigol-ds1000z
python -m wavebench plugin install packages/wavebench-rigol-ds1000z --dry-run
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)；正式验收仍使用真实 wheel 和一次性虚拟环境。

默认测试使用 FakeTransport，不扫描资源、不连接仪器、不发送真实 SCPI。真实仪器资源、序列号、波形、截图和命令日志不得提交。

## 实机验收边界

2026-07-21 在 DS1104Z Plus 上完成脱敏回归：IDN、空错误队列、CH1 高阻 coupling、NORM 1200 点、显式 autoscale、MAX/DMAX 2400000 点分块读取、PNG 截图和 CH1/CH2 单次 acquisition 均通过。MAX/DMAX 各分为 10 个不超过 250000 点的块，前后错误队列均为空。

同日追加四通道实机路径回归：CH1–CH4 coupling 均可查询；一次 acquisition、一次 OPC 后，四个通道均返回 1200 点有限波形，采样间隔均为 2 µs，前后错误队列为空。CH1 当时测得约 2.04 Vpp；CH2–CH4 未接独立测试信号，因此本次只验收其通信和采集路径，不宣称已完成独立模拟幅度验收。

当前 VXI-11 路径读取 2400000 点约需 135 秒，因此该结果证明功能完整性，不代表长记录性能已优化。实测没有写入仓库中的配置、波形、截图或命令日志。

## 来源

0.1.0 初始实现从 WaveBench 主仓库的 DS1000Z 可安装插件试点迁移而来，保留原 canonical ID、entry point、兼容范围和驱动语义。本仓库是迁移后的外置包源码真源。
