# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

M0～M3 已离线完成，M4 的 `DEF` 采集切片已经进入 `0.3.1`。当前声明 `scope.idn`、`scope.channel_coupling`、`scope.fetch_waveform`、`scope.capture_waveform` 与 `scope.capture_waveforms`；MAX/DMAX、截图、数字通道和消费型错误队列尚未完成。

本轮开发只使用手册审计、FakeTransport、故障注入、构建和安装生命周期验证，不连接真实仪器。所有型号、固件、transport、吞吐、恢复和测量结论均保持「未实机验证」。

当前身份信息：

- distribution：`wavebench-rigol-mso8000`
- canonical driver ID：`rigol.mso8104`
- kind：`scope`
- 目标型号：`MSO8104`
- Python：`>=3.11`
- WaveBench：`>=0.8.22,<0.9`

## 目录说明

- `doc/vendor-local/`：本地厂商手册。原始 PDF 和转换后的 Markdown 都放在这里；除说明文件外的内容会被 Git 忽略，也不会进入发行包。
- `src/wavebench_rigol_mso8000/`：descriptor、driver 与严格解析器。
- `tests/`：FakeTransport、故障注入与制品生命周期测试；默认测试不得连接真实仪器。
- `pyproject.toml`：distribution 元数据、WaveBench 版本范围和唯一 entry point。
- `doc/`：公开覆盖矩阵和验收记录；厂商原文不要放到公开文档目录。

## 设计文档

- [MSO8104 功能覆盖里程碑](doc/MSO8104_COVERAGE_MILESTONES.md)
- [MSO8104 编程手册功能覆盖矩阵](doc/MSO8104_COVERAGE_MATRIX.md)

## 推荐开发顺序

1. M4 补齐有界 MAX/DMAX 长记录。
2. 后续 capability 按里程碑分别补齐离线测试、写入副作用和恢复边界。

## 安全边界

descriptor 导入不得打开 transport、扫描端口、发送 SCPI 或创建文件。真实资源、序列号、凭据、波形、截图和命令日志不得提交。仪器写入和 acquisition trigger 不做盲目重试。核心缺少必要安全接口时，先写 RFC 并跳过对应 capability，不在插件中增加 raw SCPI 入口。

当前 descriptor 允许 `tcpip`、`usb`、`gpib` 资源前缀，这是手册声明和离线路由合同，不是连接实机通过的证据。

`channel_coupling()` 联合查询通道耦合与输入阻抗，并把 `AC/DC + OMEG` 映射为核心高阻 token `ACL/DCL`，把 `AC/DC + FIFT` 映射为低阻 token `AC/DC`。核心默认拒绝 50 Ω、`GND` 和未知状态。由于 `:SYSTem:ERRor?` 会消费队首且核心普通文本查询可能重放，当前不声明 `scope.errors`；调用后续波形 Service 时必须显式配置 `scope.check_errors=false`，直到 [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) 落地。

当前波形能力只接受 `points="def"`，要求目标通道已经显示，并暂时把传输状态设为 `NORMal + BYTE + 1000` 点。driver 保存、逐字段回读并恢复 SOURCE、MODE、FORMAT、POINTS、START 与 STOP；不发送 STOP、SINGLE 或 AUTOSCALE。恢复失败或写入结果不明会锁存波形写域，后续调用必须关闭并重新打开会话。该能力会写波形传输状态，因此配置需使用 `scope.access="read_write"`。

`capture_waveform(s)` 同样只接受 `points="def"`，要求全部目标通道已经显示且时基为 MAIN。多通道调用只发送一次 `:SINGle`，随后轮询 `:TRIGger:STATus?` 直到 STOP，再逐通道读取并校验 X 轴一致；不使用 `*OPC?` 代替采集完成，不自动强制 STOP、RUN 或重新触发。超时或状态不明会锁存 acquisition 写域。该切片不接受 `time_range_s` 或 `vertical_scale_v_per_div`，相关状态须预先配置；完成后仪器保持 SINGLE 自然结束的 STOP 状态。

```toml
[connection]
backend = "pyvisa"
resource = "TCPIP0::192.0.2.80::INSTR"

[scope]
driver = "rigol.mso8104"
default_channel = 1
check_errors = false
access = "read_write"

[waveform]
format = "real"
byte_order = "lsbf"
points = "def"
```

示例地址属于 RFC 5737 文档网段，不是实验室资源。

## 开发手册位置

本地厂商资料的具体放置规则见 [`doc/vendor-local/README.md`](doc/vendor-local/README.md)。
