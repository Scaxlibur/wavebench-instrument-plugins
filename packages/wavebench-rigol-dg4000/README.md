# WaveBench RIGOL DG4000 插件

[English](README_EN.md)

面向双通道 RIGOL DG4202 和兼容 DG4000 系列函数/任意波形发生器的 WaveBench 可执行仪器插件。

## 身份与兼容范围

- distribution：`wavebench-rigol-dg4000`
- canonical driver ID：`rigol.dg4202`
- WaveBench：`>=0.8,<0.9`
- Python：`>=3.11`
- transport backend：`pyvisa`

当前包面向 WaveBench `v0.8.0` release，不能与 `v0.7.0` 配套运行，也不自动声明兼容未来 `0.9`。

该插件不声明 alias。安装后，显式 canonical ID `rigol.dg4202` 选择外置实现；短 alias `dg4202` 始终选择 WaveBench 内建 fallback。卸载插件后，canonical ID 也回退到内建实现。

## 能力

- `*IDN?`、错误队列与 CH1/CH2 状态读取；
- 固定频率、函数、VPP 幅度、方波占空比和显式输出控制；
- 只读任意波形 SCPI 能力探测；
- 使用 WaveBench 公共 `DG4000DacBlock` 契约上传已校验的 DAC14 binary block。

WaveBench 核心继续负责波形文件加载、归一化、DAC14 编码、幅度安全限制、Service、run plan、状态恢复和 artifact。插件不复制这些策略。

完整的厂商手册命令域、当前公开 API、离线/实机证据和默认拒绝的高风险命令见
[DG4000 功能覆盖矩阵](doc/DG4000_COVERAGE_MATRIX.md)。分阶段退出门和硬件验收边界见
[DG4000 覆盖里程碑](doc/DG4000_COVERAGE_MILESTONES.md)。本地厂商手册保存在被忽略的
`doc/vendor-local/`，不进入发行包。

## 安全边界

descriptor 导入不连接仪器。factory 只通过 `DriverContext` 打开当前配置的 transport。默认离线测试不扫描资源、不连接仪器，也不发送真实 SCPI。输出控制、任意波形上传和其他写操作不会盲目重试。

`0.3.0` 的 M1/M2/M4 离线实现已收口：所有 I/O 使用同一可重入锁，固定波写入采用
写前快照、逐步回读、off-first 恢复和歧义写锁存；DAC14 上传仅允许目标通道已 OFF、
FIX 且 sweep OFF，并明确把被覆盖的 volatile USER 波表视为不可恢复副作用。DG4202
固件 `00.01.14` 已通过 M1/M2 实机退出门；M4 的 CH1 完整退出门及 CH2 协议/恢复门已
通过，CH2 模拟形状验收仍待接入高阻示波器。结论不外推到其它型号、固件或通道接线。

示例使用文档保留地址：

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.30::INSTR"

[source]
driver = "rigol.dg4202"
model_hint = "DG4202"
default_channel = 1
check_errors = true
```

## 许可证

本插件采用 [MIT License](LICENSE)。

## 实机验收边界

早期验收曾使用外置 `wavebench-rigol-dg4000` 驱动 DG4202 CH1 输出 1 kHz、1 Vpp 正弦，并由外置 `wavebench-rigol-ds1000z` 驱动 DS1104Z Plus CH1 闭环采集。示波器 CH1 为 AC 耦合、固定高阻输入；DEF 波形返回 1200 点，WaveBench 测得 1000.000 Hz、1.008 Vpp。两台仪器前后错误队列均为空，发生器 CH1 原状态在 `finally` 路径恢复并回读确认。

2026-07-27 在 DG4202 固件 `00.01.14` 上重新执行当前 `0.3.0` 工作树验收：M1 对
CH1/CH2 完成合计 24 查询、0 写入的严格状态 profile；M2 对两路分别完成 OFF、临时
SQU/不同固定频率/0.8 Vpp/37% duty、显式 ON→OFF、off-first 恢复及新会话逐字段复核。
两路最终均恢复为原始 SIN、1 kHz、5 Vpp、0 V offset、FIX、sweep OFF、输出 ON。

M4 对 CH1/CH2 分别在输出 OFF 时上传 64 点 little-endian DAC14 三角波，回读
USER/1 kHz/1 Vpp/0 V、确认错误队列为空，并在新会话确认原态恢复。CH1 随后以 2 Vpp
显式输出到高阻 RTM2032：10,000 点采集测得 997.26 Hz、2.16 Vpp，三角模板 RMSE
0.0390 V，约为正弦模板 RMSE 的 49.2%；恢复后复测原正弦为 998.25 Hz、5.12 Vpp。
CH2 当前接 DMM，因此只验收协议、回读和恢复，不宣称模拟波形形状通过。RTM2032
抓波会发送受控的传输格式/点数设置，不计作示波器零写入会话。两路 volatile USER
内容均被本次上传覆盖，这是已知且不可恢复的副作用；未保存真实地址、序列号、原始波形
或命令日志。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rigol-dg4000/tests
python -m ruff check packages/wavebench-rigol-dg4000
python -m wavebench plugin package check packages/wavebench-rigol-dg4000
python -m wavebench plugin install packages/wavebench-rigol-dg4000 --dry-run
```

日常源码开发可使用仓库级 [editable 开发环境](../../doc/DEVELOPMENT.md)；正式验收仍使用真实 wheel 和一次性虚拟环境。

真实仪器地址、序列号、波形、截图和命令日志不得提交。

## 来源

- `0.1.0`：从 WaveBench 内建 DG4202 协议实现迁移；核心继续持有 Service 和安全策略。
- `0.2.0`：增加 M0–M12 双语覆盖里程碑与发行包防泄漏回归；不扩大 capability。
- `0.3.0`：交付现有 API 的严格收口、固定波事务化和 DAC14 fail-closed 实现；DG4202 `00.01.14` 的 M1/M2 与 M4 CH1 实机退出门通过，M4 CH2 仅协议/恢复通过，未扩大 capability。
