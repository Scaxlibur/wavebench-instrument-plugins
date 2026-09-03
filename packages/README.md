# Plugin packages

[English](README_EN.md)

`packages/` 保存本仓库维护的独立 WaveBench 插件 distribution。每个子目录对应一台仪器或一个紧密相关的型号系列。

## 查询插件

[生成式插件目录](../doc/reference/plugin-catalog.md)列出所有 distribution、driver ID、登记型号、WaveBench 兼容范围和 production descriptor 已声明的 capability。该页面由包内元数据生成，不在本页重复维护状态表。

进入具体包的 README，可以继续查看：

- 适用型号与连接方式；
- 最小配置和只读起步示例；
- 型号特有的安全边界与限制；
- 当前 Reference、历史验收证据和厂商资料入口。

## 包合同

每个正式包至少包含：

- 独立的 `pyproject.toml`、元数据版本和 `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- production descriptor 及不访问真实仪器的离线测试；
- 中英文用户入口；
- 独立可打包的 MIT 许可证文件和 SPDX 包元数据；
- 不含真实设备资源、凭据、原始波形或私有实验记录的公开内容。

一个 distribution 可以声明多个有明确用途的 driver entry point。未进入 production descriptor 的 capability 不得由 README、里程碑或验收记录提前声明为当前能力。

## 新增插件

新增插件前应阅读 WaveBench Core 的[插件开发指南](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md)和[仪器驱动指南](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/instrument-drivers.md)。本仓库的 editable 安装、检查和测试方式见[开发环境说明](../doc/DEVELOPMENT.md)。
