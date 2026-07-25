# WaveBench R&S RTM2000 插件

[English](README_EN.md)

面向 Rohde & Schwarz RTM2000 系列、当前以 RTM2032 为实机基线的 WaveBench 可执行示波器插件。

## 身份与开发基线

- distribution：`wavebench-rohde-schwarz-rtm2000`
- canonical driver ID：`rohde-schwarz.rtm2032`
- 开发基线：WaveBench `60dffd0`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- 默认 transport backend：核心提供的 `rsinstrument-socket`

本插件对齐 WaveBench `v0.8.0` release，不维护旧核心兼容矩阵，不能与 `v0.7.0` 配套运行，也不自动声明兼容未来 `0.9`。安装后，显式 canonical ID
`rohde-schwarz.rtm2032` 选择外置实现；短 alias `rtm2032` 始终选择内建 fallback。卸载
插件后，canonical ID 也回退内建实现。

## 能力与边界

- `*IDN?`、错误队列和显式 autoscale；
- 厂商专用只读 identity/options/health 快照，不消费 EVENT 寄存器或错误队列；
- RTM2032 CH1/CH2 类型化模拟通道、时基和探头元数据快照；
- 当前波形读取与单次 acquisition；
- 一次 acquisition 后按通道读取多路波形；
- 通道 coupling 查询和 PNG 截图；
- `DEF` / `MAX` / `DMAX` 点数模式原样交给 RTM2000。

插件只负责 RTM2000 厂商 SCPI、header/REAL 波形解析和错误语义。RsInstrument 会话、超时、
高阻保护、Service、artifact、run plan 和实验级状态恢复留在核心。空列表、短列表、无效 header、
非 PNG 截图和 OPC 超时都显式失败，不补零、不伪造成功、不盲目重试。

`backend = "lan"` 按 descriptor 首选顺序使用 RsInstrument SocketIO，不依赖 VISA-C 或
pyvisa-py。诊断兼容性时可显式选择 `rsinstrument`、`rsinstrument-rsvisa` 或
`rsinstrument-pyvisa-py`；切换后端必须重新打开会话，读取失败后不会自动重放。插件仅对
`MAX` / `DMAX` 波形数据读取使用独立的长传输 timeout，并记录不含地址、序列号和波形内容的
分块进度、点数、字节数、耗时与吞吐 telemetry。

## 配置示例

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

## 编程手册投放位置

将 RTM2000 系列示波器编程手册放到：

```text
doc/vendor-local/RTM2000_programming_manual.pdf
```

也可以保留厂商原始文件名。`doc/vendor-local/` 中除说明文件外的内容会被 Git 忽略，整个目录也会从 sdist 排除，不会随仓库推送或公开发行包发布。项目根据手册整理的 SCPI 索引、能力矩阵和验收资料应另放在公开 `doc/` 中，并明确区分手册声明与实机验证结果。

当前手册命令面与插件、内建 fallback、实机证据的对照见 [RTM2000 手册功能覆盖矩阵](doc/RTM2000_COVERAGE_MATRIX.md)。

## 验收状态

0.1.0 已于 2026-07-24 完成真实 wheel 的受控 RTM2032 LAN/VXI-11 验收：受管安装与 healthy/load、
canonical 与短 alias 路由、双通道单次 acquisition、`DEF` / `MAX` / `DMAX` 完整波形、
autoscale、高阻 coupling 守卫、PNG 截图、20/20 双通道重复采集和空错误队列均通过。
`MAX` 每通道实测 10000000 点，`DMAX` 每通道实测 6250000 点；长记录使用独立 300 s
传输上限，不把统一 30 s 超时误判为协议失败。验收前保存了完整 setup 快照，结束后确认
setup blob、配置指纹和活动采集状态均恢复。验收未修改真实 `wavebench.toml`，未提交真实
地址、序列号、波形、截图、快照或命令日志。实验级快照与恢复仍属于核心/验收工具边界，
不进入厂商驱动。

0.2.0 将默认 LAN transport 改为 RsInstrument SocketIO，保留上述显式兼容后端。离线门禁
覆盖 descriptor 路由、调用级长传输 timeout、脱敏 telemetry 和 wheel 生命周期。RTM2032
实机已通过 SocketIO 的 DEF/MAX/DMAX、截图、autoscale、20/20 重复采集与空错误队列验收。
实验级 `SYST:SET` setup 恢复不属于插件驱动：SocketIO 写入曾出现只部分生效，因此验收工具
固定使用已验证的 VXI-11 512-byte 协议分片，并在重连后只读核对完整 blob、配置指纹和活动
采集状态。验收结束时快照已删除，真实地址、序列号、波形和命令日志均未进入提交。

0.3.0 开发线新增严格类型化的只读 identity/options/health 快照。health 快照只读取
`*STB?`、operation/questionable condition、acquisition available/count 和 sample rate；不读取会
消费状态的 EVENT 寄存器，也不自动清空错误队列。该厂商专用 API 不扩张 WaveBench 核心
capability 声明。0.3.0 还增加 RTM2032 CH1/CH2 的模拟通道、时基和探头元数据快照；
`FULL` 带宽、`UNKN` 阻抗和仪器不可用数值映射为 `None`；封闭枚举中的未知值、格式非法的
开放 token、非有限值、未加引号文本和 CH1/CH2 之外的索引均失败关闭。命令索引只证明命令面存在，返回类型来自 RTM2032
受控只读实测；不会外推为所有 RTM2000 型号的通用契约。实机已验证两路通道、当前时基和
无源探头状态，验收后 status byte 为 0；未读取 EVENT 或错误队列，也未发送设置命令。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rohde-schwarz-rtm2000/tests
python -m ruff check packages/wavebench-rohde-schwarz-rtm2000
python -m wavebench plugin package check packages/wavebench-rohde-schwarz-rtm2000
```

真实地址、序列号、波形、截图和命令日志不得提交。本插件采用 [MIT License](LICENSE)。

## 来源

0.1.0 从 WaveBench 主仓库 `973fc88` 的内建 RTM2032 协议实现迁移，只把厂商驱动、
descriptor、entry point 和 FakeTransport 测试外置。
