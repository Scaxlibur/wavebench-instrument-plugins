# Plugin packages

[English](README_EN.md)

该目录用于放置独立的 WaveBench 仪器插件源码包。当前正式包为 `wavebench-rigol-ds1000z`、`wavebench-rigol-dg4000`、LAN-only 的 `wavebench-rigol-dm3000`、当前 HEAD 基线的 `wavebench-rigol-dp800`、已完成 SocketIO 数据路径实机验收的 `wavebench-rohde-schwarz-rtm2000` 和 M3 query-only 的 `wavebench-shengpu-sp3000a`。前五个包是主包预装驱动的可选外置发行版；后续也按仪器或紧密相关系列逐包维护，但不以移除预装驱动为目标，也不在这里冻结第二套 manifest、安装器或 catalog 协议。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 独立可打包的 MIT 许可证文件和 SPDX 包元数据；
- 不含真实设备资源、凭据、原始波形或私有实验记录。
