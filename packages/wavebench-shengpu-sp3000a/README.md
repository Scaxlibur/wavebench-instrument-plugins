# WaveBench Shengpu SP30120 插件

[English](README_EN.md)

面向 Shengpu SP30120 数字扫频仪的 WaveBench 外置插件。distribution 名沿用早期文档孵化阶段冻结的 `wavebench-shengpu-sp3000a`；它不表示将 SP30120 冒认为手册中的 SP30120A。

## 当前状态

M3 已建立可安装的 query-only distribution、V2 entry point、驱动、FakeTransport 测试和 wheel 生命周期测试：

- distribution：`wavebench-shengpu-sp3000a` 0.1.0
- canonical driver ID：`shengpu.sp30120`
- instrument kind：`sweep_analyzer`
- backend：WaveBench 核心 `serial` transport
- 已声明 capability：`sweep_analyzer.idn`
- WaveBench：`>=0.8,<0.9`

驱动另提供经实机验证的标量状态读取：RF 状态、输入/输出阻抗、中心/跨度与起止频率、CW 频率、频偏、扫描时间、线性/对数模式、连续/单次方式和外部触发状态。该方法只发送固定 allowlist 中的 query，不发送设置命令，也不自动重试设备私有错误。

通用 `SweepAnalyzerSnapshot` 需要 `FUNC`、功率、平均和测量状态等完整有效计划，而目标固件尚不能稳定查询这些字段，因此 0.1.0 不声明 `sweep_analyzer.status`。`frequency_response` 是通用能力与数据域，不是第二种 instrument kind；M4 曲线 framing、点数、单位和频率轴未验收，所以也不声明 trace、marker 或 analysis 能力。配置、触发和 RF 输出方法完全不暴露。

M4 曲线协议确认已获得受控实机测试授权并进入开发，但尚未通过。历史探索曾收到一组无完整终止边界的短帧，以及多组“501 个有效幅度候选值 + 501 个零值”的 1002-token 帧；这些结果不能证明 AMPT、PHASE、ALL 模式切换生效，也不能证明点数、单位或控制响应与异步曲线流已正确分离。0.1.0 因此继续保持 query-only，不把探索证据当作 trace capability。

详见[远控协议与能力审计](doc/PROTOCOL_AUDIT.md)和 [RS-232 只读协议验收](doc/RS232_READONLY_ACCEPTANCE.md)。

## 安全边界

- descriptor 导入和 registry 发现执行零仪器 I/O；factory 仅通过 `DriverContext.open_transport()` 打开一次核心 transport。
- 身份校验只接受实机返回的 `SHENGPU SP3000 Series Digital Sweeper` 家族字符串，并仅容忍大小写、空白和末尾句点差异；该字符串本身不能证明子型号或固件版本。
- `ERRORNo00`–`ERRORNo08` 和目标固件未文档化的 `Error` 都是确定性失败，不自动重试。
- 0.1.0 不提供裸 SCPI、写命令、曲线读取、状态恢复、Local 切换或 RF 控制。
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
