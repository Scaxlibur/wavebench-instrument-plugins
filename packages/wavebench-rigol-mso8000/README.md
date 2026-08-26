# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

`0.9.0` 开发版本在当前 WaveBench Core 开发分支的有界二进制与 portability V2 合同下声明 `scope.error_drain_v1`、`scope.fetch_waveform`、`scope.capture_waveform`、`scope.capture_waveforms`、`scope.acquisition_control`、`scope.channel_input_state_v2`、`scope.measurement_statistics_v2`、`scope.fft_status_v2`、`scope.acquisition_status_v2`、`scope.acquisition_run_state`、`scope.digital_status_v2`、`scope.snapshot_v2` 和 `scope.cursor_readout_v2`。waveform 入口支持 `DEF`、停止态 `MAX` 与停止态 `DMAX`；descriptor 精确声明 `LF` trailing、单响应最多 `250,000` bytes、单操作最多 `4,000,000` bytes 与最多 16 次 binary query。`scope.capture_waveform` 和 `scope.capture_waveforms` 仅接受已停止、MAIN 时基下的 `DEF + BYTE` 基线；单通道最多 1 次、双通道最多 4 次 binary query，均由 Core 恢复并新鲜验证 acquisition、trigger、时基、四路 display/vertical 与 transfer 的 13 个字段。SINGLE 写入后必须读回 `SING`：首条 `STOP` 使用受限 completion proof，`WAIT` 或 `TD` 到 `STOP` 使用状态迁移 proof；capture 仅接受后者作为波形新鲜性证据。

实机结论只适用于记录的 MSO8104 固件 `00.02.02`、LAN/PyVISA 和受控步骤。单通道和双通道 bounded `DEF + BYTE` capture 都在 1 Vpp 安全限制内返回每通道 `1,000` 样本并具备有效幅度；两者均观察到 `WAIT → STOP`，恢复后 `*OPC?` 由 `0` 轮询至 `1`，随后完成 Core 的 13 字段新鲜验证。`TD → STOP` 已在独立的 SINGLE control 验收中观察到。每轮结束均以新会话确认 source CH1/CH2 OFF、scope STOP、CH1/CH2 为 high_z。此前 `DEF + LF` fetch、停止态 MAX/DMAX、统计、FFT、静态 acquisition/digital 状态与 snapshot 的受限实机证据保持有效。该结果不外推到运行态 MAX、其他点数、时基、通道组合、transport 或一般测量准确度。

采集控制的实机边界仍受限：`start(normal)`→`stop` 已形成 active/stopped 过程；SINGLE 在模式读回为 `SING` 后，首条 `STOP` 和 `WAIT/TD → STOP` 都已完成受控验证。`*OPC?` 只用于 capture 恢复写批次的通信同步，不能替代 SINGLE completion 或波形新鲜性证明。

平均采集仍不声明。受控 `capture_average_v2` 探测在已停止、高阻、1 Vpp 方波条件下，对 `:ACQuire:TYPE AVERages`、其合法缩写 `AVER` 以及 PEAK/NORM 对照均完成有界写入同步后立即读回 type；设备始终返回 `NORM`，且随后读取的错误队列为 `0,"No error"`。因此当前固件／配置无法通过远程接口进入平均模式；即使该前提解决，手册也没有把 trigger STOP、`*OPC?` 或 preamble count 绑定为平均完成。正式 descriptor 不声明 `scope.capture_average_v2`。

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

- MSO8104 包测试：390 项通过；全仓 Ruff 通过。
- 根测试：在一次性同级 WaveBench core 布局中 715 项通过，2 项 SP3000A 私有实机证据测试按预期跳过。
- 当前 WaveBench `0.8.24` 开发环境的 package check：源码目录和真实 wheel 均通过。
- wheel/sdist：唯一仪器 entry point、WaveBench runtime dependency、MIT 许可证和公开内容符合合同；vendor-local 未进入制品。
- 一次性虚拟环境：安装、零 I/O descriptor 发现、卸载和 canonical ID fallback 通过。
- 文档：61 个受跟踪 Markdown 文件的本地链接有效。

这些结果只证明离线合同与发行完整性，不构成型号、固件、transport、吞吐、恢复或测量准确度的实机证据。

## 安全边界

descriptor 导入不得打开 transport、扫描端口、发送 SCPI 或创建文件。真实资源、序列号、凭据、波形、截图和命令日志不得提交。仪器写入和 acquisition trigger 不做盲目重试。核心缺少必要安全接口时，先写 RFC 并跳过对应 capability，不在插件中增加 raw SCPI 入口。

当前 descriptor 允许 `tcpip`、`usb`、`gpib` 资源前缀，这是手册声明和离线路由合同，不是连接实机通过的证据。

已受控声明 `scope.screenshot_profile` 与 `scope.screenshot_v2`。profile 固定单次 binary query、`DEFINITE_BLOCK`、精确 `LF` transport trailing、`8,388,608`-byte 上限与 `png/device/device`。driver 先只读确认 `:SAVE:IMAGe:TYPE? = PNG`，再读取 `:SAVE:IMAGe:DATA?`；记录固件实际返回无压缩 BMP24，driver 仅接受该严格子集并在内存中转换为 PNG。公开实机调用返回 `1024 × 600`、`47,584` bytes 的 `image/png`，前后错误队列均为空，session healthy；最终 source 双路 OFF、scope STOP、CH1/CH2 high_z。不写 `TYPE`、`INVert`、`COLor`、菜单或设备文件，也不使用 `:DISPlay:DATA?`。该证据不外推到截图视觉／像素准确度、其他屏幕状态或最大 payload；详见 [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md)。

当前不声明 legacy `scope.digital_status` 或 `scope.digital_waveform`。legacy 数字状态模型要求 MSO8000 无法查询的必填字段；数字 waveform 的厂商手册未定义 BYTE/WORD 逻辑 code，WORD 字节序也不明确。插件不以默认值或模拟量换算制造数字状态。

`scope.autoscale` 会按核心操作合同改变垂直、时基和触发设置，且不承诺恢复。driver 先查询 `:SYSTem:AUToscale?`，禁用时不发送写命令；调用必须设置 `check_errors=false`。对 MSO8104，遗留参数 `wait_opc=true` 明确定义为固定 `3 s` settle：写入一次 `:AUToscale` 后等待 `3 s`，不查询 `*OPC?`，随后将本次操作视为完成。写入或 settle 等待异常都会锁存 autoscale 写域，关闭并重新打开会话前不再重试。受控 CH1 `1 Vpp / 1 kHz` probe 经公开 autoscale 后的 bounded fetch 返回 1000 样本且幅度有效，最终 source 双路 OFF、scope STOP、CH1/CH2 high_z。该固定时长是本插件的运行完成策略，不证明设备内部自动设置算法、显示效果或设置恢复；`wait_opc=false` 仅显式跳过等待，尚无实机完成验收。

`scope.math_metadata` 只接受已显示的 MATH1～MATH4 和 MAIN 时基。driver 保存六项 waveform 传输状态，按手册要求先切换到 NORM，再选择 MATH 源与 BYTE 格式，只查询 preamble 后恢复原状态；不读取波形数据。记录的 MATH1 调用已返回 1000 点、有限轴和 8 位 BYTE 元数据，并完成六字段最终恢复复核。返回的 `values_per_sample` 仍为未知；数学运算内容、其他槽位／operator 的轴语义和 FFT 精度不由该能力推断。

`scope.cursor_readout` 保留兼容接口，只读取调用方确认已配置的全局手动光标，公共 `cursor_index` 固定为 `1`。`scope.cursor_readout_v2` 使用全局寻址，要求 `cursor_index=None`；除手动 `TIME/AMPL` 外，还读取预配置的 `TRAC` 追踪光标。公开实机的 `MAN + TIME + CHAN1/CHAN1` 已返回有限 X A/B、`ΔX` 与 `1/ΔX`，单位分别为秒和 Hz。追踪路径仅接受 `MAIN/ROLL` 时基和 `CHAN1`～`CHAN4`，读取 A/B source、时基、通道幅度单位和 A/B/差值；当前 `TRAC + CHAN2/CHAN2` 返回全部有限读数与 `V` 纵轴单位。仅当 A/B 纵轴单位相同且已知时才读取 `ΔY`，否则将其标为 not applicable。driver 不移动或重配光标。Math source、XY、测量模式、`NONE`、LA 和未知或不同的纵轴单位保持 fail closed，光标读数准确度仍未验证。

`scope.measurement_statistics_v2` 覆盖手册列出的统计 item，使用规范化的大写 item token 和显式 `CHAN1`～`CHAN4`、`MATH1`～`MATH4` source；`D0`～`D15` 仅接受手册明确允许的周期、频率、宽度、占空比、延时和相位项。延时与相位项必须给出两个 source，其他 item 必须给出一个 source。driver 只查询 CURRENT、AVERages、DEViation、MINimum、MAXimum 与 CNT，不发送统计配置、清零或显示写入。受控实机已确认 `VPP,CHAN1` 与 `VPP,CHAN2` 的 6 个数值字段和 `CNT=1000` 可读取；设备既有统计历史未被修改，因此平均、标准差、最小值和最大值不作为信号准确度或统计窗口语义的证据。legacy `scope.measurement_statistics` 继续不声明。

`scope.fft_status_v2` 只接受调用方已在前面板配置的 MATH1～MATH4 FFT。driver 先查询 `OPERator?` 并要求回包为 `FFT`，再读取 FFT source、window、vertical unit、起始频率和终止频率；所有步骤均为文本 query。`average_complete`、RBW 和 FFT sample rate 没有手册可证明的 query，因此固定列入 `unavailable_fields`，不会从全局 acquisition sample rate、频率范围或波形点数推导。受控实机 MATH1 已确认 `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`，前后 source 两路均 OFF、`consistent`、`healthy`；该结果不构成 FFT 振幅、频率或频率轴准确度证据。

`scope.acquisition_status_v2` 固定读取 `:ACQuire:TYPE?`、`:ACQuire:SRATe?` 和 `:ACQuire:MDEPth?`；仅当 type 为 `AVER` 时才读取 `:ACQuire:AVERages?`。average 分区在非 AVER 模式下明确为 not applicable；AVER 模式下只报告配置次数，`average.complete` 仍为 unavailable。run state 和 segmented 分区没有进入 profile，不发送 `:TRIGger:STATus?`、`*OPC?`、`*STB?` 或 `*ESR?`，也不从 STOP 推导完成状态。受控实机当前返回 `NORM + 500 kSa/s + 10 kpts`；后续平均模式写入探测也始终回读 `NORM`，所以 AVER 分支继续没有实机可达性证据。前后 source 两路均 OFF、`consistent`、`healthy`。legacy `scope.acquisition_status` 与平均采集仍不声明。

`scope.acquisition_run_state` 只读取 `:TRIGger:STATus?`：`STOP` 映射为 stopped，`WAIT` 映射为 waiting，`RUN` 和记录条件下经 STOP 验证的 `AUTO` 映射为 acquiring；通常 `TD` 保持 unknown。仅在刚完成 `SING` 模式读回的 SINGLE 事务中，`TD` 被保守表示为非终态 arming，并且必须后续读到 `STOP` 才能构成 state-transition proof。`scope.acquisition_control` 已声明；它支持 `start(normal)`、`stop` 与受限 SINGLE completion。bounded capture 与 control proof 相互独立：capture 不接受首条 STOP，仍要求 `WAIT/TD → STOP`，并恢复和新鲜验证 13 个字段。运行态 MAX、其他 capture 点数/时基/通道组合仍未验收。

`scope.digital_status_v2` 只接受 D0～D15。每次先查询 LA 模块位；LA 缺席时只返回 `shared.module_present=false`，不会发送任何 `:LA:*?` 查询。LA 存在时，driver 以 6 条文本 query 读取逐通道显示和标签、所属 POD 的共享阈值、全局 timing calibration 与显示大小。`position_div` 因手册查询格式自相矛盾而保持 unavailable；`label_enabled`、activity、technology 和 hysteresis 也没有可证明查询，绝不以默认值或 UI 活动选择替代。受控实机的 D0、D8 都已确认显示、标签、各自 POD 边界与 `1.4 V` 阈值，以及 `0 s` timing calibration 和 `MEDIUM` size；前后 source 两路均 OFF、`consistent`、`healthy`。该结果不构成数字探头、电气阈值、逻辑活动或数字 waveform 编码的准确度证据。

`scope.snapshot_v2` 只接受 CH1～CH4 请求，但当前 profile 只读当前 identity 与授权选件状态：先执行 `*IDN?`，再按手册枚举读取 13 种 `:SYSTem:OPTion:STATus? <type>`。空 options 仅在本次全部 13 项都明确返回未安装时出现；不从 descriptor、缓存或型号常量补齐。health、channel、timebase、probe、waveform 和 trigger 的 55 个字段均按稳定顺序列为 unavailable。受控实机完成全部 14 条 query；前后 source 两路均 OFF、`consistent`、`healthy`。该能力不读取状态寄存器、错误队列、trigger、波形或二进制数据，也不构成各未读分区的状态或准确度证据。

`scope.error_drain_v1` 对 `:SYSTem:ERRor?` 的每次读取都显式使用 Core 的 `ReplayPolicy.NO_REPLAY`，并严格解析 `<integer>,"<message>"`；`0,"No error"` 是已实机观察的唯一终止记录，非零记录、格式异常和队列 overflow 都 fail closed。Core 对有界 fetch/capture 在 `scope.check_errors=true` 时于主操作前后执行有限 drain，并核对实际 query 数。受控实机的公开单通道 capture 在此前后各完成一次空队列 drain，仍返回 1000 样本并恢复安全状态。非空记录和 overflow 目前只有离线故障注入证据。legacy `scope.errors` 仍不声明；autoscale 等旧路径仍必须使用 `check_errors=false`。

`scope.fetch_waveform` 的有界路径支持 `DEF`、停止态 `MAX` 与停止态 `DMAX`。它使用 Core 的 `query_binary()`，不再调用 legacy `query_bin_block()`；`LF` trailing、`250,000`-byte 单响应上限、`4,000,000`-byte 单操作上限、最多 16 次 binary query 与 no-replay 均由 descriptor profile 约束。MAX/DMAX 在任何 transfer setup 前都要求 scope 已停止。该 fetch 证据不外推到运行态 MAX、其他量程、时基、深度和探头条件；受限 capture 的独立验收见上文。

离线设计仍保留每块 `250,000` 点、每次调用总计 `4,000,000` 点、最多 16 块的长记录边界。停止态 MAX/DMAX fetch 与 bounded 单／多通道 capture 已有各自受限实机证据；运行态 MAX、其他 capture 点数、时基、通道组合和 transport 仍需要独立验收。

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
