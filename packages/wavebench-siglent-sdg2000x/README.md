# WaveBench SIGLENT SDG2000X 插件

[English](README_EN.md)

面向 SIGLENT SDG2042X、SDG2082X 和 SDG2122X 函数／任意波形发生器的 WaveBench 仪器插件。该包注册 canonical driver ID `siglent.sdg2000x`，不声明 alias，也不覆盖 WaveBench 内置驱动。

## 从这里开始

- [查询当前 capability、兼容范围和明确拒绝项](doc/SDG2000X_COVERAGE_MATRIX.md)
- [查阅开发记录与实机证据](doc/README.md)
- [在 WaveBench Core 中安装和管理插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

当前元数据版本为 `0.8.2`。包内 `pyproject.toml` 和 production descriptor 是版本、兼容范围与 capability 的权威来源。仓库级[生成式插件目录](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog.md)提供可检查的摘要。

> `source.harmonics_disable_v2` 只适用于 `SDG2122X` 固件 `2.01.01.39R7T2`。登记型号并不表示所有 capability、固件或 profile 可以互相外推。

## 只读起步

以下片段需合并到包含 `[connection]` 与 `[scope]` 的有效 `wavebench.toml`。示例使用 RFC 5737 文档保留地址，并从 `read_only` 开始：

```toml
[source]
driver = "siglent.sdg2000x"
resource = "TCPIP::192.0.2.40::INSTR"
default_channel = 1
check_errors = false
access = "read_only"

[safety_limits]
max_source_vpp = 10.0
```

`read_only` 允许身份和状态查询，Core 会拒绝写入。`check_errors = false` 表示当前 descriptor 没有声明错误队列 capability。通用配置字段和运行方式以 [WaveBench Core 配置 Reference](https://github.com/Scaxlibur/wavebench/blob/master/docs/reference/configuration.md)为准。

## 安全边界

- descriptor 导入不创建 transport，也不访问仪器。
- factory 只通过 `DriverContext` 打开已配置的 transport。
- 默认测试使用 fake transport，不扫描资源、不连接真实仪器。
- 输出开启需要可读的波形、幅度、偏置和复合模式状态，并由 Core 检查 `max_source_vpp`。
- profile、型号、固件、输出状态或写后 readback 不符合合同时，操作关闭失败。
- 高级命令域的历史实机证据不等于当前公共 capability，也不提供 raw SCPI 入口。
- 实机测试必须单独授权，并预先确认资源、固件、端接、初始输出状态、安全上限和恢复方式。

精确写入范围、Source V2 query budget 和 unsupported 项见[当前能力 Reference](doc/SDG2000X_COVERAGE_MATRIX.md)。

## 开发验证

```bash
python -m pytest -q packages/wavebench-siglent-sdg2000x/tests
python -m ruff check packages/wavebench-siglent-sdg2000x
python -m wavebench plugin package check packages/wavebench-siglent-sdg2000x
```

日常源码开发可使用仓库级 [editable 开发环境](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/DEVELOPMENT.md)。

## 许可证

本插件采用 [MIT License](LICENSE)。
