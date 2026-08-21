# SDG2000X 特殊波形协议与实机验收

[English](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成 Noise、DC、Noise Add 与 TrueArb 采样率模式的专项验收。Noise、DC 和 TARB 均取得 A4 波形证据；最高实测 1.68 Vpp，低于 9 V 停止阈值和 10 Vpp 硬上限。

`NOISE_ADD` 的 `RATIO` 与 `RATIO_DB` 能写入并回读，但手册规定的所有启用写法在当前固件上均静默保持 `STATE,OFF`。双通道、输出 OFF/ON 两种前置条件共 12 次启用探针得到相同结果。因此本轮把 Noise Add 记为 A3 负向验收，不声明写能力，也不伪造 A4 结果。

现有核心 `SourceChannelProfile` 以周期波形的有限 Vpp 为基础，不能无损表示 Noise 的 `STDEV/MEAN/BANDWIDTH`、DC 电平或 ARB 的 DDS/TARB 模式。插件只保留已发布的只读 `source.arbitrary_probe`，不为这些状态声明有损 capability。通用改进方向见 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.8.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH2 → 示波器 CH2，高阻输入。
- 停止阈值：任一采样达到 9 Vpp 或绝对值超过 5 V，立即关闭输出。

每组参数均在输出 OFF 时配置。Harmonic、Modulation、Sweep、Burst、Combine 与 Coupling 均关闭；采集后立即关闭输出。DC 使用新的单次采集帧，读取后恢复 RTM2032 连续运行，避免 AUTO 触发下复用旧帧。

## Noise

设置为 `STDEV=0.2 V`、`MEAN=0 V`。关闭带宽限制和启用 20 MHz 限制时均取得非平坦随机波形：

| 模式 | 实测均值 | 中心化 RMS | 实测 Vpp |
| --- | ---: | ---: | ---: |
| 带宽限制 OFF | -5.4 mV | 182.1 mV | 1.52 V |
| 带宽限制 ON，20 MHz | -3.6 mV | 196.7 mV | 1.68 V |

向当前固件写入 100 kHz 后，`BSWV?` 回读为 20 MHz，证明该请求被钳位到型号下限。本轮示波器时基与采样设置用于安全波形确认，不足以把两档 FFT 功率差解释为带宽精度校准；20 MHz 只记协议回读 A3。

## DC

| 设定 | 实测均值 | 实测 Vpp |
| ---: | ---: | ---: |
| -1.0 V | -1.0038 V | 0.16 V |
| 0 V | -5.4 mV | 0.24 V |
| +1.0 V | +1.0027 V | 0.16 V |

三档均值误差不超过 5.4 mV。表中 Vpp 是静态轨迹上的采集噪声与量化范围，不是信号源的周期波形幅度。

## Noise Add 负向结果

探针分别覆盖 CH1、CH2，并在主输出 OFF 与 ON 下尝试：

- `STATE,ON,RATIO,100`；
- `STATE,ON,RATIO_DB,20`；
- 先写 `RATIO,100`，再单独写 `STATE,ON`。

每次查询都返回 `STATE,OFF,RATIO,100,RATIO_DB,20dB`。这说明参数寄存器接受写入，但当前硬件/固件没有进入 Noise Add 状态。探针结束后显式写回 `STATE,OFF` 并关闭两路输出。

该结果只证明当前样机上的稳定负向行为，不足以判定整个 SDG2000X 系列永久不支持 Noise Add。后续若在其他固件上读到 `STATE,ON`，必须补做载波拟合残差和频谱噪声底的 A4 验收后才可发布。

## TrueArb 采样率模式

选择内建 ARB 索引 2，以 0.5 Vpp、0 V 偏置设置 `SRATE MODE,TARB,VALUE,1000000`。查询严格回读 TARB 和 1 MSa/s；实测波形为非平坦，Vpp 0.72 V、中心化 RMS 107.7 mV。随后切回 DDS，恢复原 ARB 选择，并恢复 Sine / 1 kHz / 4 Vpp / 0 V 的安全基准。

本轮不上传、不删除、不覆盖用户任意波数据。

## Transport 审计与恢复

正式 CH2 波形轮次执行：

- 查询：51 次；
- 写请求：77 次；
- 已发送：77 次；
- 已完成：77 次；
- 写结果未知：0 次。

结束后：

- CH1/CH2 均为 OFF；
- CH2 恢复 Sine / 1 kHz / 4 Vpp / 0 V；
- 原 ARB 选择、DDS 模式与 Harmonic 启用状态均恢复；
- RTM2032 通道、探头、时基与触发快照无漂移，且无过载。

## 覆盖边界

- Noise 带宽只完成状态、钳位和随机输出确认，不替代噪声谱密度或模拟带宽校准。
- DC 是高阻负载下的三个安全点，不外推到 50 Ω 极限。
- TARB 只覆盖一个内建波形和一个安全采样率，不覆盖用户波形上传与存储。
- Noise Add 是当前固件的负向结果；不宣称跨固件不可用。
- 实机证据只适用于当前 SDG2122X；SDG2042X/SDG2082X 仅按相同协议契约放行查询能力。
