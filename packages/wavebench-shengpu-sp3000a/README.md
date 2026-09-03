# WaveBench Shengpu SP30120 插件

[English](README_EN.md)

面向 Shengpu SP30120 数字扫频仪的 WaveBench 外置插件。distribution 名沿用早期文档孵化阶段冻结的 `wavebench-shengpu-sp3000a`；它不表示将 SP30120 冒认为手册中的 SP30120A。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 SP3000A 开发与证据文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 当前边界

production descriptor 只声明 `sweep_analyzer.idn`。driver 还提供经过命令认证的标量状态读取
和五项厂商专用 RF-OFF 控制，但它们不构成通用 SweepPlan、trace、analysis、configure 或
trigger capability。精确命令状态、实机证据和拒绝边界见开发文档中的认证矩阵与验收记录。

当前没有 raw SCPI、RF 输出控制或未经认证的参数写入。曲线 framing、点数、单位和频率轴尚未
形成可验证合同，因此探索结果不会作为频响能力公开。

## 安全边界

- descriptor 导入和 registry 发现执行零仪器 I/O；factory 仅通过 `DriverContext.open_transport()` 打开一次核心 transport。
- 身份校验只接受实机返回的 `SHENGPU SP3000 Series Digital Sweeper` 家族字符串，并仅容忍大小写、空白和末尾句点差异；该字符串本身不能证明子型号或固件版本。
- `ERRORNo00`–`ERRORNo08` 和目标固件未文档化的 `Error` 都是确定性失败，不自动重试。
- 只有认证矩阵列出的厂商专用 RF-OFF setter 可执行写入；不提供裸 SCPI、曲线读取、通用状态恢复、Local 切换、RF 控制或其它写命令。
- 真实串口路径、序列号和原始日志不得写入公开仓库。

## 开发与许可证

本地厂商资料的存放和发布边界见[开发文档](doc/README.md)。日常源码开发使用仓库级
[editable 开发环境](../../doc/DEVELOPMENT.md)。项目原创代码和文档采用 [MIT License](LICENSE)；
厂商资料不属于公开 distribution。
