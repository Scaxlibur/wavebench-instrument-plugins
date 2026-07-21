# Plugin packages

该目录用于放置独立的 WaveBench 仪器插件源码包。首个插件尚未确定，因此当前不创建示例实现，也不冻结额外 manifest 或 catalog 格式。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 不含真实设备资源、凭据、原始波形或私有实验记录。
