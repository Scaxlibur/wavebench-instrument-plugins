# WaveBench RIGOL DP800 插件

[English](README_EN.md)

面向 RIGOL DP800 系列、当前以 DP832/DP832A 为公开兼容范围的 WaveBench 可执行仪器插件。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [查看当前功能覆盖矩阵](doc/DP800_COVERAGE_MATRIX.md)
- [查阅开发里程碑与实机证据](doc/DP800_COVERAGE_MILESTONES.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 当前边界

显式配置 `rigol.dp800` 时使用此外置实现；短 alias `dp800` 始终选择 Core fallback。当前实现
覆盖身份与错误队列、通道状态和测量、电压／电流限值、显式输出控制及 OVP／OCP。精确
capability、型号范围和协议限制以 production descriptor 与功能覆盖矩阵为准。

插件负责 DP800 厂商 SCPI、解析和读回。Core 负责安全上限、保护阈值与设定值关系、输出开启
前检查、Service、run plan 和实验级状态恢复。

## 配置示例

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.50::INSTR"

[safety_limits]
max_power_voltage_v = 5.0
max_power_current_limit_a = 0.2

[power]
driver = "rigol.dp800"
default_channel = 1
check_errors = true
settle_ms_after_set = 2000
settle_ms_after_output = 500
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 安全边界

descriptor 导入不连接仪器。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。写命令
不会盲目重试；结果不明、恢复无法确认或出现新 trip 时，当前实例会拒绝后续配置写入。输出
失败会尝试保持 OFF，保护恢复不发送 `CLEAR`。

真实地址、序列号、设定值快照、测量值和命令日志不得提交。

## 开发与许可证

日常源码开发和离线验证见仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用
[MIT License](LICENSE)。
