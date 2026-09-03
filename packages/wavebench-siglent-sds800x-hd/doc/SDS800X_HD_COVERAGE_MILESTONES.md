# SDS800X HD 功能覆盖开发路线

[English](SDS800X_HD_COVERAGE_MILESTONES_EN.md)

> 类型：Development

本页记录 SDS800X HD 插件的开发阶段、待办范围和新 capability 退出门。它不维护当前
capability 清单，也不复述具体设备、固件和测量结果。当前能力以
[production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py) 为准；手册域与当前
行为见[功能覆盖矩阵](SDS800X_HD_COVERAGE_MATRIX.md)；设备条件与实测结果见
[实机验收记录](SDS800X_HD_HARDWARE_ACCEPTANCE.md)和
[Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md)。

## 共同规则

- 通用 SDS 手册命令不能自动视为 SDS800X HD capability；先核对型号、固件和 production descriptor。
- Core 增加公共合同不表示插件自动采用；driver、profile、descriptor 和实机恢复证据需要分别完成。
- Python 方法或离线测试存在不等于 capability；只有 descriptor 声明的能力属于当前公开面。
- 仪器 I/O 使用 Core transport；不增加 raw SCPI 入口。
- 实机结果只适用于记录的设备、firmware、transport 和步骤，不外推其他型号或连接方式。
- Reset、Autoset、系统设置和仪器文件操作默认不进入基础驱动。

## 阶段状态

| 阶段 | 范围 | 当前开发状态 | 下一退出门 |
|---|---|---|---|
| M1 | 严格 identity 与只读 coupling | capability 已声明 | 新型号需要独立 identity、通道数和回包验证。 |
| M2 | Preamble 解析、数据换算、stopped-record waveform 事务 | 已实现并具备离线测试 | 新格式必须补全 descriptor 长度、端序、点数和失败恢复测试。 |
| M3 | TCPIP WORD／LSB、分块读取、transfer restore、Sequence 拒绝 | 已有受控实机证据 | USB 和其他型号仍需独立验收；证据写入 Acceptance，不写入 Current Reference。 |
| M4 | SINGLE、Stop 轮询、单／多通道 capture | capability 已声明 | 新采集模式需要独立完成证明、失败 cleanup 和 fresh readback。 |
| R1.3 adoption | Screenshot 与 acquisition run-state／control | capability 与 descriptor profile 已声明 | Profile 修改必须同步验证 framing、预算、状态恢复和 conformance。 |

## 后续能力

| 工作项 | 当前开发状态 | 下一退出门 |
|---|---|---|
| Typed trace metadata／fetch | 未声明 | Core 点数上限与已支持长记录之间需要明确策略；补全 transfer baseline、profile 和实机 fresh readback。 |
| Error drain | 未声明 | CN11G 没有可靠错误队列命令；没有真实协议前保持 unavailable，不伪造空结果。 |
| Math／FFT | 未声明对应扩展能力 | 先定义频率轴、ready、RBW、sample rate 和 payload 的可表达合同。 |
| Digital channels | 未声明 | 先确认选件、电气阈值、编码、位序和恢复语义。 |
| Sequence／history | 未声明 | 先定义 frame identity、timestamp、附加 preamble 数据和有界读取。 |
| Snapshot 与配置能力 | 未声明 | 按字段证明可查询性、适用性、写入副作用和完整恢复，不创建假完整模型。 |
| Autoset | 默认拒绝 | 只有在可保存并恢复 trigger、vertical 和 timebase 状态时另案评审。 |
| 其他写能力 | 未声明 | 每一类独立建模，不通过 raw SCPI 绕过 capability 与恢复门。 |

## 每项新能力的退出门

1. Core typed model 能准确表达该型号的返回值、不适用字段和错误语义。
2. Driver 方法、descriptor capability、profile、配置字段和权限保持一致。
3. 精确 FakeTransport 测试覆盖正常路径、异常 framing、无效枚举、timeout 与恢复失败。
4. Binary 读取明确 framing、payload 上限、trailing、分块策略和 resynchronization 边界。
5. 写入或采集控制具备 snapshot、readback、失败 cleanup、fresh verification 和必要锁停。
6. 受控实机验收记录型号、firmware、transport 和未覆盖范围，但不保存资源地址、序列号或原始数据。
7. 中英文 Current Reference、导航、生成式插件目录和 package tests 同步通过。
