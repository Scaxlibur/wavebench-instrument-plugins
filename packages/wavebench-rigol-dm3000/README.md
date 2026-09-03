# WaveBench RIGOL DM3000 插件

[English](README_EN.md)

面向 RIGOL DM3000/DM3058 数字万用表的 WaveBench 可执行仪器插件。本包仅支持经
PyVISA 访问的 LAN/VXI-11 连接。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [查看当前功能覆盖矩阵](doc/DM3000_COVERAGE_MATRIX.md)
- [查阅开发里程碑与实机证据](doc/DM3000_COVERAGE_MILESTONES.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 连接与能力边界

显式配置 `rigol.dm3000` 时使用此外置 LAN-only 实现。短 alias `dm3000` 和 `dm3058` 仍选择
Core fallback，并保留 RS-232 路径。canonical driver 会在打开 transport 前拒绝 serial backend
以及 ASRL、USB、GPIB 等非 TCPIP resource。

当前实现覆盖常见读数、测量功能与 profile、触发／calculation／系统接口只读状态，以及受限的
功能、DCV／ACV 档位和 DCV 输入阻抗设置。精确 capability、参数边界和拒绝行为以 production
descriptor 与功能覆盖矩阵为准。

## 配置示例

示例使用 RFC 5737 文档地址，不是实验室真实地址：

```toml
[dmm]
driver = "rigol.dm3000"
backend = "lan"
resource = "TCPIP::192.0.2.40::INSTR"
timeout_ms = 3000
settle_ms_before_read = 0
settle_ms_after_function_change = 500
```

## 安全边界

descriptor 导入不连接仪器。factory 只通过 `DriverContext` 打开当前配置的一个 transport。
默认测试不扫描资源、不连接仪器，也不会发送真实 SCPI。

档位或阻抗写入结果不明、恢复失败或无法证明自动／手动方式恢复时，当前实例会拒绝后续配置
写入。真实仪器地址、序列号、读数、截图和命令日志不得提交。

## 开发与许可证

日常源码开发和离线验证见仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用
[MIT License](LICENSE)。
