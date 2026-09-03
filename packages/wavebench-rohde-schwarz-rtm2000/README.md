# WaveBench R&S RTM2000 插件

[English](README_EN.md)

面向 Rohde & Schwarz RTM2000 系列示波器的 WaveBench 仪器插件，当前以 RTM2032 作为代表性
实机基线。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 RTM2000 插件文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 适用范围

显式配置 `driver = "rohde-schwarz.rtm2032"` 时，WaveBench 使用此外置插件。短 alias
`rtm2032` 始终选择 Core fallback；卸载插件后，canonical ID 也回退到内建实现。

当前实现覆盖模拟波形采集、coupling、显式 autoscale、截图、只读状态与分析数据，以及受控
average acquisition、通道显示和多通道 focus 配置。B1、K15 等选件相关行为保持显式门控；
没有证据的高级应用不会通过 raw SCPI 暴露。精确 capability、profile、配置字段和兼容范围以
production descriptor 及生成式插件目录为准。

默认 LAN 连接使用 Core 提供的 `rsinstrument-socket` backend。诊断兼容性时可以显式选择其他
descriptor 已声明的 RsInstrument backend；切换 backend 需要重新打开会话，失败的读取不会
自动重放。

## 最小配置

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.60::INSTR"

[scope]
driver = "rohde-schwarz.rtm2032"
default_channel = 1
check_errors = true

[scope.options]
long_waveform_timeout_ms = 300000
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 安全边界

插件负责 RTM2000 厂商 SCPI、波形解析和设备错误语义。Core 负责会话、权限、高阻保护、
artifact、run plan 和实验级恢复。真实仪器资源、序列号、波形、截图和命令日志不得提交。

## 开发与许可证

日常源码开发和离线验证见仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用
[MIT License](LICENSE)。
