# Plugin packages

[English](README_EN.md)

该目录用于放置独立的 WaveBench 仪器插件源码包。当前可安装包包括五个预装驱动的可选外置发行版、M3 query-only 的 `wavebench-shengpu-sp3000a`、已完成 Source V2 C3 候选审计的 `wavebench-siglent-sdg2000x`，以及已完成 SDS804X HD 波形、PNG 截图和独立采集控制验收的 `wavebench-siglent-sds800x-hd` `0.6.0`。后续仍按仪器或紧密相关系列逐包维护，不以移除预装驱动为目标，也不在这里冻结第二套 manifest、安装器或 catalog 协议。

这些包分别声明各自的 WaveBench `0.8.x` 最低版本；SDS800X HD `0.6.0` 要求 `wavebench>=0.8.23,<0.9`，SDG2000X `0.8.2` 要求 `wavebench>=0.8.24,<0.9`。它们不能与 `v0.7.0` 配套运行，也不会把未来 `0.9` 自动视为兼容版本。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 独立可打包的 MIT 许可证文件和 SPDX 包元数据；
- 不含真实设备资源、凭据、原始波形或私有实验记录。

## 孵化目录

- [`wavebench-siglent-sds3000`](wavebench-siglent-sds3000/README.md)：正在审计 MAUI 编程手册的早期 SIGLENT SDS3000 系列目录，首个验证型号为 SDS3054。

孵化目录在协议边界冻结前不提供 `pyproject.toml`、entry point 或 capability。仓库级开发环境会跳过这类目录，避免尚未完成审计的驱动进入正式插件集合。
