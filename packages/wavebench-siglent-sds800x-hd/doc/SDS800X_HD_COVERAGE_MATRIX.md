# SDS800X HD 编程手册功能覆盖矩阵

[English](SDS800X_HD_COVERAGE_MATRIX_EN.md)

本页将 SIGLENT SDS 系列编程手册 `CN11G` 的功能域映射到外置
`wavebench-siglent-sds800x-hd` 插件当前公开的 WaveBench capability。当前包版本、依赖和
入口点以 [包元数据](../pyproject.toml)为准，型号、resource scheme、配置字段和 capability 以
[production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py) 为准，截图和采集控制
边界以 [profiles](../src/wavebench_siglent_sds800x_hd/profiles.py) 为准，精确 SCPI 与事务行为以
[driver](../src/wavebench_siglent_sds800x_hd/driver.py) 为准。

[功能覆盖开发路线](SDS800X_HD_COVERAGE_MILESTONES.md)记录阶段状态和后续退出门；
[实机验收记录](SDS800X_HD_HARDWARE_ACCEPTANCE.md)与
[Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md)保存特定设备、固件、transport 和
步骤的证据。这些页面用于追溯，不会独立增加当前 capability。

## 范围

`CN11G` 是多个 SDS 系列共用的编程手册，没有逐条标注每个命令适用的系列。通用手册命令
不能自动视为 SDS800X HD 能力。本地转录只用于内部审计，位于 Git 忽略且不进入 sdist 的
`doc/vendor-local/`。

本矩阵只回答「production descriptor 当前公开什么」以及「公开行为的边界是什么」。Core
增加公共合同、Python 方法存在、离线测试或一次实机成功，都不能替代 descriptor 声明。

## 功能覆盖

| 功能域 | 手册命令面 | 当前公开 capability | 当前边界 |
|---|---|---|---|
| 身份 | `*IDN?` | `scope.idn` | 严格解析四字段 identity，并按 descriptor 登记型号验证通道数。未知厂商、型号或格式会失败。 |
| 模拟通道 coupling | `:CHANnel<n>:COUPling?` | `scope.channel_coupling` | 只接受 `AC`、`DC` 或 `GND`；具体通道上限由 identity 型号决定。该系列输入阻抗策略为固定高阻。 |
| 输入阻抗写入 | 共用手册中的 `ONEMeg`、`FIFTy` | 未声明 | 不把其他 SDS 系列的 `FIFTy` setter 外推到本系列。 |
| 错误队列 | `CN11G` 未记录可靠 query | 未声明 | 不猜测 `SYSTem:ERRor?`，也不返回伪造的空列表；波形操作要求 `check_errors=false`。 |
| 已停止记录读取 | waveform source、range、format、preamble、data | `scope.fetch_waveform` | 只接受 `points="dmax"` 和 `check_errors=false`；要求 acquisition 为 Stop、Sequence 为 OFF，并在读取后恢复 transfer state。 |
| 单／多通道采集 | trigger mode／run／stop／status、waveform | `scope.capture_waveform`、`scope.capture_waveforms` | 先配置全部目标通道，只执行一次 SINGLE，再逐通道读取；不使用 `*OPC?` 作为触发完成证据。 |
| 测量统计 | mode、slot、type、statistics、history | `scope.measurement_statistics` | 只读取已启用的 Advanced measurement slot；不配置、启用或清空统计。Buffer 只在调用方请求时读取。 |
| Screenshot | `:PRINt? PNG,NORMal`／`INVerted` | `scope.screenshot_profile`、`scope.screenshot_v2` | 只接受 profile 中的 color／inverted variant，使用 MESSAGE framing，在内存中校验 PNG，不修改持久显示状态。 |
| Acquisition run state | `:TRIGger:STATus?` | `scope.acquisition_run_state` | 将厂商 token 映射为公共运行状态；acquisition count 只作诊断，不能单独证明完成。 |
| Acquisition control | trigger mode、run、stop、single | `scope.acquisition_control` | 连续模式只支持 `auto`／`normal`；SINGLE 使用 `configure_then_arm`，失败 cleanup 和恢复顺序由 profile 定义。 |
| Autoset | `:AUToset` | 未声明 | 会同时改变 trigger、vertical 和 timebase，且当前没有完整恢复合同，默认拒绝。 |
| Math／FFT | function、operator、source、scale、span | 未声明对应扩展能力 | 频率轴、ready、RBW、sample rate 和 payload 尚无完整公共合同。 |
| Typed trace | source、metadata、data | 未声明 | 当前长记录与 Core typed trace 点数上限之间尚未形成可声明的完整 profile。 |
| Snapshot、测量配置、digital、Sequence／history | 共用 SDS 子系统 | 未声明 | 需要逐项核对型号、选件、可读字段和恢复语义，不能创建假完整模型。 |
| Reset、系统设置与仪器文件 | `*RST`、system、save／recall、image save | 未声明 | 会改变全局、网络或持久状态，默认不进入基础驱动。 |

## Waveform 行为

`fetch_waveform()` 在任何 waveform 写入前验证 `points="dmax"`、`check_errors=false`、目标通道、
`TRIGger:STATus? = Stop` 和 `ACQuire:SEQuence? = OFF`。随后保存
`SOURCE/START/INTERVAL/POINT/WIDTH/BYTEorder`，并为本次读取配置目标 source、`WORD`、LSB、
`START 0`、`INTERVAL 1` 和 `POINT 0`。

`PREamble?` 必须是 Core 去除 IEEE binary-block envelope 后恰好 346 bytes 的 descriptor；附加
Sequence timestamp 或无法确定的 descriptor byte order 会失败。Driver 验证 source、sample
width、byte order、点数与 data byte count，再查询 `MAXPoint?` 决定每块上限并读取完整记录。
成功、协议错误或 transport 异常后都会尝试恢复原 transfer state；恢复失败不会掩盖已有主异常。

模拟波形换算使用：

```text
vdiv = vertical_scale_raw * probe
offset = vertical_offset_raw * probe
voltage = raw_code * (vdiv / code_per_div) - offset
x[i] = horizontal_delay - timebase * 10 / 2 + i * sample_interval
```

8-bit 样本按有符号整数解释；更高 ADC 位数使用 `WORD`、LSB 和有符号 16-bit 解码。高分辨率
样本按手册保持左对齐，driver 不自行右移。`DEF` 和 `MAX` 在仪器 I/O 前失败，不发送手册未定义
的点数关键字。

## Screenshot 与 acquisition profile

- Screenshot profile 只声明 color 和 inverted 两种 PNG 请求，使用 MESSAGE framing，限制
  response／operation payload，并要求规范 PNG 后只有 `0A` content trailing。它不捕获、修改或恢复
  持久显示字段。
- Acquisition control profile 只声明 `auto` 和 `normal` 连续模式；SINGLE 先配置再 arm，模式切换
  会重置 acquisition count。失败恢复依次处理 acquisition 与 trigger，最终重新确认 Stop。
- 精确 payload 上限、步骤预算和 profile 语义以
  [profiles.py](../src/wavebench_siglent_sds800x_hd/profiles.py) 为准，不在本文复制第二份数值表。

## 当前直接使用的 SCPI

以下列表按当前 driver 汇总，用于定位协议域；[driver.py](../src/wavebench_siglent_sds800x_hd/driver.py)
仍是完整事实源。

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
:ACQuire:MODE[?]
:ACQuire:SEQuence?
:PRINt? PNG,NORMal
:PRINt? PNG,INVerted
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

## 相关来源

- [Production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py)
- [Descriptor profiles](../src/wavebench_siglent_sds800x_hd/profiles.py)
- [Driver implementation](../src/wavebench_siglent_sds800x_hd/driver.py)
- [功能覆盖开发路线](SDS800X_HD_COVERAGE_MILESTONES.md)
- [实机验收记录](SDS800X_HD_HARDWARE_ACCEPTANCE.md)
- [Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md)
