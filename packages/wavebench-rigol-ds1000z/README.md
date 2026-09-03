# WaveBench RIGOL DS1000Z 插件

[English](README_EN.md)

面向四通道 RIGOL DS1104Z、DS1104Z Plus、DS1104Z-S Plus 和兼容 DS1000Z 系列的 WaveBench 仪器插件。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [查看受控实机验收记录](doc/DS1000Z_HARDWARE_ACCEPTANCE.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 适用范围

显式配置 `driver = "rigol.ds1000z"` 时，WaveBench 使用此外置插件。内建的 `ds1104` 和
`ds1000z` alias 仍选择 Core fallback；本插件不声明 alias。

当前实现覆盖身份与错误队列查询、CH1–CH4 coupling、显式 autoscale、NORM／RAW／DMAX
BYTE 波形读取、单通道和四通道采集、PNG 截图及传输 telemetry。精确 capability、型号、
配置字段和兼容范围以 production descriptor 及生成式插件目录为准。

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

默认测试使用 FakeTransport，不扫描资源、不连接仪器，也不发送真实 SCPI。真实仪器资源、
序列号、波形、截图和命令日志不得提交。

## 开发与许可证

日常源码开发和离线验证见仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用
[MIT License](LICENSE)。
