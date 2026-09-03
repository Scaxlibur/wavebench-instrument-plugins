# WaveBench SIGLENT SDS800X HD 插件

[English](README_EN.md)

面向 SIGLENT SDS800X HD 系列示波器的 WaveBench 仪器插件。SDS804X HD 是当前代表性实机
基线；其他型号的具体身份返回和实机范围以证据页面为准。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 SDS800X HD 插件文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 当前边界

当前实现覆盖严格身份检查、模拟通道 coupling、`DMAX` 波形读取与单次采集、只读测量统计、
PNG 截图，以及独立采集运行状态与控制。精确 capability、profile 和型号范围以 production
descriptor 为准；[功能覆盖矩阵](doc/SDS800X_HD_COVERAGE_MATRIX.md)说明协议行为和未支持项。

该系列模拟输入固定为 `1 MΩ`，没有内部 `50 Ω` 端接。CN11G 没有记录错误队列命令，因此
插件不声明 `scope.errors`。使用波形读取时必须显式关闭 WaveBench 错误队列检查：

```toml
[scope]
driver = "siglent.sds800x-hd"
check_errors = false

[waveform]
format = "real"
byte_order = "lsbf"
points = "dmax"
```

当前只接受 `points="dmax"`。`points="def"`、`points="max"` 和 `check_errors=True` 会在仪器
I/O 前失败。插件不提供 raw SCPI，也不将其他 SIGLENT 系列的协议推定为兼容。

## 安全边界

descriptor 导入不执行仪器 I/O；factory 只通过 `DriverContext.open_transport()` 获取 Core
transport。默认测试使用 FakeTransport。真实设备地址、序列号、原始波形、截图和命令日志
不得提交。

## 开发与许可证

本地手册、实机验收和 Scope R1.3 conformance 入口见 [插件文档](doc/README.md)。日常源码开发
使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。项目原创代码和文档采用
[MIT License](LICENSE)；厂商资料不属于公开 distribution。
