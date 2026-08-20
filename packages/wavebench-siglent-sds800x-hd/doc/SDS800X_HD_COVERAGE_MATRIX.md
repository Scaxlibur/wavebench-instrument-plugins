# SDS800X HD 编程手册功能覆盖矩阵

[English](SDS800X_HD_COVERAGE_MATRIX_EN.md)

## 目的与证据边界

本矩阵将 SIGLENT《SDS 系列数字示波器编程手册》`CN11G` 与 WaveBench
`siglent.sds800x-hd` 外置插件对照。它用于区分手册声明、离线实现和实机验收，不把通用
SDS 命令自动视为 SDS800X HD 的可用能力。

本地手册因转换工具限制拆为三个目录，正文合计三个 `full.md`。原始转换内容保存在
`doc/vendor-local/`，由 Git 和 sdist 排除。手册支持表将 SDS800X HD 的最低固件列为
`1.1.3.1`，但没有逐条标注每个系列支持的命令；型号和固件仍需通过目标仪器确认。

当前证据标签：

- **实机已验收**：当前外置插件、目标 SDS800X HD 实机和受控测试证据同时存在。
- **已实现 / 离线验证**：该功能已有 driver 和 FakeTransport 测试，但尚无对应实机证据。
- **手册已审计**：命令格式和返回语义已核对，但尚未公开 capability。
- **核心接口阻塞**：厂商协议与 WaveBench 当前 transport 或公共模型不能完整对接。
- **实机阻塞**：离线代码不足以证明响应 framing、状态迁移或硬件差异。
- **默认拒绝**：命令会修改全局状态、写仪器存储或缺少可靠恢复边界。

通用接口缺口目前对应 `R1.1 Draft` RFC。这里的「核心接口阻塞」表示当前核心合同不足，
不是插件缺少一个可以私自补上的方法；RFC 预审不会改变主仓库，也不会扩大本插件的
descriptor capability。

## 当前覆盖

| 功能域 | 手册命令面 | WaveBench 映射 | 当前状态 | 边界与下一步 |
|---|---|---|---|---|
| 身份 | `*IDN?` | `scope.idn` | **SDS804X HD 实机已验收** | 四字段、厂商、型号、14 字符 ASCII 序列号和固件格式通过；其他型号待补 |
| 模拟通道耦合 | `:CHANnel<n>:COUPling?`，返回 `AC`、`DC` 或 `GND` | `scope.channel_coupling` | **SDS804X HD 实机已验收** | CH1–CH4 均返回 DC；二通道型号和其他 coupling 状态待补 |
| 输入阻抗 | 通用手册列出 `ONEMeg`、`FIFTy` | 无独立 capability | **默认拒绝** | SDS800X HD 专属产品资料说明固定 `1 MΩ`；不得把通用 `FIFTy` setter 外推到本系列 |
| 错误队列 | CN11G 未记录错误队列命令 | `scope.errors` | **设备协议阻塞** | 核心接口已经存在；本系列没有可依赖命令，不猜测 `SYSTem:ERRor?`，也不返回伪造的空列表 |
| 波形读取 | `SOURce`、`STARt`、`INTerval`、`POINt`、`MAXPoint?`、`WIDTh`、`BYTeorder`、`PREamble?`、`DATA?` | `scope.fetch_waveform` | **SDS804X HD 多块实机已验收** | Stop、sequence OFF、CH1/CH2 `DMAX`、WORD/LSB、数值和成功/异常恢复通过；`10M` 记录按 `5M + 5M` 两块读取通过，USB 待补 |
| Sequence 门禁 | `:ACQuire:SEQuence?` | `scope.fetch_waveform` 的前置条件 | **SDS804X HD 实机已验收** | `NORMAL` 触发模式下建立 Stop + sequence ON；driver 在任何 waveform 写入和 binary query 前拒绝 |
| 测量统计 | `:MEASure:MODE?`、`ADVanced:P<n>?`、`TYPE?`、`STATistics?`、`SHIStory?` | `scope.measurement_statistics` | **SDS804X HD 实机已验收** | 只读既有槽位；P3 `PKPK` 的 6 项统计和停止态 5 项历史通过，driver 零写入 |
| 单次与多通道采集 | `TRIGger:MODE`、`RUN`、`STOP`、`STATus?`、`ACQuire:NUMACq?` | `scope.capture_waveform`、`scope.capture_waveforms` | **SDS804X HD 实机已验收** | SINGLE 模式回读、Stop 轮询和采集计数通过；CH1/CH2 只执行一次 acquisition，不依赖 `*OPC?` |
| 触发运行状态 | `:TRIGger:STATus?` 返回 `Arm`、`Ready`、`Auto`、`Trig'd`、`Stop` 或 `Roll` | 无独立 capability | **核心接口阻塞** | 不能误映射为公共 `ScopeAcquisitionStatus`；跨仪器运行状态和控制见通用 RFC |
| 截图 | `:PRINt? PNG,NORMal` 或反色格式 | `scope.screenshot` | **核心接口阻塞；framing 实机确认** | 实机返回 `43628` 字节 raw PNG、无 IEEE block、IEND 后 1 个尾字节；核心缺 message-bounded binary，现有菜单参数也无法满足 |
| Autoset | `:AUToset` | `scope.autoscale` | **默认拒绝** | 同时修改触发、垂直和水平设置；没有错误队列和恢复闭环 |
| 采集状态 | `ACQuire:TYPE?`、`SEQuence?`、`NUMACq?` 等 | `scope.acquisition_status` | **核心模型不匹配** | 无法完整提供 `average_complete`、选件、容量和可用段数；运行阶段应使用独立模型 |
| Math / FFT | `FUNCtion<n>`、`OPERation?`、`SOURce?`、FFT scale/span 等 | `scope.math_metadata`、`scope.fft_status` | **核心模型不匹配** | 实机 F1–F4 均为 OFF；手册没有通用 FFT ready/RBW 合同，也不能把频率轴塞入模拟波形模型 |
| Snapshot、测量配置、数字与历史 | 多个通用 SDS 子系统 | 对应可选 Scope capability | **未覆盖** | 逐能力核对型号、选件、公共模型和恢复语义后再拆分 |
| Reset、系统和仪器文件系统 | `*RST`、系统设置、保存/调用、图片保存等 | 无基础 capability | **默认拒绝** | 可能改变全局状态、网络或持久存储，不纳入基础驱动 |

## 已确认的波形协议边界

`PREamble?` 返回 definite-length binary block，其 descriptor 固定部分为 346 bytes；sequence
数据可能在其后附加时间戳。当前纯解析器只支持非 sequence 模拟通道，因此要求核心去除
IEEE block envelope 后的 payload 恰好为 346 bytes，并显式拒绝附加时间戳，而不是静默
丢弃。`DATA?` 同样使用带声明长度的 binary block；核心 transport 按声明长度取 payload，
插件不能对二进制数据使用 `rstrip()`。

SDS804X HD 固件 `4.8.12.1.1.6.5` 的实机 preamble 进一步确认：非 sequence 记录返回
`read_frames=0`、`sum_frames=1`、`segment=-1`。手册示例使用的 `segment=1` 形式也保留；
其他帧组合继续拒绝。该固件的 WORD preamble 实测为 `100000` 点、`200000` bytes、
`50.000000584 ns` sample interval，和解析公式一致。补充长记录验收又确认 `10000000` 点、
`MAXPoint=5000000` 时按 `START 0` 和 `START 5000000` 完成两块读取。

首版模拟波形换算使用手册字段：

```text
vdiv = vertical_scale_raw * probe
offset = vertical_offset_raw * probe
voltage = raw_code * (vdiv / code_per_div) - offset
```

在 `STARt 0`、`INTerval 1` 下，时间轴为：

```text
x[i] = horizontal_delay - timebase * 10 / 2 + i * sample_interval
```

8-bit 样本按有符号整数解释；ADC 位数大于 8 时使用 `WORD`，明确设置 LSB，并按有符号
16-bit 解码。手册说明高分辨率数据左对齐、低位补零；首版不自行右移。单片上限必须查询
`MAXPoint?`，不能硬编码手册示例值。

公开的读取事务只接受 WaveBench `DMAX`。CN11G 第 385 页将 `WAVeform:POINt` 参数定义为
整数 NR1，没有 `DEF/MAX/DMAX` 仪器关键字；driver 使用厂商波形重构示例中的 `POINT 0`
选择完整记录。`DEF` 和 `MAX` 在任何 I/O 前拒绝，不能为了表面兼容发送无文档依据的命令。

事务先确认 `TRIGger:STATus? = Stop` 和 `ACQuire:SEQuence? = OFF`，再完整保存
`SOURCE/START/INTERVAL/POINT/WIDTH/BYTEorder`。读取期间固定 `WORD`、LSB、`START 0` 和
`INTERVAL 1`，由 preamble 给出总点数，由 `MAXPoint?` 给出单片点数。成功、协议错误或
transport 异常后均尝试恢复全部 transfer 状态；恢复失败不覆盖已有主异常。该流程不发送
`RUN`、`SINGLE` 或 `STOP`，只读取已经停止的记录。

## 与 WaveBench 核心的接口约束

- driver 只通过 `DriverContext.open_transport()` 获取核心 transport，并负责幂等关闭。
- capability 只在对应公共方法完整实现后声明；运行时的「方法可调用」校验不替代签名和语义测试。
- `fetch_waveform(channel, points="dmax", check_errors=True)` 必须返回核心
  `WaveformData` 和 `WaveformHeader`，不得在插件内复制同名模型。
- CN11G 没有错误队列，使用 waveform 时必须显式配置 `scope.check_errors=false`；直接调用
  driver 且 `check_errors=True` 时在任何 I/O 前失败。
- 当前 `points` 只支持 `DMAX`；公共签名仍保持
  `fetch_waveform(channel, points="dmax", check_errors=True)`，不伪造 `DEF/MAX` 映射。
- 多通道 capture 必须先配置全部通道，只触发一次 acquisition，再逐通道读取；不得逐通道重新触发。
- capture 使用 `DriverContext.opc_timeout_ms` 作为状态轮询 deadline，但不调用 `query_opc()`；
  `*OPC?` 不作为物理触发完成证据。
- 截图、独立采集运行控制、类型化 trace source 和三态错误检查的跨仪器方案见
  [scope 通用扩展接口 RFC](../../../doc/rfcs/WaveBench_scope通用扩展接口RFC.md)。该 RFC 为
  `R1.1 Draft`，不代表主仓库已经提供对应 capability。

## 开发顺序

1. M1：严格身份解析和只读 `scope.channel_coupling`，完成离线测试。
2. M2：346-byte preamble、数据换算和已停止模拟记录的 `scope.fetch_waveform` 已完成离线
   事务测试；M3 已补齐真实硬件证据。
3. M3：已在一台 SDS804X HD 上完成 TCPIP WORD/LSB 读取、CH1/CH2 数值、transfer 恢复、
   `10M` 真实多块读取和 sequence ON 安全拒绝；USB 路径和其他型号仍待补。
4. M4：SINGLE、Stop 轮询、采集计数和一次 CH1/CH2 acquisition 已完成实机验收；capture capability 已公开。
5. 截图、独立采集控制和 math/FFT 等待通用 RFC 评审；数字通道、sequence/history、Autoset
   和其他写能力分别立项，不经 raw SCPI 绕过门禁。

## 当前直接使用的 SCPI

```text
*IDN?
:CHANnel<n>:COUPling?
:CHANnel<n>:SWITch
:CHANnel<n>:SCALe
:TIMebase:SCALe
:TRIGger:MODE[?]
:TRIGger:RUN
:TRIGger:STOP
:TRIGger:STATus?
:ACQuire:NUMACq?
:ACQuire:SEQuence?
:MEASure:MODE?
:MEASure:ADVanced:P<n>?
:MEASure:ADVanced:P<n>:TYPE?
:MEASure:ADVanced:P<n>:STATistics?
:MEASure:ADVanced:P<n>:SHIStory?
:MEASure:ADVanced:STATistics?
:WAVeform:SOURce[?]
:WAVeform:START[?]
:WAVeform:INTerval[?]
:WAVeform:POINt[?]
:WAVeform:MAXPoint?
:WAVeform:WIDTH[?]
:WAVeform:BYTeorder[?]
:WAVeform:PREamble?
:WAVeform:DATA?
```

命令出现在矩阵中不等于已经由 descriptor 声明或由真实仪器验证。
