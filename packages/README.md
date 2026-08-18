# Plugin packages

[English](README_EN.md)

该目录用于放置独立的 WaveBench 仪器插件源码包。当前还包含 `wavebench-rigol-mso8000`：首个目标为 MSO8104，`0.2.0` 完成 `scope.idn` 与 `scope.channel_coupling` 离线合同，未连接实机。DG4000、DM3000、DP800、DS1000Z 与 RTM2000 是主包预装驱动的可选外置发行版；MSO8000 与 Shengpu SP3000A 使用独立 canonical ID。后续仍按仪器或紧密相关系列逐包维护，不在这里定义第二套 manifest、安装器或 catalog 协议。

这些包面向 WaveBench `0.8.x`，各自按实际使用的公开接口声明最低版本，并统一排除未来 `0.9`。MSO8000 当前要求 `wavebench>=0.8.22,<0.9`。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 独立可打包的 MIT 许可证文件和 SPDX 包元数据；
- 不含真实设备资源、凭据、原始波形或私有实验记录。
