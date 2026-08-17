# WaveBench SIGLENT SDG2000X 插件

[English](README_EN.md)

面向 SIGLENT SDG2042X、SDG2082X 和 SDG2122X 函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 当前开发基线

版本 `0.1.0` 是 M0 身份查询基线，只声明 `source.idn`。驱动支持编程手册记录的两种 `*IDN?` 返回格式，并拒绝非 SDG2000X 系列型号。状态读取、错误队列、输出控制、固定波、调制、扫描、Burst、任意波上传和计数器能力尚未开放。

这个边界是刻意保守的：未经过编程手册审计、fake transport 测试和受控实机验收的命令，不写进 descriptor，也不伪装成可用 capability。

## 身份与兼容范围

- distribution：`wavebench-siglent-sdg2000x`
- canonical driver ID：`siglent.sdg2000x`
- 已登记型号：`SDG2042X`、`SDG2082X`、`SDG2122X`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件不声明 alias，也不覆盖 WaveBench 内置驱动。安装后必须显式配置 canonical ID `siglent.sdg2000x`。

## 本地编程手册

厂商编程手册放在被忽略的 [`doc/vendor-local/`](doc/vendor-local/README.md) 目录。推荐文件名为：

```text
SDG_Series_Programming_Guide_E05C.pdf
```

手册原文件不进入 Git 或发行包。公开的命令覆盖状态见 [SDG2000X 功能覆盖矩阵](doc/SDG2000X_COVERAGE_MATRIX.md)，分阶段开发门见 [SDG2000X 覆盖里程碑](doc/SDG2000X_COVERAGE_MILESTONES.md)。

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

M0 只支持身份查询。`check_errors = false` 表示错误队列尚未形成已认证 capability，不代表忽略已经发生的仪器错误。

## 安全边界

- descriptor 导入不创建 transport，也不访问仪器。
- factory 只通过 `DriverContext` 打开当前配置的 transport。
- 默认测试只使用 fake transport，不扫描资源、不连接仪器。
- 当前驱动没有写方法，不会发送 reset、输出切换或波形配置命令。
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
- [SIGLENT SDG Series Programming Guide](https://int.siglent.com/u_file/download/24_06_07/SDG_Programming%20Guide_PG02-E05C.pdf)
