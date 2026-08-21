# WaveBench SIGLENT SDG2000X 插件

[English](README_EN.md)

面向 SIGLENT SDG2042X、SDG2082X 和 SDG2122X 函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 当前开发基线

版本 `0.4.0` 在 M3 基线上增加 `source.set_frequency`，当前声明 `source.idn`、`source.status`、`source.set_frequency` 与 `source.output`。频率写入按型号和波形检查 1 µHz 至对应上限；写前、写后均读取完整安全上下文，写后异常会确认输出 OFF 并锁止当前会话的全部配置写入。函数、幅度、占空比、调制、Sweep、Burst、任意波上传和 Counter capability 仍未开放。

`SDG2122X` 固件 `2.01.01.39R7T2` 已完成身份、CH1/CH2 状态与 `source.output` 实机验收。两路保留 1 kHz、4 Vpp、0 V 偏置正弦配置，分别通过 RTM2032 高阻输入闭环测量，验收结束时均为 OFF。`SDG2042X` 与 `SDG2082X` 按同一手册命令合同放行 `source.output`，但实机结论不从 `SDG2122X` 外推。

## 身份与兼容范围

- distribution：`wavebench-siglent-sdg2000x`
- canonical driver ID：`siglent.sdg2000x`
- 已登记型号：`SDG2042X`、`SDG2082X`、`SDG2122X`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件不声明 alias，也不覆盖 WaveBench 内置驱动。安装后必须显式配置 canonical ID `siglent.sdg2000x`。

## 本地编程手册

厂商编程手册保存在被忽略的 [`doc/vendor-local/`](doc/vendor-local/README.md) 目录：

```text
SDG_Series_Programming_Guide_E05C.pdf
```

手册原文件不进入 Git 或发行包。公开的命令覆盖状态见 [SDG2000X 功能覆盖矩阵](doc/SDG2000X_COVERAGE_MATRIX.md)，分阶段开发门见 [SDG2000X 覆盖里程碑](doc/SDG2000X_COVERAGE_MILESTONES.md)，实机证据见 [SDG2000X 只读实机验收](doc/SDG2000X_READONLY_ACCEPTANCE.md) 与 [SDG2000X 输出控制实机验收](doc/SDG2000X_OUTPUT_ACCEPTANCE.md)。

## 配置示例

以下片段需合并到已包含 `[connection]` 与 `[scope]` 的有效 `wavebench.toml`。示例使用 RFC 5737 文档保留地址，并以更安全的 `read_only` 状态起步。`source.output` 需要显式改为 `read_write`，同时保留 Vpp 安全上限：

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

将 `access` 改为 `read_write` 后才能调用 `source.set_frequency` 或 `source.output`；保留 `read_only` 时，身份和通道状态仍可查询，写操作会由核心拒绝。`check_errors = false` 表示错误队列尚未形成已认证 capability；驱动不会伪装错误队列检查。

## 安全边界

- descriptor 导入不创建 transport，也不访问仪器。
- factory 只通过 `DriverContext` 打开当前配置的 transport。
- 默认测试只使用 fake transport，不扫描资源、不连接仪器。
- `source.output` 开启前必须读取 FIX、Sweep OFF、Vpp 幅度、偏置和所有已知复合波模式，并由核心检查 `max_source_vpp`。
- `source.set_frequency` 检查型号与当前波形上限；Sweep 自动切回 FIX 只允许在输出 OFF 时执行。
- 目标配置只写入一次；任何写后异常都会尝试 OFF 恢复并锁止本会话的全部配置写入。
- 函数、幅度、占空比和高级命令域写入仍未开放。
- 实机测试必须单独授权，并先确认资源、固件、终止符、输出状态、安全上限和恢复方式。

## 开发验证

```bash
python -m pytest -q packages/wavebench-siglent-sdg2000x/tests
python -m ruff check packages/wavebench-siglent-sdg2000x
python -m wavebench plugin package check packages/wavebench-siglent-sdg2000x
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。正式验收仍使用真实 wheel 和一次性虚拟环境。

## 许可证

本插件采用 [MIT License](LICENSE)。

## 公开资料

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- [SDG2000X 协议审计](doc/SDG2000X_PROTOCOL_AUDIT.md)
- [SDG2000X 只读实机验收](doc/SDG2000X_READONLY_ACCEPTANCE.md)
- [SDG2000X 输出控制实机验收](doc/SDG2000X_OUTPUT_ACCEPTANCE.md)
