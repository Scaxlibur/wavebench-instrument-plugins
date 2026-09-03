# RTM2000 功能覆盖开发路线

[English](RTM2000_COVERAGE_MILESTONES_EN.md)

> 类型：Development

本页记录 RTM2000 插件的后续开发顺序、当前阻塞项和新 capability 的退出门。它不维护当前
capability 清单，也不替代特定设备和版本的验收记录。当前能力以
[production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py) 为准；手册域与
当前能力的映射见[功能覆盖矩阵](RTM2000_COVERAGE_MATRIX.md)；既有实机结果与负向证据见
[开发与验收存档](archive/RTM2000_README_0.15.md)。

## 共同规则

- 新能力必须先有可准确表达的 Core typed model，再进入插件 descriptor。
- 选件相关能力先核对 identity 和 option，再发送专用 query；未安装选件不作为插件缺陷。
- 只读方法、Python 方法或手册命令存在，不等于 production capability。
- 写入、采集和触发不能盲目重试；状态无法确认时必须失败，并按对应事务合同锁停。
- setup blob、持久存储、网络设置和全局维护命令不作为普通 capability。
- 实机验收只证明记录中的型号、固件、transport 和步骤，不外推整个 RTM2000 系列。

## P1：基础示波器与诊断能力

| 工作项 | 当前开发状态 | 下一退出门 |
|---|---|---|
| Identity、options 与非消费型 health | 已实现 | 新字段仍需证明不会读取消费型 EVENT 或错误队列。 |
| CH1／CH2 模拟通道、时基与 probe metadata | 已实现 | 新字段需要严格解析、型号边界和只读实机证据。 |
| Edge trigger | 只读状态与 CH2 最小受控配置已实现 | 扩展 source／type 前先建立完整事务、恢复责任和型号门控。 |
| 自动测量统计 | 已实现已配置槽位的只读接口 | Buffer 读取需要独立 stopped 前置条件与实机验收。 |
| 波形缩放与形状 metadata | 已实现 | Segment／history identity 必须使用独立模型，不能复用 header 第四字段。 |
| 通道显示与多通道 focus | 已实现受控 V2 配置 | 扩展 position、offset、coupling、termination 或 bandwidth 前补全联合 baseline 与恢复。 |

## P2：特殊采集与只读分析

| 工作项 | 当前开发状态 | 下一退出门 |
|---|---|---|
| Average acquisition | capability 已声明，事务已有离线测试 | 需要独立实机正常路径、失败恢复和新 session 终态验证。 |
| Segmented acquisition | 未实现 | 先定义 segment identity、选择规则、数据上限、artifact 和恢复合同。 |
| History timestamps | capability 已声明；K15 query 仍有阻塞证据 | 只在选件门控后读取；timeout 不重试、不清错，也不把 frame number 当 timestamp。 |
| Math／FFT | 现有 metadata／status 已声明 | Payload、expression 与准确度分别评审，不从主机 DSP 结果推导仪器能力。 |
| Reference metadata | capability 已声明；有效 reference 的实机门未完成 | 不为制造证据调用 update／save／load，也不覆盖用户 reference。 |
| Cursor | 只读 readout 已声明 | 配置与定位保持独立受控写入。 |
| DVM／counter | 未实现 | 先确认选件、source、类型、状态和结果模型，再设计窄的只读 capability。 |
| Probe 安全联动 | 基础 metadata 已实现 | 补充 identity、衰减／阻抗与输入安全限制的明确关系。 |
| Digital waveform | capability 已声明，存在离线覆盖与受控负向证据 | 在已停止且存在稳定数字记录时完成零写入 payload、位序与 X 轴一致性验收。 |

## P3：选件相关高级应用

以下功能需要独立 capability、选件门控、结果模型和恢复策略，不合并进基础 scope API：

- spectrum 与 spectrogram；
- 串行／并行总线 decode；
- protocol trigger 与 search；
- mask test；
- power analysis。

仪器文件系统、报告导出、保存／加载状态、calibration、reset、网络和全局系统设置默认不做。
如确有需求，应另建具备路径权限、持久副作用说明和人工确认的维护流程。

## 每项新能力的退出门

1. Core typed model 能准确表达设备语义，或已有合同明确允许 unavailable 字段。
2. Driver 行为、descriptor 声明、配置字段与权限保持一致。
3. 精确离线测试覆盖正常路径、异常回包、timeout、结果不明和恢复失败。
4. 写入或触发具备 snapshot、readback、恢复、独立验证和必要锁停语义。
5. 选件、型号、transport 与资源限制明确，不从 RTM2032 证据外推整个系列。
6. 实机验收使用受控环境，并将设备条件和结果写入 Historical／evidence 页面。
7. 中英文 Current Reference、导航和生成式插件目录同步通过检查。
