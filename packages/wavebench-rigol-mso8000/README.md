# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

`0.9.0` 开发版本保留 MSO8104 身份与 CH1/CH2 高阻输入的受控实机证据，并在当前 WaveBench core 工作树的有界二进制合同下声明 `scope.fetch_waveform`。该入口当前只接受 `DEF`：精确声明 `LF` trailing、单响应和单操作均最多 `1,000` bytes、最多一次 binary query，并由 core 负责恢复和新鲜验证。`scope.capture_waveform` 与 `scope.capture_waveforms` 继续暂停；见 [RFC-0008](doc/rfcs/0008-bounded-waveform-block-trailing-contract.md)。

实机结论只适用于记录的 MSO8104 固件 `00.02.02`、LAN/PyVISA 和受控步骤。CH1 `DEF` 的 block 读取与 core-owned transfer-state restore 已通过；但返回读数与已启用的 `1 kHz / 1 Vpp` source 不符，频率、Vpp、X/Y 换算和测量准确度仍未获得信号源闭环证据。

当前身份信息：

- distribution：`wavebench-rigol-mso8000`
- canonical driver ID：`rigol.mso8104`
- kind：`scope`
- 目标型号：`MSO8104`
- Python：`>=3.11`
- WaveBench：`>=0.8.24,<0.9`

本轮依赖的标准 waveform bounded API 尚在当前 core 工作树中，尚未形成独立 core 发布版本。因此 `0.9.0` 仅用于开发与受控验收，不能据此发布兼容性 wheel。

## 目录说明

- `doc/vendor-local/`：本地厂商手册。原始 PDF 和转换后的 Markdown 都放在这里；除说明文件外的内容会被 Git 忽略，也不会进入发行包。
- `src/wavebench_rigol_mso8000/`：descriptor、driver 与严格解析器。
- `tests/`：FakeTransport、故障注入与制品生命周期测试；默认测试不得连接真实仪器。
- `pyproject.toml`：distribution 元数据、WaveBench 版本范围和唯一 entry point。
- `doc/`：公开覆盖矩阵和验收记录；厂商原文不要放到公开文档目录。

## 设计文档

- [MSO8104 功能覆盖里程碑](doc/MSO8104_COVERAGE_MILESTONES.md)
- [MSO8104 编程手册功能覆盖矩阵](doc/MSO8104_COVERAGE_MATRIX.md)
- [MSO8104 受控实机验收记录](doc/MSO8104_HARDWARE_ACCEPTANCE.md)

## M8 离线发行证据

- MSO8104 包测试：171 项通过；全仓 Ruff 通过。
- 根测试：在一次性同级 WaveBench core 布局中 715 项通过，2 项 SP3000A 私有实机证据测试按预期跳过。
- 当前 WaveBench `0.8.24` 开发环境的 package check：源码目录和真实 wheel 均通过。
- wheel/sdist：唯一仪器 entry point、WaveBench runtime dependency、MIT 许可证和公开内容符合合同；vendor-local 未进入制品。
- 一次性虚拟环境：安装、零 I/O descriptor 发现、卸载和 canonical ID fallback 通过。
- 文档：61 个受跟踪 Markdown 文件的本地链接有效。

这些结果只证明离线合同与发行完整性，不构成型号、固件、transport、吞吐、恢复或测量准确度的实机证据。

## 安全边界

descriptor 导入不得打开 transport、扫描端口、发送 SCPI 或创建文件。真实资源、序列号、凭据、波形、截图和命令日志不得提交。仪器写入和 acquisition trigger 不做盲目重试。核心缺少必要安全接口时，先写 RFC 并跳过对应 capability，不在插件中增加 raw SCPI 入口。

当前 descriptor 允许 `tcpip`、`usb`、`gpib` 资源前缀，这是手册声明和离线路由合同，不是连接实机通过的证据。

当前不声明 `scope.screenshot`。`:DISPlay:DATA?` 的手册段落没有声明 TMC block framing，`:SAVE:IMAGe:DATA?` 虽为 TMC block，却不能证明返回图片满足核心 `include_menu=False` 合同。具体缺口见 [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md)；插件不猜测 framing、不忽略参数，也不创建仪器文件。

当前也不声明 `scope.digital_status` 或 `scope.digital_waveform`。数字状态的核心模型要求 MSO8000 无法查询的必填字段，见 [RFC-0004](doc/rfcs/0004-portable-scope-digital-status.md)；数字 waveform 的厂商手册未定义 BYTE/WORD 逻辑 code，WORD 字节序也不明确。插件不以默认值或模拟量换算制造数字状态。

`scope.autoscale` 会按核心操作合同改变垂直、时基和触发设置。driver 先查询 `:SYSTem:AUToscale?`，禁用时不发送写命令；调用必须设置 `check_errors=false`。写入或 OPC 完成状态不确定时会锁存 autoscale 写域，关闭并重新打开会话前不再重试。该能力只有离线序列与故障注入证据，自动设置效果未实机验证。

`scope.math_metadata` 只接受已显示的 MATH1～MATH4 和 MAIN 时基。driver 保存六项 waveform 传输状态，按手册要求先切换到 NORM，再选择 MATH 源与 BYTE 格式，只查询 preamble 后恢复原状态；不读取波形数据。返回的 `values_per_sample` 为未知，Y 分辨率来自 BYTE 格式的 8 位合同。数学运算内容、FFT 精度和设备恢复均未实机验证。

`scope.cursor_readout` 只读取调用方确认已配置的全局手动光标，公共 `cursor_index` 固定为 `1`。当前仅接受 A/B 同源的 `TIME + SEC` 或 `AMPL + SOUR`：前者返回 X 差和倒数，后者返回 Y 差。追踪、XY、测量模式、双源、NONE、LA 幅度以及 Hz、角度、百分比单位均默认拒绝；driver 不移动或重配光标。读数准确度未实机验证。

`channel_coupling()` 联合查询通道耦合与输入阻抗，并把 `AC/DC + OMEG` 映射为核心高阻 token `ACL/DCL`，把 `AC/DC + FIFT` 映射为低阻 token `AC/DC`。核心默认拒绝 50 Ω、`GND` 和未知状态。由于 `:SYSTem:ERRor?` 会消费队首且核心普通文本查询可能重放，当前不声明 `scope.errors`；调用后续波形 Service 时必须显式配置 `scope.check_errors=false`，直到 [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) 落地。

`scope.fetch_waveform` 的有界路径只支持 `DEF`。它使用 core 的 `query_binary()`，不再调用 legacy `query_bin_block()`；`LF` trailing、`1,000`-byte 上限和 no-replay 均由 descriptor profile 约束。CH1 已成功读取 1000 个样本，core 也完成五字段 transfer-state restore 与新鲜验证；但读数约为 `5.25 mVpp / 8.89 kHz`，不能作为 `1 Vpp / 1 kHz` source 的闭环结果。MAX、DMAX、CH2 和双通道结论均不从本轮外推。

离线设计仍保留每块 `250,000` 点、每次调用总计 `4,000,000` 点的长记录边界。MAX、DMAX、单次和多通道 capture 需要各自的有界 profile 与 acquisition 恢复证据，当前不构成公开能力或实机采集结论。

```toml
[connection]
backend = "pyvisa"
resource = "TCPIP0::192.0.2.80::INSTR"

[scope]
driver = "rigol.mso8104"
default_channel = 1
check_errors = false
access = "read_write"

```

示例地址属于 RFC 5737 文档网段，不是实验室资源。

## 开发手册位置

本地厂商资料的具体放置规则见 [`doc/vendor-local/README.md`](doc/vendor-local/README.md)。
