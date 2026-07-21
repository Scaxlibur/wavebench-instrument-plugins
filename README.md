# WaveBench Instrument Plugins

[English](doc/README_EN.md)

WaveBench 仪器插件的独立源码仓库。仓库计划按“一台仪器或一个仪器系列一个包”的方式，维护可由 WaveBench 发现和加载的外置仪器驱动。

## 当前状态

仓库目前只有待开发骨架，尚未发布任何插件、catalog 或安装接口。包格式和生命周期将在 WaveBench 的本地插件包管理契约稳定后逐步落地。

## 计划结构

```text
packages/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

每个 Python 插件将作为独立 distribution，通过 `wavebench.instruments` entry point 注册 canonical driver ID。复杂协议可使用可信 Python 驱动；声明式 SCPI 包的可执行边界尚未冻结。

## 安全边界

Python 插件会以运行 WaveBench 的用户权限执行，不是安全沙箱。安装或加载插件前必须信任其来源并审查代码。公开内容不得包含真实仪器地址、序列号、凭据、私钥、原始采集数据或实验室专用配置。

## 开发状态说明

当前尚未选择开源许可证，也没有配置远程仓库。正式发布、兼容范围和贡献流程将在首个插件进入开发后补充。
