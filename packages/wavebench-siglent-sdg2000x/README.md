# WaveBench SIGLENT SDG2000X 插件

[English](README_EN.md)

面向 SIGLENT SDG2042X、SDG2082X 和 SDG2122X 函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 当前开发基线

版本 `0.2.0` 是 M2 严格只读基线，声明 `source.idn` 与 `source.status`。驱动支持编程手册记录的两种 `*IDN?` 返回格式，并通过 `OUTP?`、`BSWV?`、`SWWV?` 将 CH1/CH2 状态映射为 WaveBench `SourceStatus`。错误队列、输出控制、固定波、调制、Sweep、Burst、任意波上传和 Counter capability 尚未开放。

`SDG2122X` 固件 `2.01.01.39R7T2` 已完成身份和 CH1/CH2 状态的零写入实机验收。该结论不外推到 `SDG2042X`、`SDG2082X` 或其它固件。未完成审计与离线验证的命令不写入 descriptor，也不伪装成可用 capability。

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

手册原文件不进入 Git 或发行包。公开的命令覆盖状态见 [SDG2000X 功能覆盖矩阵](doc/SDG2000X_COVERAGE_MATRIX.md)，分阶段开发门见 [SDG2000X 覆盖里程碑](doc/SDG2000X_COVERAGE_MILESTONES.md)，实机证据见 [SDG2000X 只读实机验收](doc/SDG2000X_READONLY_ACCEPTANCE.md)。

## 配置示例

示例使用 RFC 5737 文档保留地址，并保持只读访问：

```toml
[connection]
backend = "lan"

[source]
driver = "siglent.sdg2000x"
resource = "TCPIP::192.0.2.40::INSTR"
default_channel = 1
check_errors = false
access = "read_only"
```

M2 支持身份和通道状态查询。`check_errors = false` 表示错误队列尚未形成已认证 capability，不代表忽略已经发生的仪器错误。

## 安全边界

- descriptor 导入不创建 transport，也不访问仪器。
- factory 只通过 `DriverContext` 打开当前配置的 transport。
- 默认测试只使用 fake transport，不扫描资源、不连接仪器。
- 当前驱动没有写方法；状态读取只发送身份、输出状态、基本波和 Sweep 状态查询。
- 实机测试必须单独授权，并先确认资源、固件、终止符、输出状态和恢复方式。

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
