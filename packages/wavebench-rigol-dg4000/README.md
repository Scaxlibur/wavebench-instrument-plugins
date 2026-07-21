# WaveBench RIGOL DG4000 插件

[English](README_EN.md)

面向双通道 RIGOL DG4202 和兼容 DG4000 系列函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 身份与兼容范围

- distribution：`wavebench-rigol-dg4000`
- canonical driver ID：`rigol.dg4202`
- WaveBench：`>=0.7,<1`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件不声明 alias。安装后，显式 canonical ID `rigol.dg4202` 选择外置实现；短 alias `dg4202` 始终选择 WaveBench 内建 fallback。卸载插件后，canonical ID 也回退到内建实现。

## 能力

- `*IDN?`、错误队列与 CH1/CH2 状态读取；
- 固定频率、函数、VPP 幅度、方波占空比和显式输出控制；
- 只读任意波形 SCPI 能力探测；
- 使用 WaveBench 公共 `DG4000DacBlock` 契约上传已校验的 DAC14 binary block。

WaveBench 核心继续负责波形文件加载、归一化、DAC14 编码、幅度安全限制、Service、run plan、状态恢复和 artifact。插件不复制这些策略。

## 安全边界

descriptor 导入不连接仪器。factory 只通过 `DriverContext` 打开当前配置的 transport。默认离线测试不扫描资源、不连接仪器，也不发送真实 SCPI。输出控制、任意波形上传和其他写操作不会盲目重试。

示例使用文档保留地址：

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

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dg4000/tests
python -m ruff check packages/wavebench-rigol-dg4000
python -m wavebench plugin package check packages/wavebench-rigol-dg4000
python -m wavebench plugin install packages/wavebench-rigol-dg4000 --dry-run
```

真实仪器地址、序列号、波形、截图和命令日志不得提交。仓库尚未为该包选择开源许可证，不能据此推断发布许可。

## 来源

0.1.0 初始驱动从 WaveBench 内建 DG4202 协议实现迁移而来。迁移保留核心 Service 和安全策略，只把厂商协议、descriptor、entry point 与 FakeTransport 测试外置。
