# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

`0.9.0` 开发版本保留 MSO8104 身份与 CH1/CH2 高阻输入的受控实机证据，并在当前 WaveBench core 开发分支的有界二进制与 portability V2 合同下声明 `scope.fetch_waveform`、`scope.channel_input_state_v2`、`scope.measurement_statistics_v2`、`scope.fft_status_v2`、`scope.acquisition_status_v2`、`scope.digital_status_v2` 和 `scope.cursor_readout_v2`。waveform 入口当前只接受 `DEF`：精确声明 `LF` trailing、单响应和单操作均最多 `1,000` bytes、最多一次 binary query，并由 core 负责恢复和新鲜验证。input state V2 保留原始 coupling、termination 与阻抗；statistics V2 只接受显式 `item + sources`，以 6 条纯读取查询返回完整统计结果且拒绝 `include_buffer=True`；FFT V2 先确认 math slot 为 `FFT`，再读取 source、window、vertical unit 与起止频率；acquisition status V2 读取采集类型、采样率、存储深度，并仅在 AVER 模式下读取平均配置次数；digital status V2 先确认 LA 模块，再读取逐通道显示、标签、POD 阈值和共享显示状态；cursor V2 只读取预配置的全局手动 `TIME/AMPL` 光标。`scope.capture_waveform` 与 `scope.capture_waveforms` 继续暂停；见 [RFC-0008](doc/rfcs/0008-bounded-waveform-block-trailing-contract.md)。

实机结论只适用于记录的 MSO8104 固件 `00.02.02`、LAN/PyVISA 和受控步骤。在 `DEF + LF` profile 下，CH1 返回 `1.05713 Vpp / 1000 Hz`，CH2 返回 `1.0705 Vpp / 999.167 Hz`；`scope.measurement_statistics_v2` 对 `VPP,CHAN1` 和 `VPP,CHAN2` 均成功读取 6 个聚合字段，`CNT` 均为 `1000`；前面板预配置的 MATH1 FFT 返回 CH1、HANN、VRMS 与 `0–1 MHz`；当前采集状态返回 NORM、`500 kSa/s` 和 `10 kpts`；D0/D8 数字状态确认对应 POD、`1.4 V` 阈值、`0 s` timing calibration 与 `MEDIUM` size。两路均使用 `1 kHz / 1 Vpp / 0 V` 信号源，并在每次读取后独立确认两路输出关闭。该结果只证明记录条件下的数据换算、摘要、统计回包、FFT 状态回包、静态采集/数字状态回包与五字段恢复，不构成通用测量准确度、统计窗口语义、FFT 精度、平均完成、数字探头/逻辑活动、探头校准、MAX/DMAX 或 capture 的证据。

当前身份信息：

- distribution：`wavebench-rigol-mso8000`
- canonical driver ID：`rigol.mso8104`
- kind：`scope`
- 目标型号：`MSO8104`
- Python：`>=3.11`
- WaveBench：`>=0.8.24,<0.9`

本轮依赖的标准 waveform bounded API 与 portability V2 API 已提交到当前 core 开发分支，但尚未形成独立 core 发布版本。因此 `0.9.0` 仅用于开发与受控验收，不能据此发布兼容性 wheel。

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

- MSO8104 包测试：268 项通过；全仓 Ruff 通过。
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

当前不声明 legacy `scope.digital_status` 或 `scope.digital_waveform`。legacy 数字状态模型要求 MSO8000 无法查询的必填字段；数字 waveform 的厂商手册未定义 BYTE/WORD 逻辑 code，WORD 字节序也不明确。插件不以默认值或模拟量换算制造数字状态。

`scope.autoscale` 会按核心操作合同改变垂直、时基和触发设置。driver 先查询 `:SYSTem:AUToscale?`，禁用时不发送写命令；调用必须设置 `check_errors=false`。写入或 OPC 完成状态不确定时会锁存 autoscale 写域，关闭并重新打开会话前不再重试。该能力只有离线序列与故障注入证据，自动设置效果未实机验证。

`scope.math_metadata` 只接受已显示的 MATH1～MATH4 和 MAIN 时基。driver 保存六项 waveform 传输状态，按手册要求先切换到 NORM，再选择 MATH 源与 BYTE 格式，只查询 preamble 后恢复原状态；不读取波形数据。返回的 `values_per_sample` 为未知，Y 分辨率来自 BYTE 格式的 8 位合同。数学运算内容、FFT 精度和设备恢复均未实机验证。

`scope.cursor_readout` 保留兼容接口，只读取调用方确认已配置的全局手动光标，公共 `cursor_index` 固定为 `1`。新增的 `scope.cursor_readout_v2` 使用全局寻址，要求 `cursor_index=None`，可读取手动 `TIME/AMPL` 的独立 A/B source、秒/赫兹/角度/百分比或 source/百分比单位，以及 A、B、差值读数；driver 不移动或重配光标。追踪、XY、测量模式、NONE 和 LA 幅度仍默认拒绝。当前实机光标为 `VBA`，V2 在读取数值前拒绝；光标读数准确度仍未实机验证。

`scope.measurement_statistics_v2` 覆盖手册列出的统计 item，使用规范化的大写 item token 和显式 `CHAN1`～`CHAN4`、`MATH1`～`MATH4` source；`D0`～`D15` 仅接受手册明确允许的周期、频率、宽度、占空比、延时和相位项。延时与相位项必须给出两个 source，其他 item 必须给出一个 source。driver 只查询 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT，不发送统计配置、清零或显示写入。受控实机已确认 `VPP,CHAN1` 与 `VPP,CHAN2` 的 6 个数值字段和 `CNT=1000` 可读取；设备既有统计历史未被修改，因此平均、标准差、最小值和最大值不作为信号准确度或统计窗口语义的证据。legacy `scope.measurement_statistics` 继续不声明。

`scope.fft_status_v2` 只接受调用方已在前面板配置的 MATH1～MATH4 FFT。driver 先查询 `OPERator?` 并要求回包为 `FFT`，再读取 FFT source、window、vertical unit、起始频率和终止频率；所有步骤均为文本 query。`average_complete`、RBW 和 FFT sample rate 没有手册可证明的 query，因此固定列入 `unavailable_fields`，不会从全局 acquisition sample rate、频率范围或波形点数推导。受控实机 MATH1 已确认 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`，前后 source 两路均 OFF、`consistent`、`healthy`；该结果不构成 FFT 振幅、频率或频率轴准确度证据。

`scope.acquisition_status_v2` 固定读取 `:ACQuire:TYPE?`、`:ACQuire:SRATe?` 和 `:ACQuire:MDEPth?`；仅当 type 为 `AVER` 时才读取 `:ACQuire:AVERages?`。average 分区在非 AVER 模式下明确为 not applicable；AVER 模式下只报告配置次数，`average.complete` 仍为 unavailable。run state 和 segmented 分区没有进入 profile，不发送 `:TRIGger:STATus?`、`*OPC?`、`*STB?` 或 `*ESR?`，也不从 STOP 推导完成状态。受控实机当前返回 `NORM + 500 kSa/s + 10 kpts`；前后 source 两路均 OFF、`consistent`、`healthy`。legacy `scope.acquisition_status` 与所有采集控制、平均采集、单次/多通道 capture 仍不声明。

`scope.digital_status_v2` 只接受 D0～D15。每次先查询 LA 模块位；LA 缺席时只返回 `shared.module_present=false`，不会发送任何 `:LA:*?` 查询。LA 存在时，driver 以 6 条文本 query 读取逐通道显示和标签、所属 POD 的共享阈值、全局 timing calibration 与显示大小。`position_div` 因手册查询格式自相矛盾而保持 unavailable；`label_enabled`、activity、technology 和 hysteresis 也没有可证明查询，绝不以默认值或 UI 活动选择替代。受控实机的 D0、D8 都已确认显示、标签、各自 POD 边界与 `1.4 V` 阈值，以及 `0 s` timing calibration 和 `MEDIUM` size；前后 source 两路均 OFF、`consistent`、`healthy`。该结果不构成数字探头、电气阈值、逻辑活动或数字 waveform 编码的准确度证据。

`channel_coupling()` 联合查询通道耦合与输入阻抗，并把 `AC/DC + OMEG` 映射为核心高阻 token `ACL/DCL`，把 `AC/DC + FIFT` 映射为低阻 token `AC/DC`。新增 `scope.channel_input_state_v2` 不使用上述兼容 token，而是分别返回 `ac/dc/gnd`、`high_z/50_ohm` 和可证明阻抗。实机 CH1/CH2 均读为 `dc + high_z + 1 MΩ`。核心默认拒绝 50 Ω、`GND` 和未知状态。由于 `:SYSTem:ERRor?` 会消费队首且核心普通文本查询可能重放，当前不声明 `scope.errors`；调用后续波形 Service 时必须显式配置 `scope.check_errors=false`，直到 [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) 落地。

`scope.fetch_waveform` 的有界路径只支持 `DEF`。它使用 core 的 `query_binary()`，不再调用 legacy `query_bin_block()`；`LF` trailing、`1,000`-byte 上限和 no-replay 均由 descriptor profile 约束。在记录的 `1 kHz / 1 Vpp / 0 V` 信号源条件下，CH1 读取 `1.05713 Vpp / 1000 Hz`，CH2 读取 `1.0705 Vpp / 999.167 Hz`，每次均返回 1000 个样本并完成五字段 transfer-state restore 与新鲜验证。该证据不外推到 MAX、DMAX、单次/多通道 capture 或其他量程、时基和探头条件。

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
