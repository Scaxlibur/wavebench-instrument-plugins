# SDG2000X 当前能力 Reference

[English](SDG2000X_COVERAGE_MATRIX_EN.md)

本页说明 `siglent.sdg2000x` production descriptor 当前声明的 capability、适用范围和失败边界。包元数据版本为 `0.8.2`；该值表示仓库内的源码合同，不依赖独立的 PyPI、Git tag 或 GitHub Release 状态。

## Synopsis

| 项目 | 当前值 |
| --- | --- |
| Distribution | `wavebench-siglent-sdg2000x` |
| Driver ID | `siglent.sdg2000x` |
| 登记型号 | `SDG2042X`、`SDG2082X`、`SDG2122X` |
| WaveBench | `>=0.8.24,<0.9` |
| Python | `>=3.11` |
| Backend | `pyvisa` |
| 配置字段 | `source.resource`、`source.driver`、`safety_limits.max_source_vpp` |

Source V2 topology 包含 CH1 和 CH2。快照 query contract 为 pure read，预算上限 `44` 次 query，timeout 为 `5000 ms`。

## 当前 capability

| Capability | 精确范围与行为 |
| --- | --- |
| `source.idn` | 读取并匹配 SDG2000X 系列身份。 |
| `source.status` | 读取指定通道的基础波形、频率、幅度、偏置和输出状态。 |
| `source.set_frequency` | 设置固定波频率；检查型号与当前波形边界。Sweep 自动切回 FIX 只允许在输出 OFF 时发生。 |
| `source.set_function` | 设置有界周期波；Sine、Square、Ramp 和 Pulse 可以按合同切换，Noise／DC 只允许在输出 OFF 时配置。 |
| `source.set_amplitude_vpp` | 设置 `2 mVpp–10 Vpp`；幅度与偏置包络必须保持在 `±10 V` 内。 |
| `source.set_square_duty_cycle` | 仅适用于 FIX 模式 Square；频率相关钳位或 readback 不匹配时关闭失败。 |
| `source.output` | 读取、开启或关闭通道输出；开启前要求 FIX、可读的 Vpp／Offset、已知复合模式关闭和 `max_source_vpp` 检查。 |
| `source.arbitrary_probe` | 只读探测任意波状态；不上传、删除或覆盖波形。 |
| `source.snapshot_v2` | 对 CH1／CH2 执行 anchor／facet／anchor 纯读取；包含 identity、Basic、Output 和按激活条件读取的 Harmonics facet。 |
| `source.basic_configure_v2` | 对 CH1／CH2 的 Sine、Square、Ramp、Pulse 执行单字段 Basic MAIN 配置；支持 fixed frequency、Vpp 和 Square duty，`offset_v` 当前不开放写入。 |
| `source.output_v2` | 独立读取、开启或关闭 CH1／CH2；每次 MAIN 只写目标字段，随后由 Core 独立读取快照。 |
| `source.harmonics_disable_v2` | 仅适用于 `SDG2122X`／`2.01.01.39R7T2`、Sine 和目标输出 OFF；只读取或关闭 Harmonic，不配置或开启。 |

## Source V2 的型号与固件限制

Basic 和 Output feature 的 descriptor applicability 没有附加型号或固件限制，适用于登记型号的运行时合同。当前受控实机证据主要来自 `SDG2122X` 固件 `2.01.01.39R7T2`；该证据不会替代 descriptor，也不会自动证明其它型号、固件和物理工作点。

Harmonic feature 具有显式限制：

- 型号必须是 `SDG2122X`；
- 固件必须是 `2.01.01.39R7T2`；
- 目标通道必须为 Sine，且输出为 OFF；
- 已关闭时不发送 MAIN 写入；已开启时只发送一条 `HARMSTATE,OFF`；
- Core 随后独立回读 Harmonic 与输出状态。

Harmonic profile 可读取 2–16 次谐波和绝对 Vpp／相对 dB 幅度，但当前公共写方向只有 `DISABLE`。

## Side effects 与失败行为

- descriptor 导入不访问仪器；factory 只打开已配置的 transport。
- `read_only` session 只允许读取，Core 在写入前拒绝不匹配的 access。
- V1 与 V2 写操作都必须满足目标通道、波形、输出、安全上限和 readback 合同。
- V2 Basic 和 Output 的目标配置各只写一次；写后异常会尝试输出 OFF，并锁止当前 session 的后续配置写入。
- Source V2 不把 Noise／DC 的 `STDEV` 或标称值伪装成 Vpp；无法无损表达时保留 V1 的安全路径。
- 不通过历史 harness 或 raw SCPI 绕过当前 descriptor。

## 当前不支持

production descriptor 不声明错误队列、调制、Sweep、Burst、Pulse 参数、任意波上传／删除、Combine、相位／Invert、跟踪／耦合／复制、Sync、Counter、外部参考、Cascade 或 raw SCPI capability。

部分命令域具有受控实机证据，但在 Core 缺少无损模型或 descriptor 未声明 capability 时，仍属于 unavailable。证据用于追溯，不是第二份当前能力表。

## Sources

- [包元数据](../pyproject.toml)
- [Production descriptor](../src/wavebench_siglent_sdg2000x/descriptor.py)
- [Driver implementation](../src/wavebench_siglent_sdg2000x/driver.py)
- [Driver tests](../tests/test_driver.py)
- [Wheel 与 descriptor tests](../tests/test_wheel.py)
- [开发记录与实机证据入口](README.md)
