# WaveBench Instrument Plugins

[English](doc/README_EN.md)

WaveBench 仪器插件的独立源码仓库。仓库计划按“一台仪器或一个仪器系列一个包”的方式，维护可由 WaveBench 发现和加载的外置仪器驱动。

## 当前状态

首批正式源码包已进入独立维护：`wavebench-rigol-ds1000z` 已完成离线生命周期和首轮实机验收，`wavebench-rigol-dg4000` 已完成协议迁移与离线验收，`wavebench-shengpu-sp3000a` 已进入 SP30120 query-only M3。WaveBench 0.7 已提供本地 package check、受管安装、状态查询、升级/降级、卸载和保守事务恢复；本仓库只维护插件源码，不重复实现安装器或远程 catalog。

## 计划结构

```text
packages/
├── wavebench-rigol-ds1000z/
├── wavebench-rigol-dg4000/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

每个 Python 插件作为独立 distribution，通过 `wavebench.instruments` entry point 注册 canonical driver ID。复杂协议可使用可信 Python 驱动；声明式 SCPI 包的可执行边界尚未冻结。

## 当前插件

- [`wavebench-rigol-ds1000z`](packages/wavebench-rigol-ds1000z/README.md)：四通道 RIGOL DS1104Z / DS1000Z 系列，canonical ID `rigol.ds1000z`。
- [`wavebench-rigol-dg4000`](packages/wavebench-rigol-dg4000/README.md)：双通道 RIGOL DG4202 / DG4000 系列，canonical ID `rigol.dg4202`。
- [`wavebench-shengpu-sp3000a`](packages/wavebench-shengpu-sp3000a/README.md)：Shengpu SP30120 query-only 扫频仪驱动，canonical ID `shengpu.sp30120`；只声明已验证的身份能力，曲线和写操作保持关闭。

## 安全边界

Python 插件会以运行 WaveBench 的用户权限执行，不是安全沙箱。安装或加载插件前必须信任其来源并审查代码。公开内容不得包含真实仪器地址、序列号、凭据、私钥、原始采集数据或实验室专用配置。

## 许可证

本仓库及其中维护的官方插件采用 [MIT License](LICENSE)。每个独立 distribution 也在包目录中携带许可证文件，并在包元数据中声明 SPDX `MIT`。

当前源码已公开维护；PyPI 发布、版本标签和正式贡献流程仍待后续确认。

## 开发环境

仓库提供标准 PEP 660 editable 开发环境工具。首次同步核心与正式插件后，普通源码修改无需重复安装；发布门禁仍使用真实 wheel 和一次性虚拟环境。参见[插件开发环境](doc/DEVELOPMENT.md)。
