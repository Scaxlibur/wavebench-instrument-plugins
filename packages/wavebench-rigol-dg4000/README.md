# WaveBench RIGOL DG4000 插件

[English](README_EN.md)

面向双通道 RIGOL DG4202 和兼容 DG4000 系列函数／任意波形发生器的 WaveBench 仪器插件。

## 从这里开始

- [查询当前版本、入口点、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 DG4000 插件文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Driver 入口

- `rigol.dg4202`：保留现有 V1 路由，并提供已声明的 Source V2 Basic、Output 和 Counter 操作。
- `rigol.dg4202-v2`：显式 opt-in 的受限 Sweep configure／manual-fire 入口。
- `rigol.dg4202-v2-workspace`：显式 opt-in 的无通道 volatile ARB 工作区替换入口。

三个入口都不声明 alias；短 alias `dg4202` 始终选择 Core fallback。各入口的精确 capability、
profile、版本范围和 conformance evidence refs 以 production descriptor 与生成式插件目录为准。

当前实现还覆盖严格只读快照与 profile、固定波形配置、输出控制，以及经过校验的 DAC14
上传。Core 负责波形文件加载、归一化、幅度安全限制、Service、run plan、状态恢复和 artifact。

## 最小配置

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.30::INSTR"

[source]
driver = "rigol.dg4202"
model_hint = "DG4202"
default_channel = 1
check_errors = true
```

示例使用 RFC 5737 文档地址。需要高级 Sweep 或 volatile workspace 时，必须显式选择对应的
opt-in driver ID。

## 安全边界

descriptor 导入不连接仪器。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。输出控制、
任意波形上传和其他写操作不会盲目重试；volatile USER／workspace 内容可能被覆盖，且不能承诺
恢复。真实仪器地址、序列号、波形、截图和命令日志不得提交。

## 开发与许可证

覆盖矩阵、里程碑、conformance 与历史验收入口见[插件文档](doc/README.md)。日常源码开发使用
仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)。本插件采用 [MIT License](LICENSE)。
