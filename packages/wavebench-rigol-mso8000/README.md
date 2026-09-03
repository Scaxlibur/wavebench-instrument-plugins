# WaveBench RIGOL MSO8000 插件

[English](README_EN.md)

面向 RIGOL MSO8000 系列混合信号示波器的 WaveBench 仪器插件，当前 production descriptor
只登记 MSO8104。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 MSO8000 插件文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 当前边界

当前实现覆盖有界 waveform fetch／capture、非重放错误队列、coupling、autoscale、截图，以及
受限的 math、统计、FFT、采集、数字状态、snapshot 和 cursor 接口。精确 capability、binary
预算、profile、未支持项和实机范围以 production descriptor、[功能覆盖矩阵](doc/MSO8104_COVERAGE_MATRIX.md)
及[验收记录](doc/MSO8104_HARDWARE_ACCEPTANCE.md)为准。

平均采集不在当前 descriptor 中。`tcpip`、`usb` 和 `gpib` resource scheme 只表示手册与离线
路由合同，不等于相应连接已经通过实机验收。

## 最小配置

```toml
[connection]
backend = "pyvisa"
resource = "TCPIP0::192.0.2.80::INSTR"

[scope]
driver = "rigol.mso8104"
default_channel = 1
check_errors = false
access = "read_write"
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 安全边界

descriptor 导入不打开 transport、扫描端口、发送 SCPI 或创建文件。仪器写入和 acquisition
trigger 不会盲目重试；Core 缺少必要安全接口时保持 capability 不可用，不增加 raw SCPI 入口。
真实资源、序列号、凭据、波形、截图和命令日志不得提交。

## 开发与许可证

里程碑、RFC、实机证据和历史状态见[插件文档](doc/README.md)。日常源码开发使用仓库级
[editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用 [MIT License](LICENSE)。
