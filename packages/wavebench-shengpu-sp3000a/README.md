# WaveBench Shengpu SP30120 插件

[English](README_EN.md)

面向 Shengpu SP30120 数字扫频仪的 WaveBench 外置插件。distribution 名沿用早期文档孵化阶段冻结的 `wavebench-shengpu-sp3000a`；它不表示将 SP30120 冒认为手册中的 SP30120A。

## 当前状态

0.2.0 在 M3 query-only 基线上加入 M3.5 的厂商专用、类型化 RF-OFF 控制：

- distribution：`wavebench-shengpu-sp3000a` 0.2.0
- canonical driver ID：`shengpu.sp30120`
- instrument kind：`sweep_analyzer`
- backend：WaveBench 核心 `serial` transport
- 已声明 capability：`sweep_analyzer.idn`
- WaveBench：`>=0.8,<0.9`

驱动另提供经实机验证的标量状态读取：RF 状态、输入/输出阻抗、中心/跨度与起止频率、CW 频率、频偏、扫描时间、线性/对数模式、连续/单次方式和外部触发状态。该方法只发送固定 allowlist 中的 query，不发送设置命令，也不自动重试设备私有错误。

M0–M3 命令认证在 RF OFF 下确认了 TRIM、参考位置、时钟显示、界面语言和外部触发五类可逆控制各连续 3/3 通过。0.2.0 将它们以厂商专用类型化 API 接入 `SP30120SweepAnalyzer`：`set_trim()`、`set_reference_position()`、`set_clock_display()`、`set_ui_language()` 和 `set_external_trigger()`；对应 read API 只使用各命令的稳定 query。它们不满足通用 SweepPlan 契约，因此 descriptor 仍只声明 `sweep_analyzer.idn`。

每次有效 setter 调用均在同一实例锁中执行一条 canonical 写命令：身份与 RF-OFF 前置检查、完整核心指纹、原值 query、写入、独立精确回读、RF-OFF 后置检查、核心指纹和身份复核。它不重试或自动恢复原值；写入后任一异常、回读差异、RF 非 OFF 或指纹变化都会永久锁存该实例的写路径，之后的写请求零 I/O 拒绝。关闭实例并独立核实仪器状态后才能重新打开。RF ON 只会触发互锁，不会被驱动自动关闭。

通用 `SweepAnalyzerSnapshot` 需要 `FUNC`、功率、平均和测量状态等完整有效计划，而目标固件尚不能稳定查询这些字段，因此 0.2.0 不声明 `sweep_analyzer.status`。`frequency_response` 是通用能力与数据域，不是第二种 instrument kind；M4 曲线 framing、点数、单位和频率轴未验收，所以也不声明 trace、marker、analysis、通用 configure 或 trigger 能力。驱动不提供 RF 输出、频率窗口、SweepPlan、任意 SCPI 或未认证参数写入。

M4 曲线协议确认已完成受控实机探索，但未通过。`OUTPRFORM?` 可重复返回完整 LF 终止的 1002-token 帧（501 个有限幅频候选值 + 501 个零值）；但标准与紧凑拼写的 MODE、POINT、CONT、幅相测量以及 20/200/730 点写入，均未改变独立 `OUTSTATEC?` 快照或曲线布局。该固件也不提供这些配置 query 的可验证读回。0.2.0 因此不声明 trace capability，也不将探索证据推广为频响数据契约。

M4 已加入一个尚未接入 descriptor/driver 的严格离线 parser：它按 LF 累积完整帧，要求单模式恰好 P 个有限值、ALL 恰好 2P 个有限值，并拒绝短帧、长帧、坏 token、非 ASCII、NaN/Inf、尾随数据和无终止符帧。该 parser 已用私有 501+501 完整帧和 739-token 截断帧回归，但这只证明帧校验逻辑，不代表写命令、模式切换、点数、单位、状态恢复或 trace capability 已通过实机验收。

详见[远控协议与能力审计](doc/PROTOCOL_AUDIT.md)、[RS-232 只读协议验收](doc/RS232_READONLY_ACCEPTANCE.md)、[命令认证计划](doc/COMMAND_CERTIFICATION_PLAN.md)和[逐命令矩阵](doc/COMMAND_CERTIFICATION_MATRIX.md)。未达到矩阵门禁的手册命令不会进入驱动。

## 安全边界

- descriptor 导入和 registry 发现执行零仪器 I/O；factory 仅通过 `DriverContext.open_transport()` 打开一次核心 transport。
- 身份校验只接受实机返回的 `SHENGPU SP3000 Series Digital Sweeper` 家族字符串，并仅容忍大小写、空白和末尾句点差异；该字符串本身不能证明子型号或固件版本。
- `ERRORNo00`–`ERRORNo08` 和目标固件未文档化的 `Error` 都是确定性失败，不自动重试。
- 0.2.0 仅提供上述五项厂商专用 RF-OFF setter；不提供裸 SCPI、曲线读取、通用状态恢复、Local 切换、RF 控制或其它写命令。
- 真实串口路径、序列号和原始日志不得写入公开仓库。

本包当前面向 WaveBench `v0.8.0` release，不能与 `v0.7.0` 配套运行，也不自动声明兼容未来 `0.9`。

## 手册投放位置

将本地 Markdown 手册复制到：

```text
doc/vendor-local/SP3000A_manual.md
```

`doc/vendor-local/` 中除说明文件外的内容会被 Git 忽略，整个目录也被 sdist 构建规则排除，不会随仓库推送或公开发行包发布。我们基于手册重新整理的能力矩阵、通信参数、SCPI 摘要、曲线格式和验收计划将放在 `doc/` 中，并清楚区分“手册声明”和“实机验证”。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地保存的厂商手册及其转写不因此获得 MIT 授权，也不属于公开 distribution 的发布内容。
