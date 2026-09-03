# WaveBench SIGLENT SDS3000 插件

[English](README_EN.md)

本包面向早期 SIGLENT SDS3000 系列示波器，不包含名称带 `X` 或 `HD` 的后续产品。当前
production descriptor 只登记经过验证的 SDS3054。

## 从这里开始

- [查询当前版本、兼容范围、型号和 capability](../../doc/reference/plugin-catalog.md)
- [进入 SDS3000 插件文档](doc/README.md)
- [安装和管理 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## 当前边界

当前实现覆盖严格身份检查、错误寄存器读取、通道 coupling、二进制波形读取，以及单通道和
同次 acquisition 多通道采集。精确 capability、固件与选件限制、未支持项和协议处置以
production descriptor 及 [WaveBench capability 矩阵](doc/WAVEBENCH_CAPABILITY_MATRIX.md)为准。

SDS3054 使用 Teledyne LeCroy MAUI／X-Stream 命令体系。前面板选择 `TCP/IP (VICP)` 时必须
使用 `VICP::<host>::INSTR`；`TCPIP::<host>::INSTR` 表示 VXI-11，只能与前面板的
`LXI (VXI-11)` 模式配套。两种资源不能混用。

该身份和协议边界不能外推到任意 LeCroy 仪器、SDS3000X、SDS3000X HD 或其他 SIGLENT
SDS 系列。

## 安全边界

- 不使用 SDS3000X、SDS3000X HD 或其他新款 SIGLENT SDS 系列的 SCPI 手册推断本机协议。
- 不为缺失能力创建脱离 WaveBench 的公共接口；核心接口不足时单独提交建议。
- descriptor 导入不得连接仪器、扫描端口、创建文件或修改全局状态。
- driver 只能通过 WaveBench `DriverContext.open_transport()` 获取核心 transport。
- 仪器写入、输出切换和 acquisition trigger 不做盲目重试。
- 真实设备地址、序列号、凭据、原始波形、截图和实验日志不得提交。

## 开发与许可证

本地手册、审计顺序和发布边界见[插件文档](doc/README.md)。日常源码开发使用仓库级
[editable 开发环境](../../doc/DEVELOPMENT.md)。项目原创代码和文档采用 [MIT License](LICENSE)；
厂商资料保留原始权利状态，不属于公开 distribution。
