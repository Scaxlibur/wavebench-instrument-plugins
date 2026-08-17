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

- **已实现 / 离线验证**：driver 和 FakeTransport 测试存在，尚无真实 SDS800X HD 证据。
- **手册已审计**：命令格式和返回语义已核对，但尚未公开 capability。
- **核心接口阻塞**：厂商协议与 WaveBench 当前 transport 或公共模型不能完整对接。
- **实机阻塞**：离线代码不足以证明响应 framing、状态迁移或硬件差异。
- **默认拒绝**：命令会修改全局状态、写仪器存储或缺少可靠恢复边界。

## 当前覆盖

| 功能域 | 手册命令面 | WaveBench 映射 | 当前状态 | 边界与下一步 |
|---|---|---|---|---|
| 身份 | `*IDN?` | `scope.idn` | **已实现 / 离线验证** | 严格四字段、厂商和型号校验仍需脱敏实机样本确认 |
| 模拟通道耦合 | `:CHANnel<n>:COUPling?`，返回 `AC`、`DC` 或 `GND` | `scope.channel_coupling` | **已实现 / 离线验证** | 按二通道或四通道型号限制 `<n>`，未知响应直接拒绝；实机验收待补 |
| 输入阻抗 | 通用手册列出 `ONEMeg`、`FIFTy` | 无独立 capability | **默认拒绝** | SDS800X HD 专属产品资料说明固定 `1 MΩ`；不得把通用 `FIFTy` setter 外推到本系列 |
| 错误队列 | CN11G 未记录错误队列命令 | `scope.errors` | **未覆盖** | 不猜测 `SYSTem:ERRor?`；消费型查询也不适合核心普通 query 的自动重试 |
| 波形读取 | `SOURce`、`STARt`、`INTerval`、`POINt`、`MAXPoint?`、`WIDTh`、`BYTeorder`、`PREamble?`、`DATA?` | `scope.fetch_waveform` | **已实现 / 离线验证** | 仅支持 Stop、sequence OFF、模拟通道和 `DMAX`；分块、精确长度、失败恢复和核心服务已有离线测试，实机一致性待验 |
| 单次与多通道采集 | `TRIGger:MODE`、`RUN`、`STOP`、`STATus?`、`*OPC?` | `scope.capture_waveform`、`scope.capture_waveforms` | **实机阻塞** | 手册未保证 `RUN` 后 `*OPC?` 等待真实触发完成；多通道必须一次 acquisition 后逐通道读取 |
| 触发运行状态 | `:TRIGger:STATus?` 返回 `Arm`、`Ready`、`Auto`、`Trig'd`、`Stop` 或 `Roll` | 无独立 capability | **手册已审计** | 不能误映射为公共 `ScopeAcquisitionStatus`；后者描述平均和分段采集状态 |
| 截图 | `:PRINt? PNG,NORMal` 或反色格式 | `scope.screenshot` | **核心接口阻塞 / 实机阻塞** | 手册示例按原始图片字节读取，核心仅提供 definite-block query；命令也没有可靠的菜单开关 |
| Autoset | `:AUToset` | `scope.autoscale` | **默认拒绝** | 同时修改触发、垂直和水平设置；没有错误队列和恢复闭环 |
| 采集状态 | `ACQuire:TYPE?`、`SEQuence?`、`NUMACq?` 等 | `scope.acquisition_status` | **未覆盖** | 无法完整提供 `average_complete`、选件、容量和可用段数，不能拼造公共模型 |
| Snapshot、测量、数字、历史与分析 | 多个通用 SDS 子系统 | 对应可选 Scope capability | **未覆盖** | 逐能力核对型号、选件、公共模型和恢复语义后再拆分 |
| Reset、系统和仪器文件系统 | `*RST`、系统设置、保存/调用、图片保存等 | 无基础 capability | **默认拒绝** | 可能改变全局状态、网络或持久存储，不纳入基础驱动 |

## 已确认的波形协议边界

`PREamble?` 返回 definite-length binary block，其 descriptor 固定部分为 346 bytes；sequence
数据可能在其后附加时间戳。当前纯解析器只支持非 sequence 模拟通道，因此要求核心去除
IEEE block envelope 后的 payload 恰好为 346 bytes，并显式拒绝附加时间戳，而不是静默
丢弃。`DATA?` 同样使用带声明长度的 binary block；核心 transport 按声明长度取 payload，
插件不能对二进制数据使用 `rstrip()`。

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
- 当前核心 PyVISA 没有把独立 `opc_timeout_ms` 应用于 `query_opc()`，因此 acquisition 暂不声明
  独立 OPC 超时保证。

## 开发顺序

1. M1：严格身份解析和只读 `scope.channel_coupling`，完成离线测试。
2. M2：346-byte preamble、数据换算和已停止模拟记录的 `scope.fetch_waveform` 已完成离线
   事务测试；真实硬件证据仍为空。
3. M3：取得 TCPIP 与 USB 的脱敏二进制响应样本，确认分片、WORD 对齐、时基和 transfer
   设置恢复。
4. M4：单独验证触发状态迁移、OPC 等待和一次多通道 acquisition，再评估 capture capability。
5. 截图、数字通道、FFT、sequence/history、Autoset 和写能力分别立项，不经 raw SCPI 绕过门禁。

## 当前直接使用的 SCPI

```text
*IDN?
:CHANnel<n>:COUPling?
:TRIGger:STATus?
:ACQuire:SEQuence?
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
