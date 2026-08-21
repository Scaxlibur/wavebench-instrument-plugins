# SDG2000X 通道跟踪、耦合、复制与双通道触发验收

[English](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成通道跟踪、频率/幅度/相位耦合、双向参数复制及双通道手动 Burst 触发验收。

- `TRACE` 能立即把 CH1 完整基本波状态复制到 CH2，并持续跟随 CH1 的频率和幅度变化。
- `FRAT/FDEV`、`ARAT/ADEV`、`PRAT/PDEV` 均能严格回读，并在两路输出上取得对应 A4 波形。
- `PACP C2,C1` 与 `PACP C1,C2` 均完成完整基本波回读；CH1→CH2 另取得双路 A4 波形。
- `TRDUCH` 的真实语义是双通道 Manual Burst 同触发，不是一般跟踪方向。`TRDUCH ON` 后从 CH2 发起手动触发，两次有效采集均出现双路 10-cycle Burst。

常规联动最高实测 0.72 Vpp，双路 Burst 最高实测 2.16 Vpp，均低于 9 V 停止阈值和 10 Vpp 硬上限。所有正式信号源写入均完成，未知结果为 0；结束后两路输出、Burst 和全部 Coupling 状态均为 OFF。

## 环境与安全边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.8.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：信号源 CH1 → 示波器 CH1；信号源 CH2 → 示波器 CH2；两路均为高阻输入。

测试前确认两路输出、Modulation、Sweep、Burst、Harmonic、Combine 与 Noise Add 均关闭。联动模式一次只开启一个；所有模式切换均在输出 OFF 时进行。任一采样达到 9 Vpp 或绝对值超过 5 V 会立即停止。

## 协议结果

### 跟踪与双通道触发

`COUP?` 在普通关闭态返回 `TRACE/FCOUP/PCOUP/ACOUP/TRDUCH` 五个状态。`TRACE ON` 时当前固件只返回 `COUP TRACE,ON`，其它字段被省略；解析器不能强制关闭态字段在所有状态都存在。

`TRACE ON` 立即把 CH2 的 Square / 3 kHz / 0.2 Vpp / 30° 替换为 CH1 的 Sine / 1 kHz / 0.4 Vpp / 10°。随后把 CH1 改为 1.5 kHz、0.6 Vpp，CH2 同步回读完全相同。

`TRDUCH ON` 不复制基本波状态；CH1 改频时 CH2 保持不变。用户手册将该字段定义为 Manual Burst 的「双通道触发」，实机测试按该语义执行。

### 频率、幅度与相位耦合

| 模式 | CH1 回读 | CH2 回读 | 关系 |
| --- | ---: | ---: | --- |
| `FRAT,2` | 1200 Hz | 2400 Hz | CH2 / CH1 = 2 |
| `FDEV,500` | 1200 Hz | 1700 Hz | CH2 − CH1 = 500 Hz |
| `ARAT,0.5` | 0.4 Vpp | 0.2 Vpp | CH2 / CH1 = 0.5 |
| `ADEV,0.1` | 0.4 Vpp | 0.5 Vpp | CH2 − CH1 = 0.1 Vpp |
| `PRAT,2` | 30° | 60° | CH2 / CH1 = 2 |
| `PDEV,90` | 30° | 120° | CH2 − CH1 = 90° |

`COUP?` 只返回当前有效的关系字段，例如 `FRAT` 与 `FDEV` 互斥、`ARAT` 与 `ADEV` 互斥。通用解析必须按字段名和可用性处理条件字段。

### 参数复制

在两路输出 OFF、全部 Coupling OFF 时：

- `PACP C2,C1` 把 CH1 的 Sine / 2 kHz / 0.4 Vpp / 0.05 V / 10° 完整复制到 CH2；
- `PACP C1,C2` 把 CH2 的 Ramp / 4 kHz / 0.3 Vpp / -0.02 V / 40° 完整复制到 CH1。

编程手册没有 PACP 查询，验收以复制后的独立 `BSWV?` 为证据。

## 常规联动波形结果

| 项目 | CH1 结果 | CH2 结果 |
| --- | --- | --- |
| 跟踪 | 1800 Hz，0.3988 Vpp | 1800 Hz，0.4051 Vpp |
| 频率比例 2 | 1200 Hz，0.3977 Vpp | 2400 Hz，0.2135 Vpp |
| 频率偏差 500 Hz | 1200 Hz，0.3969 Vpp | 回读 1700 Hz，在 1700 Hz 拟合 0.2127 Vpp |
| 幅度比例 0.5 | 1000 Hz，0.3997 Vpp | 1000 Hz，0.2145 Vpp |
| 幅度偏差 0.1 Vpp | 1000 Hz，0.3982 Vpp | 1000 Hz，0.5036 Vpp |
| 相位比例 2 | 相位基准 | CH2−CH1 = 29.66° |
| 相位偏差 90° | 相位基准 | CH2−CH1 = 89.85° |
| CH1→CH2 复制 | 2200 Hz，0.3979 Vpp | 2200 Hz，0.4040 Vpp |

当前 RTM2032 记录的 FFT 栅栏间隔为 200 Hz，因此 1700 Hz 偏差案例的最大 FFT 栅栏落在 1600 Hz；该案例同时有信号源 1700 Hz 精确回读和 1700 Hz 正交拟合幅度，不把 1600 Hz 栅栏误写成信号源实际频率。

## 双通道 Manual Burst 结果

两路均配置 Sine、10 kHz、2 Vpp、10 cycles、`TRSR,MAN`，并开启 `TRDUCH`。由 CH2 发送 `MTRIG`，RTM2032 分别以 CH2 为触发源捕获两路冻结帧。

三次尝试中两次取得可判定帧：

| 有效帧 | CH1 Burst 时长 | CH2 Burst 时长 | CH2−CH1 起点差 | 最大 Vpp |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.043 ms | 1.055 ms | 41.5 µs | 2.16 V |
| 2 | 1.054 ms | 1.044 ms | 40.5 µs | 2.16 V |

第三次记录被 AUTO acquisition 覆盖为跨满记录的不可判定帧，不纳入成功统计。CH1 发起方向在当前示波器触发配置下未获得可重复冻结帧，因此本轮只声明 CH2→双路的 A4，不把用户手册的「任一通道」描述扩张为双向实机结论。

## Transport 审计与恢复

协议轮次执行 46 次查询、108 次写入；常规 A4 轮次执行 45 次查询、148 次写入；正式双通道 Burst 轮次执行 16 次查询、51 次写入。三个轮次的已发送、已完成写入均等于写请求，未知结果均为 0。

双通道 Burst 的诊断阶段曾把 RTM2032 切到 `NORM` 后等待单次 acquisition 超时。该示波器会话按设计锁止；全新会话确认它暂留在 `NORM`，随后只写回 `AUTO` 与 `RUN` 并严格回读，再开始正式轮次。信号源在每次失败路径上均恢复两路 OFF。

正式轮次结束后：

- CH1/CH2 输出均为 OFF；
- `TRACE/TRDUCH/FCOUP/PCOUP/ACOUP` 均为 OFF；
- 两路 Burst、Modulation、Sweep、Combine 与 Noise Add 均为 OFF；
- 两路恢复 Sine / 1 kHz / 4 Vpp / 0 V；
- 原 Harmonic 启用状态与 `PHASE-LOCKED` 模式恢复；
- RTM2032 两路通道、探头、时基与触发快照无漂移，且无过载。

## 核心接口边界

现有核心耦合/通道 profile 不能完整表达 SDG2000X 的状态依赖响应、关系模式互斥、双向基准行为、动作式 PACP 以及 Manual Burst 联合触发事务。插件没有把这些命令塞入 raw SCPI 或伪造完整 profile。可复用的拆分 facet、availability、patch/transaction 与安全预算设计见 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)。

## 覆盖边界

- 跟踪、三类耦合与 CH1→CH2 复制均有 A4；CH2→CH1 复制完成 A3。
- `TRDUCH` 只有 CH2 发起方向的重复 A4；CH1 发起方向待更稳定的双路冻结采集方案。
- 未把 Coupling 与 Modulation、Sweep、Harmonic、Combine 或 Noise Add 组合。
- 实机证据只适用于当前 SDG2122X 固件。
