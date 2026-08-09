# RIGOL DG1000 覆盖矩阵

[English](DG1000_COVERAGE_MATRIX_EN.md)

本文记录 `wavebench-rigol-dg1000` `0.1.0` 的公开能力边界。默认门禁只使用
FakeTransport、wheel 检查和受管安装生命周期检查；真实仪器验收必须单独授权，并且只能提交脱敏
结论，不能提交真实 resource、序列号、波形、截图或命令日志。

## 型号范围

| 型号族 | 命令布局 | 当前状态 |
| --- | --- | --- |
| DG1022 / DG1022A | legacy `:CH2` 后缀 | FakeTransport 覆盖；未声明实机验收完成 |
| DG1022Z / DG1032Z / DG1062Z | `:SOUR<n>:` 前缀 | FakeTransport 覆盖；DG1032Z 可作为后续闭环实机门禁 |
| DG1000 / DG1000Z 兼容型号 | 按 IDN 选择已知布局 | 未识别型号 fail closed |

## Capability 边界

| WaveBench capability | 状态 | 说明 |
| --- | --- | --- |
| `source.idn` | 已声明 | `*IDN?` 只读身份 |
| `source.errors` | 已声明 | `SYST:ERR?` 错误队列 |
| `source.status` | 已声明 | CH1/CH2 basic status，包括输出、函数、频率、VPP、offset、phase、sweep 和方波占空比 |
| `source.set_frequency` | 已声明 | 固定频率设置；可按配置显式关闭 sweep |
| `source.set_function` | 已声明 | 基本函数设置 |
| `source.set_amplitude_vpp` | 已声明 | VPP 幅度设置 |
| `source.set_square_duty_cycle` | 已声明 | 方波占空比设置 |
| `source.output` | 已声明 | 显式输出开关 |
| `source.harmonic_profile` / `source.harmonic_configure` | 未声明 | DG1000 加法/谐波叠加功能不在支持面；启用时基波与谐波实际输出大概率与设置值不同，不准确 |
| `source.arbitrary_upload` | 未声明 | 不复用 DG4000/DG4202 任意波上传路径 |
| modulation / burst / counter / full sweep profile | 未声明 | 不把厂商菜单能力映射成 WaveBench 通用 capability |

## 验收原则

- capability 只代表已实现并测试的行为；
- descriptor 导入不得连接仪器、扫描端口或发送 SCPI；
- factory 只能通过 `DriverContext.open_transport()` 打开当前配置的 transport；
- 写入失败后不自动重试输出、trigger 或已开始消费响应的数据路径；
- 实机验收应记录可恢复状态、外部测量证据和输出关闭检查，并在公开提交中脱敏。
