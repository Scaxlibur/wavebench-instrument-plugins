# WaveBench Instrument Plugins

[English](doc/README_EN.md)

WaveBench 仪器插件的独立源码仓库。仓库计划按“一台仪器或一个仪器系列一个包”的方式，维护可由 WaveBench 发现和加载的外置仪器驱动。

## 当前状态

首批正式源码包已进入独立维护：`wavebench-rigol-ds1000z` 已完成离线生命周期和首轮实机验收，`wavebench-rigol-dg4000` 已完成协议迁移与离线验收。WaveBench 0.7 已提供本地 package check、受管安装、状态查询、升级/降级、卸载和保守事务恢复；本仓库只维护插件源码，不重复实现安装器或远程 catalog。

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

## 安全边界

Python 插件会以运行 WaveBench 的用户权限执行，不是安全沙箱。安装或加载插件前必须信任其来源并审查代码。公开内容不得包含真实仪器地址、序列号、凭据、私钥、原始采集数据或实验室专用配置。

## 开发状态说明

仓库尚未配置远程，也未选择仓库级开源许可证。DS1000Z 包保留其从 WaveBench 试点迁移而来的 MIT 包元数据；DG4000 包尚未选择许可证。正式发布和贡献流程仍待确认。
