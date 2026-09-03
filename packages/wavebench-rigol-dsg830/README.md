# WaveBench RIGOL DSG830 插件

[English](README_EN.md)

面向 RIGOL DSG830 射频信号发生器的 WaveBench 仪器插件。该包注册 canonical driver ID `rigol.dsg830`，不声明 alias，也不覆盖 WaveBench 内置驱动。

## 从这里开始

- [查询当前 capability、profile 和限制](doc/reference.md)
- [查阅开发里程碑与实机证据](doc/README.md)
- [在 WaveBench Core 中安装和管理插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

包元数据和 production descriptor 是当前版本、兼容范围与 capability 的权威来源。仓库级[生成式插件目录](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog.md)提供可检查的摘要。

## 只读起步

以下配置使用 RFC 5737 文档保留地址，只允许身份和状态查询：

```toml
[rf_source]
driver = "rigol.dsg830"
resource = "TCPIP::192.0.2.83::INSTR"
access = "read_only"
```

`read_only` 配置不会执行 reset、RF 输出切换、频率或功率写入、调制、Pulse 或 Sweep 配置。精确配置字段和通用运行方式以 [WaveBench Core 配置 Reference](https://github.com/Scaxlibur/wavebench/blob/master/docs/reference/configuration.md)为准。

## 安全边界

- descriptor 导入不创建 transport、不扫描端口，也不发送 SCPI。
- factory 只通过 `DriverContext` 打开已配置的 transport。
- 写操作必须显式使用 `read_write`，并满足对应 capability、设备状态、端口安全限制和 readback 要求。
- `rf_out` 的 50 Ω dBm 参考不等于实际端接；WaveBench 不从连接器名称推断负载。
- 后面板 `PULSE IN/OUT` 与 50 Ω RF 输出是不同接口，不得共用电气假设。
- 实机测试必须单独授权，并预先确认资源、固件、端接、初始输出状态、安全限制和恢复方式。

默认测试使用 fake transport，不连接真实仪器。当前开放的写入范围、固定 profile 和明确拒绝项见[当前 Reference](doc/reference.md)。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dsg830/tests
python -m ruff check packages/wavebench-rigol-dsg830
python -m wavebench plugin package check packages/wavebench-rigol-dsg830
```

日常源码开发可使用仓库级 [editable 开发环境](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/DEVELOPMENT.md)。

## 许可证

本插件采用 [MIT License](LICENSE)。
