# WaveBench R&S RTM2000 插件

[English](README_EN.md)

面向 Rohde & Schwarz RTM2000 系列、当前以 RTM2032 为实机基线的 WaveBench 可执行示波器插件。

## 身份与 HEAD 基线

- distribution：`wavebench-rohde-schwarz-rtm2000`
- canonical driver ID：`rohde-schwarz.rtm2032`
- 开发基线：WaveBench `973fc88`
- Python：`>=3.11`
- transport backend：核心提供的 `rsinstrument`

本插件只对齐 WaveBench 当前 HEAD，不维护旧核心兼容矩阵。安装后，显式 canonical ID
`rohde-schwarz.rtm2032` 选择外置实现；短 alias `rtm2032` 始终选择内建 fallback。卸载
插件后，canonical ID 也回退内建实现。

## 能力与边界

- `*IDN?`、错误队列和显式 autoscale；
- 当前波形读取与单次 acquisition；
- 一次 acquisition 后按通道读取多路波形；
- 通道 coupling 查询和 PNG 截图；
- `DEF` / `MAX` / `DMAX` 点数模式原样交给 RTM2000。

插件只负责 RTM2000 厂商 SCPI、header/REAL 波形解析和错误语义。RsInstrument 会话、超时、
高阻保护、Service、artifact、run plan 和实验级状态恢复留在核心。空列表、短列表、无效 header、
非 PNG 截图和 OPC 超时都显式失败，不补零、不伪造成功、不盲目重试。

## 配置示例

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.60::INSTR"

[scope]
driver = "rohde-schwarz.rtm2032"
default_channel = 1
check_errors = true
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 验收状态

0.1.0 已完成离线协议、descriptor、FakeTransport、真实 wheel 和受管生命周期实现。RTM2032
双通道实机验收尚未完成，因此当前不宣称硬件迁移收口。

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
