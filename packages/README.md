# Plugin packages

[English](README_EN.md)

该目录用于放置独立的 WaveBench 仪器插件源码包。当前包含 `wavebench-rigol-ds1000z` 和 `wavebench-rigol-dg4000`；后续按仪器或紧密相关系列逐包迁移，不在这里冻结第二套 manifest、安装器或 catalog 协议。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 不含真实设备资源、凭据、原始波形或私有实验记录。
