# SDG2000X 辅助与全局状态只读验收

[English](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 固件 `2.01.01.39R7T2` 完成 Sync、Frequency Counter、参考时钟、相位模式、过压保护、数字格式、语言、上电配置、蜂鸣器、屏保和多设备同步的只读 A3 验收。

正式轮次使用 `read_only` 访问，执行 18 次查询、0 次写入。两路主输出在开始和结束时均为 OFF。参考时钟源、多设备同步、Counter、Sync 和系统设置没有被改变。

这些结果只证明查询协议和当前状态，不代表未接线接口的电气功能或测量准确度。尤其不能为了提高数字覆盖率切换外部参考时钟、开启 Counter 或改写全局保护和 UI 配置。

## 环境与边界

- WaveBench：0.8.23。
- 插件：`wavebench-siglent-sdg2000x` 0.8.0。
- 信号源：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 已知接线只有 CH1/CH2 主输出至 RTM2032；Sync/Aux、Counter 输入和外部参考接口没有纳入本轮物理接线证明。

所有查询经插件 transport 执行，未调用 raw SCPI 公共入口。测试不发送 `*RST`、`ROSC`、`FCNT`、`SYNC`、`CASCADE`、`VOLTPRT` 或系统设置写命令。

## 查询结果

| 域 | 查询 | 当前回读 | 验收级别 |
| --- | --- | --- | --- |
| CH1 Sync | `C1:SYNC?` | OFF，Type=CH1 | A3 |
| CH2 Sync | `C2:SYNC?` | OFF，Type=CH2 | A3 |
| Frequency Counter | `FCNT?` | OFF | A3 |
| 参考时钟 | `ROSC?` | INT，10 MHz Output=ON | A3 |
| 相位模式 | `MODE?` | `PHASE-LOCKED` | A3，另有 A4 相位文档 |
| 过压保护 | `VOLTPRT?` | ON | A3 |
| 数字格式 | `NBFM?` | 小数点 DOT，分隔符 SPACE | A3 |
| 语言 | `LAGG?` | 简体中文 | A3 |
| 上电配置 | `SCFG?` | DEFAULT | A3 |
| 蜂鸣器 | `BUZZ?` | ON | A3 |
| 屏保 | `SCSV?` | OFF | A3 |
| 多设备同步 | `CASCADE?` | OFF，保留 Master 模式字段 | A3 |

`ROSC?` 表明 10 MHz Output 在验收前已经为 ON。本轮严格保持原状；没有合格外部参考源和锁定状态证据时，禁止把时钟源切到 EXT，也不把关闭已有时钟输出当作「清理」。

## 固件响应差异

- `FCNT?` 在 Counter OFF 时只返回 `FCNT STATE,OFF`，不会返回手册 ON 示例中的测量和配置字段。
- `VOLTPRT?` 返回裸 `ON`，不是手册写出的 `VOLTPRT ON`。
- `MODE?` 返回 `PHASE-LOCKED`，与 E05C 的 `PHASELOCKED` 拼写不同。
- `SYNC?` 即使状态 OFF 仍返回 `TYPE`。
- `CASCADE?` 在状态 OFF 时仍返回保留的 `MODE,MASTER`。

严格解析必须按状态允许字段缺省，并只接受已证实的响应变体；不能用固定 token 数或手册 ON 示例解析所有状态。

## 核心接口边界

- `SourceChannelProfile` 同时要求 Sync polarity，而 SDG2000X `SYNC?` 返回的是路由 Type，没有极性字段；不能猜默认极性。
- 当前 Counter profile 需要可观测配置与有效测量值，`FCNT?` 在 OFF 时只提供状态；先写配置再回填会破坏只读语义，也无法反映面板或其它客户端后续修改。
- 参考时钟需要可复用的 `selected_source`、`lock_state`、`available_sources` 与输出状态 facet，不能塞进 Sync 或 Counter。
- Cascade、保护和 UI 配置是全局系统域，不应伪装成通道 Source capability。

相关通用建模方向已纳入 [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY.md)，没有修改核心仓库。

## Transport 审计

正式轮次：

- 查询：18 次；
- 写请求：0 次；
- 已发送写入：0 次；
- 已完成写入：0 次；
- 写结果未知：0 次；
- 仪器变更写入：0 次。

结束时再次通过公开 `source.status` 确认 CH1/CH2 均为 OFF。

## 后续物理验收条件

- Sync：Sync/Aux 输出接入示波器后，验证基本波、调制、Sweep 与 Burst 下的频率和相位关系。
- Counter：已知校准信号接入 Counter BNC 后，验证频率、周期、正负脉宽、占空比与偏差。
- 外部参考：提供合格 10 MHz 源、正确幅度/阻抗和失锁检测后，作为独立高风险事务验收。
- Cascade：至少两台兼容仪器、专用接线和延迟基准；不得用单机状态切换冒充多机同步测试。
