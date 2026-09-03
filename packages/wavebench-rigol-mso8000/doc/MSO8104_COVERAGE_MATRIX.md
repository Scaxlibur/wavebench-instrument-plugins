# MSO8104 编程手册功能覆盖矩阵

[English](MSO8104_COVERAGE_MATRIX_EN.md)

本页将 MSO8000 编程手册的功能域映射到外置 `wavebench-rigol-mso8000` 插件当前公开的
WaveBench capability。当前包版本、依赖和入口点以 [包元数据](../pyproject.toml)为准，型号、
capability、binary profile 和请求限制以
[production descriptor](../src/wavebench_rigol_mso8000/descriptor.py) 为准，精确 SCPI、解析与
恢复行为以 [driver](../src/wavebench_rigol_mso8000/driver.py) 为准。

[受控实机验收记录](MSO8104_HARDWARE_ACCEPTANCE.md)保存设备、固件、transport、测试条件、
具体结果和未验收范围；[功能覆盖里程碑](MSO8104_COVERAGE_MILESTONES.md)保存开发顺序与
历史决策。这些页面用于追溯，不会独立增加当前 capability。

## 范围

审计输入为 RIGOL MSO8000 编程手册 `PGA26006-1110`。手册覆盖 MSO8064、MSO8104 和
MSO8204，并经常使用 MSO8204 举例；production descriptor 只登记 MSO8104。因此，手册命令
和其他型号参数不能直接外推到当前插件。

本矩阵只回答「production descriptor 当前公开什么」以及「公开行为的边界是什么」。
手册命令、Python 方法、里程碑完成状态或一次实机成功都不能替代 descriptor 声明。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开 capability | 当前边界 |
|---|---|---|---|
| 身份 | `*IDN?` | `scope.idn` | 只匹配 descriptor 中登记的 MSO8104 identity pattern；不向其他型号或固件外推。 |
| 错误队列 | `:SYSTem:ERRor[:NEXT]?` | `scope.error_drain_v1` | 消费型读取标记为 `NO_REPLAY`；严格解析记录并以零错误终止。legacy `scope.errors` 未声明。 |
| 输入安全 | coupling、termination、impedance query | `scope.channel_coupling`、`scope.channel_input_state_v2` | legacy 返回 Core 高阻安全 token；V2 分开表达 coupling、termination 与阻抗。未知组合会失败。 |
| Autoscale | system autoscale enable 与 autoscale command | `scope.autoscale` | 会改变垂直、时基和触发且不承诺恢复；调用失败会锁停相应写入。 |
| 完整 legacy snapshot | channel、timebase、probe、waveform、trigger、health | 未声明 | 设备无法可靠提供公共模型的全部必填字段。 |
| Snapshot V2 | identity 与授权选件状态 | `scope.snapshot_v2` | 只读取 descriptor profile 声明的字段；其余 health、channel、timebase、probe、waveform 和 trigger 字段返回 unavailable。 |
| Acquisition 基础配置 | type、averages、depth、rate、run/stop/single | 作为 fetch／capture 前置状态使用 | 没有公开任意 acquisition 配置 setter。 |
| Legacy acquisition status | averages 与 trigger status | 未声明 | legacy 合同要求设备无法可靠证明的 average completion 与 segmented 状态。 |
| Acquisition status V2 | type、sample rate、memory depth、AVER count | `scope.acquisition_status_v2` | 只返回 descriptor profile 中可读或条件适用的字段；不从 STOP、OPC 或配置次数推导完成。 |
| Acquisition run state | `:TRIGger:STATus?` | `scope.acquisition_run_state` | 映射 stopped／waiting／acquiring／unknown；状态读取不证明 SINGLE 已完成。 |
| Acquisition control | `:RUN`、`:STOP`、`:SINGle` 与状态 query | `scope.acquisition_control` | 只公开 `start(normal)`、`stop` 和完成式 SINGLE；写入不会盲目重试，completion 不以 `*OPC?` 单独证明。 |
| Average capture | global acquisition type 与 average count | 未声明 | 当前插件不能可靠进入并证明平均采集完成。 |
| 当前屏幕波形 | NORM／BYTE／preamble／data | `scope.fetch_waveform` | 支持有界 `DEF` 读取；payload、轴参数和换算结果必须完整且为有限值。 |
| 深存储波形 | MAX／RAW 与分块 | `scope.fetch_waveform` | 只在确认 stopped 后读取 MAX／DMAX，并受 descriptor 的总点数、单块点数、响应大小和 query 数限制。 |
| 单次与多通道采集 | SINGLE、trigger status、逐 source waveform | `scope.capture_waveform`、`scope.capture_waveforms` | 只接受受支持的 MAIN／`DEF + BYTE` 基线；多通道只触发一次，再逐通道读取。恢复字段与预算由 descriptor 定义。 |
| Math 元数据 | MATH display 与 waveform preamble | `scope.math_metadata` | 只读取元数据，不读取 math data，也不声明运算内容或准确度。 |
| 光标读数 | mode、type、source、unit、value、delta | `scope.cursor_readout`、`scope.cursor_readout_v2` | legacy 保留窄的手动同源子集；V2 只接受 profile 支持的寻址、source 和单位组合，不移动光标。 |
| 截图 | image type 与 binary data | `scope.screenshot_profile`、`scope.screenshot_v2` | 只接受 descriptor 声明的 `png/device/device` 请求；设备返回内容在内存中严格校验并转换，不写设备文件或显示设置。 |
| Legacy digital status | module 与 LA status | 未声明 | 设备无法提供 legacy 模型要求的全部字段。 |
| Digital status V2 | module、display、label、threshold、timing calibration、size | `scope.digital_status_v2` | 先检查 LA module；模块不存在时不发送 LA query。只返回静态状态，不推断逻辑活动或 waveform 编码。 |
| Digital waveform | D0–D15 source 与 data | 未声明 | BYTE／WORD logic code 与 WORD 字节序没有足够的公开合同。 |
| 自动测量统计 | `:MEASure:STATistic:ITEM?` | `scope.measurement_statistics_v2` | 需要显式 item／source；不支持 buffer，不修改统计配置、清零或显示状态。 |
| FFT 状态 | MATH operator 与 FFT query | `scope.fft_status_v2` | 先确认 operator 为 FFT；只返回 profile 声明字段，不推导 average completion、RBW 或 FFT sample rate。 |
| Reference 元数据 | source、vertical scale／offset、label | 未声明 | 当前手册与设备接口不能完整表达轴、点数和 Y resolution。 |
| History 时间戳 | record state、frame 与 timestamp | 未声明 | 帧号不能替代逐帧相对或日历时间戳。 |
| DVM、counter、AWG | 对应厂商命令族 | 未声明 | 当前 Scope 合同或共享资源模型不足，不通过 raw SCPI 绕过。 |
| Protocol、mask、search、record | 选件相关命令族 | 未声明 | 需要独立的选件、状态恢复和结果模型。 |
| reset、网络、选件安装、文件系统、校准 | system 与 storage 命令 | 未声明 | 属于高副作用维护操作，默认不进入普通实验流程。 |

## Binary profile 边界

精确 response／operation budget、query 上限、trailing bytes、restore order 和 screenshot variant
由 [production descriptor](../src/wavebench_rigol_mso8000/descriptor.py) 的
`ScopeDescriptorExtensions` 定义。文档不维护第二份数值表。

- `fetch`、`capture_single` 和 `capture_multiple` 使用彼此独立的 waveform operation profile。
- `capture_multiple` 只触发一次采集，再读取多个通道；不能逐通道重新触发。
- Screenshot 使用 `DEFINITE_BLOCK` framing；不修改 image type、菜单、颜色或设备文件。
- `tcpip`、`usb` 和 `gpib` resource scheme 只表示路由合同，不表示每种连接都已有实机证据。

## 波形换算合同

BYTE 波形使用手册定义的 10 字段 preamble：

```text
format,type,points,count,xincrement,xorigin,xreference,yincrement,yorigin,yreference
```

driver 按以下公式生成公共 `WaveformData`：

```text
voltage = (raw - y_origin - y_reference) * y_increment
x_start = x_origin - x_reference * x_increment
x_stop  = x_start + (points - 1) * x_increment
```

payload 必须与点数精确一致；所有轴参数与换算结果必须为有限值。Core transport 负责
IEEE／TMC block framing，插件不重复解析 `#N<length>` 头。

## 相关来源

- [Production descriptor](../src/wavebench_rigol_mso8000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_mso8000/driver.py)
- [受控实机验收与未验收范围](MSO8104_HARDWARE_ACCEPTANCE.md)
- [开发里程碑与历史决策](MSO8104_COVERAGE_MILESTONES.md)
- [相关 RFC](rfcs/README.md)
