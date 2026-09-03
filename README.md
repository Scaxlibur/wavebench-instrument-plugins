# WaveBench Instrument Plugins

[English](doc/README_EN.md)

本仓库维护可独立安装的 WaveBench 仪器插件。每个插件包面向一台仪器或一个紧密相关的型号系列，通过 `wavebench.instruments` entry point 向 WaveBench 注册 driver。

## 从这里开始

- [查询插件、型号、兼容范围和已声明 capability](doc/reference/plugin-catalog.md)
- [进入各插件包](packages/README.md)
- [使用 WaveBench Core 安装和管理插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)
- [开发 WaveBench 插件](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md)
- [配置本仓库的 editable 开发环境](doc/DEVELOPMENT.md)
- [查阅插件侧接口提案与历史记录](doc/rfcs/README.md)
- [查阅跨插件验收与历史证据](doc/evidence/README.md)

## 仓库职责

本仓库负责具体型号、厂商 SCPI、私有参数、仪器 quirks、型号 profile、capability 声明和实机验证证据。每个包的 `pyproject.toml` 与 production descriptor 是版本、入口点、兼容范围和当前 capability 的权威来源；[插件目录](doc/reference/plugin-catalog.md)由这些元数据生成。

WaveBench Core 负责通用 CLI、插件安装和管理、配置模型、run plan、artifact、安全合同、session 与 recovery，以及插件 API。这里的说明只给出型号相关边界，通用使用方法链接到 [WaveBench Core 文档](https://github.com/Scaxlibur/wavebench/tree/master/docs)。

## 包结构

每个插件是独立的 Python distribution，可以声明一个或多个 canonical driver ID：

```text
packages/wavebench-<vendor>-<instrument>/
├── pyproject.toml
├── README.md
├── README_EN.md
├── src/
└── tests/
```

包级 README 说明适用型号、最小配置和安全边界；精确 capability 由 descriptor 声明；里程碑、RFC 和验收记录用于追溯设计与实机证据，不替代当前 Reference。

## 安全边界

Python 插件以运行 WaveBench 的用户权限执行，不是安全沙箱。安装或加载前应确认来源并审查代码。公开内容不得包含真实仪器地址、序列号、凭据、私钥、原始采集数据或实验室专用配置。

默认测试使用 fake transport，不连接真实仪器。任何实机操作仍须单独授权，并遵守 WaveBench Core 的安全合同与恢复要求。

## 开发与贡献

本仓库的开发环境、测试和打包入口见[开发环境说明](doc/DEVELOPMENT.md)。新增或修改插件时，还应遵循 Core 的[插件开发指南](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md)和[仪器驱动指南](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/instrument-drivers.md)。

## 许可证

本仓库及其中维护的官方插件采用 [MIT License](LICENSE)。每个独立 distribution 也在包目录中携带许可证文件，并在包元数据中声明 SPDX `MIT`。
