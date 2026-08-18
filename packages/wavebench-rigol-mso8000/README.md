# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

M0～M4 与 M7 已离线完成，M5 截图和 M6 数字通道经 RFC/证据评审后跳过。当前 `0.7.0` 已新增 `scope.autoscale`、`scope.math_metadata` 与受限 `scope.cursor_readout`；其余高级能力按核心模型或厂商证据缺口保持未声明，下一步为 M8 发行审计。

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

1. M8 对文档、测试、制品和安装生命周期做全量离线审计。

## 安全边界

descriptor 导入不得打开 transport、扫描端口、发送 SCPI 或创建文件。真实资源、序列号、凭据、波形、截图和命令日志不得提交。仪器写入和 acquisition trigger 不做盲目重试。核心缺少必要安全接口时，先写 RFC 并跳过对应 capability，不在插件中增加 raw SCPI 入口。

当前 descriptor 允许 `tcpip`、`usb`、`gpib` 资源前缀，这是手册声明和离线路由合同，不是连接实机通过的证据。

当前不声明 `scope.screenshot`。`:DISPlay:DATA?` 的手册段落没有声明 TMC block framing，`:SAVE:IMAGe:DATA?` 虽为 TMC block，却不能证明返回图片满足核心 `include_menu=False` 合同。具体缺口见 [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md)；插件不猜测 framing、不忽略参数，也不创建仪器文件。

当前也不声明 `scope.digital_status` 或 `scope.digital_waveform`。数字状态的核心模型要求 MSO8000 无法查询的必填字段，见 [RFC-0004](doc/rfcs/0004-portable-scope-digital-status.md)；数字 waveform 的厂商手册未定义 BYTE/WORD 逻辑 code，WORD 字节序也不明确。插件不以默认值或模拟量换算制造数字状态。

`scope.autoscale` 会按核心操作合同改变垂直、时基和触发设置。driver 先查询 `:SYSTem:AUToscale?`，禁用时不发送写命令；调用必须设置 `check_errors=false`。写入或 OPC 完成状态不确定时会锁存 autoscale 写域，关闭并重新打开会话前不再重试。该能力只有离线序列与故障注入证据，自动设置效果未实机验证。

`scope.math_metadata` 只接受已显示的 MATH1～MATH4 和 MAIN 时基。driver 保存六项 waveform 传输状态，按手册要求先切换到 NORM，再选择 MATH 源与 BYTE 格式，只查询 preamble 后恢复原状态；不读取波形数据。返回的 `values_per_sample` 为未知，Y 分辨率来自 BYTE 格式的 8 位合同。数学运算内容、FFT 精度和设备恢复均未实机验证。

`scope.cursor_readout` 只读取调用方确认已配置的全局手动光标，公共 `cursor_index` 固定为 `1`。当前仅接受 A/B 同源的 `TIME + SEC` 或 `AMPL + SOUR`：前者返回 X 差和倒数，后者返回 Y 差。追踪、XY、测量模式、双源、NONE、LA 幅度以及 Hz、角度、百分比单位均默认拒绝；driver 不移动或重配光标。读数准确度未实机验证。

`channel_coupling()` 联合查询通道耦合与输入阻抗，并把 `AC/DC + OMEG` 映射为核心高阻 token `ACL/DCL`，把 `AC/DC + FIFT` 映射为低阻 token `AC/DC`。核心默认拒绝 50 Ω、`GND` 和未知状态。由于 `:SYSTem:ERRor?` 会消费队首且核心普通文本查询可能重放，当前不声明 `scope.errors`；调用后续波形 Service 时必须显式配置 `scope.check_errors=false`，直到 [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) 落地。

波形能力接受 `DEF`、`MAX` 与 `DMAX`。`DEF` 使用 `NORMal + BYTE + 1000` 点；`MAX` 保留手册定义的运行/停止状态相关语义；`DMAX` 使用 RAW，`fetch_waveform()` 仅在 acquisition 已经 STOP 时放行。driver 保存、逐字段回读并恢复 SOURCE、MODE、FORMAT、POINTS、START 与 STOP；不发送 STOP 或 AUTOSCALE。恢复失败或写入结果不明会锁存波形写域，后续调用必须关闭并重新打开会话。

长记录按不超过 250,000 点的 BYTE block 读取，每次调用的全部通道总计最多 4,000,000 点。`scope.options.max_chunk_points` 与 `scope.options.max_total_points` 可以向下收紧，不能突破上述硬上限。超出总点数预算会在分配数组和发送 binary query 前拒绝；每个 block 只调用一次核心 `query_bin_block()`，插件不解析或重放 TMC framing。

`capture_waveform(s)` 要求全部目标通道已经显示且时基为 MAIN。多通道调用只发送一次 `:SINGle`，随后轮询 `:TRIGger:STATus?` 直到 STOP，再逐通道读取并校验 X 轴一致；不使用 `*OPC?` 代替采集完成，不自动强制 STOP、RUN 或重新触发。超时或状态不明会锁存 acquisition 写域。当前不接受 `time_range_s` 或 `vertical_scale_v_per_div`，相关状态须预先配置；完成后仪器保持 SINGLE 自然结束的 STOP 状态。

```toml
[connection]
backend = "pyvisa"
resource = "TCPIP0::192.0.2.80::INSTR"

[scope]
driver = "rigol.mso8104"
default_channel = 1
check_errors = false
access = "read_write"

[scope.options]
max_total_points = 4000000
max_chunk_points = 250000

[waveform]
format = "real"
byte_order = "lsbf"
points = "def"
```

示例地址属于 RFC 5737 文档网段，不是实验室资源。

## 开发手册位置

本地厂商资料的具体放置规则见 [`doc/vendor-local/README.md`](doc/vendor-local/README.md)。
