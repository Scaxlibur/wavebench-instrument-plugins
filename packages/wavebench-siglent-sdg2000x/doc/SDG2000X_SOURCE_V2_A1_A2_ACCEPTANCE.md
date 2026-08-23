# SDG2000X Source V2 A1／A2 实机验收

[English](SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 24 日，在一台 `SDG2122X`、固件 `2.01.01.39R7T2` 上完成了当前 SDG2000X Source V2
适配的 A1 与有限 A2 验收。适用范围仅为该型号、固件和下列通道／方向；不外推到 `SDG2042X`、`SDG2082X`、其它固件或未列出的功能。

- A1：`source.snapshot_v2` 在 CH1／CH2 上完成一致的只读快照；两个 Sine 通道共 38 次查询、零仪器写入，session 保持 healthy。
- A2：`source.basic_configure_v2` 在 CH1／CH2 各完成一次 1 Vpp 写入与独立回读；`source.output_v2` 完成 CH1、CH2 各一次 ON 与 OFF；最终两路均为 Sine／1 kHz／1 Vpp／0 V、Harmonic OFF、输出 OFF，session healthy。
- A2：`source.harmonics_disable_v2` 在 CH1 完成一次已审计关闭写入，并独立回读 Harmonic OFF 与输出 OFF；该能力仍只适用于本页记录的精确型号和固件。

本记录不是 A3 波形验收、故障注入验收、正式 conformance manifest 或发布签核。

## 软件与安全边界

- 核心来源版本：WaveBench `0.8.24` 开发线；Source 合同修订 `R7`。
- 插件：`wavebench-siglent-sdg2000x` `0.8.2`，canonical driver ID 为 `siglent.sdg2000x`。
- 受控配置将 `max_source_vpp` 限制为 5 Vpp；本轮 Basic/Output 请求均为 1 Vpp，低于该限制和已授权的 10 Vpp 上限。
- 全部写入经 `run check → run verify → run intent → run plan` 执行；未使用 raw SCPI，未修改 `wavebench.toml`。
- 保存的私有运行记录包含脱敏的 intent、operation artifact、I/O 计数与最终状态；资源地址、序列号和原始响应不进入本文件或发行包。

## A1：双通道只读快照

`source.snapshot_v2` 在运行时身份与 descriptor 的适用域一致时，读取 CH1／CH2 的
anchor/facet/anchor 状态。记录结果如下：

| 项目 | 结果 |
| --- | --- |
| capability | `source.snapshot_v2` |
| 通道 | CH1、CH2 |
| 查询／写入 | 38／0 |
| 一致性 | `consistent` |
| session health | `healthy → healthy` |
| 初始基础状态 | 两路 Sine／1 kHz／4 Vpp／0 V／输出 OFF |

该证据只证明查询响应、预算和运行时型号／固件适用性，不证明输出转换或波形精度。

## A2：受控 Basic、输出与 Harmonic 关闭

### Basic 与输出

受控 plan 先在输出 OFF 时对 CH1、CH2 各写入 1 Vpp，随后依次开启、关闭两路输出。九个步骤全部成功，源端共有 6 次已完成 mutation，结果未知数为 0；示波器只参与耦合安全门，未采集波形。

每个 Basic 和 Output 操作均取得独立 postcondition snapshot。完成后重新执行只读 V2 快照，确认两路均为 Sine／1 kHz／1 Vpp／0 V、Harmonic OFF、输出 OFF，session 保持 healthy。

### Harmonic 关闭

首次 Basic 尝试发现设备已有 Harmonic 状态。早期 adapter 的 Basic driver 在发送 Basic 命令前拒绝该状态；因 MAIN 已进入，核心执行了一次 OFF recovery，最终输出已确认 OFF。该轮不构成 Basic 写入成功或实机故障注入证据。

随后使用 `source.harmonics_disable_v2` 关闭 CH1 的 Harmonic。该 operation 发送 1 次已完成 mutation、没有结果未知或 recovery；独立回读确认 Harmonic OFF 与输出 OFF，session 保持 healthy。CH2 只记录到最终 Harmonic OFF 状态，未执行 CH2 的 Harmonic 关闭 operation。之后的 Basic/Output plan 才开始执行。

## 未证明的内容

- 未通过示波器环回验证频率、Vpp、偏置、函数或占空比；A3 仍待完成。
- 未人为诱发传输失败、未知写入或写后回读不匹配。此类恢复分支仍只有 A0 故障注入证据，不宣称为 A2 实机证据。
- 未验证任何其它型号、固件、负载、端口映射或高级 Source V2 capability。
- 未生成正式 wheel conformance manifest，未进行发布签核。
