# WaveBench Instrument Plugins

[English](doc/README_EN.md)

WaveBench 仪器插件的独立源码仓库。仓库计划按“一台仪器或一个仪器系列一个包”的方式，维护可由 WaveBench 发现和加载的外置仪器驱动。

## 当前状态

正式源码包已进入独立维护：`wavebench-rigol-ds1000z`、`wavebench-rigol-dg4000`、LAN-only 的 `wavebench-rigol-dm3000`、`wavebench-rigol-dp800` 与 `wavebench-rohde-schwarz-rtm2000` 已完成离线、受管生命周期和受控实机验收；`wavebench-shengpu-sp3000a` 已进入 SP30120 M3.5，保留最小 query-only descriptor 并提供五项经认证的厂商专用 RF-OFF 控制；`wavebench-siglent-sdg2000x` 已进入 M2，`SDG2122X` 的严格只读身份和 CH1/CH2 状态已通过实机验收，写能力保持关闭。前五个包是 WaveBench 预装驱动的可选外置发行版，用于独立升级、特定 transport 或后续扩展，并不替代或淘汰主包的开箱即用基线。WaveBench v0.8.0 已提供本地 package check、受管安装、状态查询、升级/降级、卸载和保守事务恢复；本仓库只维护插件源码，不重复实现安装器或远程 catalog。

> [!IMPORTANT]
> WaveBench `v0.7.0` 尚不包含 Instrument API V2、受管插件生命周期或覆盖槽位。本仓库当前包面向 WaveBench `v0.8.0` release，并统一要求 `wavebench>=0.8,<0.9`；它们不能与 `v0.7.0` 配套运行，也不能自动假定兼容未来 `0.9`。

## 计划结构

```text
packages/
├── wavebench-rigol-dg4000/
├── wavebench-rigol-dm3000/
├── wavebench-rigol-dp800/
├── wavebench-rigol-ds1000z/
├── wavebench-rohde-schwarz-rtm2000/
├── wavebench-shengpu-sp3000a/
├── wavebench-siglent-sdg2000x/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

每个 Python 插件作为独立 distribution，通过 `wavebench.instruments` entry point 注册 canonical driver ID。复杂协议可使用可信 Python 驱动；声明式 SCPI 包的可执行边界尚未冻结。

## 预装基线与外置发行

WaveBench 主包长期预装 RTM2000、DS1000Z、DG4000、DP800 和 DM3000 五个仪器族。外置包只在用户显式安装并配置 canonical ID 时提供可选实现；内置短 alias 始终留在主包。DG4000、DM3000、DP800 与 RTM2000 通过核心按 canonical ID + distribution 双重白名单控制的覆盖槽位切换，卸载后 canonical ID 自动恢复到内置实现。DS1000Z 外置包使用独立 canonical `rigol.ds1000z`，内置 `ds1104` / `ds1000z` alias 不受影响。源码历史中仍可能使用“迁移槽位”一词，它只表示受限覆盖机制，不表示预装驱动计划移除。

## 当前插件

- [`wavebench-rigol-ds1000z`](packages/wavebench-rigol-ds1000z/README.md)：四通道 RIGOL DS1104Z / DS1000Z 系列，canonical ID `rigol.ds1000z`。
- [`wavebench-rigol-dg4000`](packages/wavebench-rigol-dg4000/README.md)：双通道 RIGOL DG4202 / DG4000 系列，canonical ID `rigol.dg4202`。
- [`wavebench-rigol-dm3000`](packages/wavebench-rigol-dm3000/README.md)：LAN-only RIGOL DM3000 / DM3058 数字万用表，canonical ID `rigol.dm3000`；短 alias 保留内建双 backend fallback。
- [`wavebench-rigol-dp800`](packages/wavebench-rigol-dp800/README.md)：RIGOL DP800 / DP832 / DP832A 可编程直流电源，canonical ID `rigol.dp800`；短 alias 保留内建 fallback。
- [`wavebench-rohde-schwarz-rtm2000`](packages/wavebench-rohde-schwarz-rtm2000/README.md)：R&S RTM2000 / RTM2032 示波器，canonical ID `rohde-schwarz.rtm2032`；双通道 `DEF` / `MAX` / `DMAX`、autoscale、截图与恢复实机验收已完成。
- [`wavebench-shengpu-sp3000a`](packages/wavebench-shengpu-sp3000a/README.md)：Shengpu SP30120 扫频仪驱动，canonical ID `shengpu.sp30120`；descriptor 只声明身份能力，另有五项经认证、类型化、RF-OFF 的厂商专用控制，曲线及通用配置仍关闭。
- [`wavebench-siglent-sdg2000x`](packages/wavebench-siglent-sdg2000x/README.md)：SIGLENT SDG2042X / SDG2082X / SDG2122X 函数/任意波形发生器，canonical ID `siglent.sdg2000x`；M2 声明身份和严格只读 CH1/CH2 状态查询，`SDG2122X` 实机通过，写能力尚未开放。

## 安全边界

Python 插件会以运行 WaveBench 的用户权限执行，不是安全沙箱。安装或加载插件前必须信任其来源并审查代码。公开内容不得包含真实仪器地址、序列号、凭据、私钥、原始采集数据或实验室专用配置。

## 许可证

本仓库及其中维护的官方插件采用 [MIT License](LICENSE)。每个独立 distribution 也在包目录中携带许可证文件，并在包元数据中声明 SPDX `MIT`。

当前源码已公开维护；PyPI 发布、版本标签和正式贡献流程仍待后续确认。

## 开发环境

仓库提供标准 PEP 660 editable 开发环境工具。首次同步核心与正式插件后，普通源码修改无需重复安装；发布门禁仍使用真实 wheel 和一次性虚拟环境。参见[插件开发环境](doc/DEVELOPMENT.md)。
