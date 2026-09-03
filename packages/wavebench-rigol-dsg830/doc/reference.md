# DSG830 当前能力 Reference

[English](reference-en.md)

本页说明 `rigol.dsg830` production descriptor 当前声明的精确使用边界。包元数据版本为 `0.2.0`；该值表示仓库内的源码合同，不表示独立的 PyPI、Git tag 或 GitHub Release 状态。

## Synopsis

| 项目 | 当前值 |
| --- | --- |
| Distribution | `wavebench-rigol-dsg830` |
| Driver ID | `rigol.dsg830` |
| 型号 | `DSG830` |
| WaveBench | `>=0.8.25,<0.9` |
| Python | `>=3.11` |
| Backend | `pyvisa` |
| Resource scheme | `tcpip`、`usb` |
| 配置字段 | `rf_source.resource`、`rf_source.driver` |

`rf_out` 的 descriptor 范围为 `9 kHz–3 GHz`、`-110–20 dBm`，功率参考阻抗为 50 Ω。该参考用于功率合同，不证明实际端接。

## 已声明 capability

| Capability | 精确范围与行为 |
| --- | --- |
| `rf_source.idn` | 读取并严格匹配 DSG830 身份。 |
| `rf_source.snapshot` | 读取身份、频率、功率、RF 输出、调制、Pulse、Sweep 和 protection 状态；不写仪器。 |
| `rf_source.cw_configure` | 读取或配置 `rf_out` 的频率与 dBm 功率；配置要求 RF OFF 和完整的 OFF-only 前置检查。 |
| `rf_source.output` | 读取、开启或关闭 `rf_out`；普通 RF ON 要求调制关闭，并通过 Core 的端口安全限制、fresh snapshot 和独立 readback。 |
| `rf_source.modulation_configure` | 只配置 RF-OFF 的内部正弦 AM、FM 或 PM；配置后保持 RF OFF。 |
| `rf_source.modulation_disable` | 只在 RF OFF 且存在一个已知活动模式时关闭该模式和全局调制；不是 reset。 |
| `rf_source.modulated_output_enable` | 只允许已配置并精确读回的固定低功率 AM／FM／PM profile；成功路径只开启一次 RF。 |
| `rf_source.pulse_configure` | 只配置 `rf_out` 的 internal／single Pulse profile；配置后保持 Pulse OFF。 |
| `rf_source.pulse_output` | 读取、开启或关闭 `pulse_in_out` 的固定 output profile；不检测或配置接收端。 |
| `rf_source.sweep_configure` | 只配置固定的 frequency-only Step Sweep profile；配置后保持 Sweep disabled，不执行或触发 Sweep。 |

## Profile

### CW 与 RF 输出

- 频率：`9 kHz–3 GHz`。
- 功率：`-110–20 dBm`，以 50 Ω 为参考。
- descriptor 标记 `alc_heater_detector_30min`、`alc_unlocked` 和 `output_power_protection` 为阻断写入的 protection condition。
- 开启输出前必须满足 Core 安全合同；驱动不会从连接器名称推断实际负载或端接。

### 内部正弦调制

| 模式 | RF-OFF 配置范围 | 内部频率 | 调制输出固定 profile |
| --- | --- | --- | --- |
| AM | `0–100 %` | `10 Hz–100 kHz` | `50 %`、`1 kHz` |
| FM | `0.1 Hz–1 MHz` 频偏 | `10 Hz–100 kHz` | `20 kHz` 频偏、`1 kHz` |
| PM | `1.25 rad` | `10 Hz–100 kHz` | `1.25 rad`、`1 kHz` |

`rf_source.modulated_output_enable` 的最大允许功率为 `-50 dBm`。普通 `rf_source.output` 不允许在调制活动时开启 RF。

### Pulse

- `rf_source.pulse_configure` 仅支持 internal／single，polarity 为 normal 或 inverted。
- Period：`40 ns–170 s`。
- Width：`10 ns–169.99999999 s`，最短 OFF 时间为 `10 ns`。
- `rf_source.pulse_output` 只适用于接口 `pulse_in_out` 的 output 方向，固定为 `0 V`／`3.3 V`、约 `600 Ω`、internal／single／normal、period `1 ms`、width `100 µs`。
- `pulse_in_out` 与 50 Ω `rf_out` 是不同接口；Pulse Output capability 不声明接收端、线缆或负载状态。

### Step Sweep

- Type：`STEP`。
- Direction：`FWD`。
- Shape：`RAMP`。
- Spacing：`LIN`。
- 频率：`9 kHz–3 GHz`。
- Points：`2–65535`。
- Dwell：`20 ms–100 s`。

该 capability 只配置并读回 profile，结尾保持 Sweep disabled。

## Side effects 与失败行为

- `read_only` session 只允许身份和状态读取。
- 写入需要显式 `read_write`，并满足 capability 对应的状态、安全配置和 readback 合同。
- profile 越界、前置状态未知、protection 活动或写后读回不一致时，操作关闭失败；不通过 raw SCPI 绕过。
- 输出开启结果不明时不会重试 ON；可恢复路径只允许受 guard 的 OFF 操作。
- descriptor 导入不访问仪器；factory 只打开已配置的 transport。

## 当前不支持

production descriptor 不声明：错误队列、`rf_source.trigger_snapshot`、Pulse input、`TRIGGER IN`、trigger、Sweep execute／fire、sync／reference、Level Sweep、list 或任意 SCPI passthrough。

## Sources

- [包元数据](../pyproject.toml)
- [Production descriptor](../src/wavebench_rigol_dsg830/descriptor.py)
- [Descriptor tests](../tests/test_descriptor.py)
- [历史里程碑与实机证据](DSG830_COVERAGE_MILESTONES.md)
- [文档入口](README.md)
