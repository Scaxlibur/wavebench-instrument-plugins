# DS1000Z 受控实机验收记录

[English](DS1000Z_HARDWARE_ACCEPTANCE_EN.md)

> 类型：Historical evidence
> 范围：2026-07-21 的 DS1104Z Plus 脱敏回归
> 当前能力入口：[生成式插件目录](../../../doc/reference/plugin-catalog.md)

本页保留特定设备、连接和时间点的验收结果，不替代 production descriptor，也不表示所有
DS1000Z 型号均完成相同的模拟精度或性能验证。

## 单通道与长记录

身份、空错误队列、CH1 高阻 coupling、NORM 1200 点、显式 autoscale、MAX／DMAX 2400000 点
分块读取、PNG 截图和 CH1／CH2 单次 acquisition 均通过。MAX／DMAX 各分为 10 个不超过
250000 点的块，前后错误队列均为空。

## 四通道路径

CH1–CH4 coupling 均可查询。一次 acquisition、一次 OPC 后，四个通道均返回 1200 点有限波形，
采样间隔均为 2 µs，前后错误队列为空。CH1 当时测得约 2.04 Vpp；CH2–CH4 未接独立测试信号，
因此本次只验收其通信和采集路径，不表示已经完成独立模拟幅度验收。

## 性能与证据边界

当时的 VXI-11 路径读取 2400000 点约需 135 秒。该结果证明功能完整性，不表示长记录性能已经
优化。验收没有向仓库写入真实配置、仪器资源、序列号、波形、截图或命令日志。

## 来源

`0.1.0` 初始实现从 WaveBench 主仓库的 DS1000Z 可安装插件试点迁移而来，保留原 canonical ID、
entry point、兼容范围和驱动语义。本仓库是迁移后外置包的源码事实源。
