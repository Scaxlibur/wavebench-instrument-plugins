# WaveBench RIGOL DG1000 插件

[English](README_EN.md)

面向双通道 RIGOL DG1022、DG1022A、DG1022Z、DG1032Z、DG1062Z 与兼容 DG1000/DG1000Z
系列函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 身份与兼容范围

- distribution：`wavebench-rigol-dg1000`
- canonical driver ID：`rigol.dg1000`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

该插件声明 canonical ID `rigol.dg1000`，不声明短 alias。安装后，需要在配置中显式使用
`driver = "rigol.dg1000"` 才会选择此外置实现。

## 能力

- `*IDN?` 与错误队列；
- CH1/CH2 输出、函数、频率、VPP 幅度、offset、phase、sweep 状态和方波占空比读取；
- 固定频率、函数、VPP 幅度和方波占空比设置；
- 显式输出开关；
- 设置固定频率前可按 WaveBench source 配置显式关闭 sweep。

当前公开能力只覆盖 basic source 控制面。插件不声明 DG4000/DG4202 专用的任意波上传、harmonic
mode、modulation、burst、counter profile 或完整 sweep profile。DG1000 前面板或厂商协议中的
加法/谐波叠加功能不在本插件的受支持能力内；启用该功能时，基波与谐波的实际输出很可能与设置值
不一致，不能把 basic status 回读视为准确的谐波验收依据。WaveBench core 继续负责安全上限、
Service、run plan、状态恢复和 artifact；插件只负责 DG1000 系列 SCPI、解析和回读。

驱动同时覆盖两种已知命令布局：DG1022/DG1022A 的 legacy `:CH2` 后缀布局，以及
DG1022Z/DG1032Z/DG1062Z 的 `:SOUR<n>:` 前缀布局。未识别型号会 fail closed。

## 安全边界

descriptor 导入不连接仪器。factory 只通过 WaveBench `DriverContext` 打开当前配置的 transport。
默认离线测试使用 FakeTransport，不扫描资源、不连接仪器，也不发送真实 SCPI。写命令失败后，
当前 driver 实例会锁停后续配置写入，要求调用方重新打开会话并独立验证设备状态。

配置示例使用 RFC 5737 文档保留地址：

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.30::INSTR"

[source]
driver = "rigol.dg1000"
default_channel = 1
check_errors = true
ensure_fix_mode_on_set_frequency = true
settle_ms_after_set_frequency = 500
```

真实仪器地址、序列号、波形、截图和命令日志不得提交。

## 许可证

本插件采用 [MIT License](LICENSE)。

## 开发验证

在已安装匹配的 WaveBench `v0.8.0` release 环境中：

```bash
python -m pytest -q packages/wavebench-rigol-dg1000/tests
python -m ruff check packages/wavebench-rigol-dg1000
python -m wavebench plugin package check packages/wavebench-rigol-dg1000
python -m wavebench plugin install packages/wavebench-rigol-dg1000 --dry-run
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)；正式验收仍使用真实
wheel 和一次性虚拟环境。
型号覆盖和能力边界见 [DG1000 覆盖矩阵](doc/DG1000_COVERAGE_MATRIX.md)。

## 实机验收边界

`0.1.0` 的公开门禁目前覆盖离线 FakeTransport、受管安装生命周期和 wheel 检查。DG1032Z
直连示波器的闭环实验台可用于后续实机门禁；在形成可复现、已脱敏的实机记录前，本包不把
DG1032Z 行为外推到其他 DG1000/DG1000Z 型号或 legacy DG1022/DG1022A 命令布局。

实机验收记录不得提交真实资源、序列号、原始波形、截图或命令日志。当前 capability 仍只代表
basic source 控制面，不覆盖任意波上传、offset/symmetry setter、modulation、burst、counter 或
完整 sweep profile。

## 来源

`0.1.0`：从 WaveBench 主仓 DG1000 草案实现迁移为独立插件包，保留 vendor driver、descriptor、
entry point 和 FakeTransport 测试；当前只声明 basic source 能力。
