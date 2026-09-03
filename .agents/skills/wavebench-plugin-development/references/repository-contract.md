# Repository contract

在新增插件包，或者修改 descriptor、entry point、兼容范围与 capability 时读取本页。这里描述生产插件必须保持一致的事实，不规定所有包采用相同实现。

## Canonical sources

| 事实 | 权威来源 | 衍生内容 |
| --- | --- | --- |
| 厂商声明、命令与参数 | 本地 `doc/vendor-local/` 中的原厂资料 | 项目原创手册基线与协议审计 |
| distribution、版本、Python 与 Core 依赖 | 包内 `pyproject.toml` | wheel metadata、生成式目录、README 摘要 |
| production entry point | `[project.entry-points."wavebench.instruments"]` | 插件发现结果、生成式目录 |
| `driver_id`、kind、型号、backend、资源 scheme | production descriptor | CLI 查询、生成式目录 |
| capability、profile、权限与配置字段 | production descriptor 和匹配的 Core 模型 | 用户文档摘要 |
| SCPI、型号差异、parser 与恢复行为 | driver、profile 和测试 | How-to、coverage reference |
| 当前安装和实际加载结果 | 构建产物与隔离环境中的 WaveBench 检查 | 验收记录 |

厂商资料和转换稿不进入 Git 或发行物；项目原创审计只保留可复核的标识、映射、边界和处置，不复制手册正文。README、coverage matrix、milestone、archive 与 evidence 不能覆盖生产源码来源。需要改生产事实时先改源码，再更新或生成衍生内容。

## Core and plugin ownership

WaveBench Core 负责通用仪器抽象、公共 capability 模型、配置和 artifact 模型、插件加载协议、session、恢复与安全合同。本仓负责具体型号、厂商 SCPI、私有参数、型号 profile、quirk、production capability 声明和型号级证据。

发现公共模型不足时，先把缺口表述为 Core 合同问题。本仓可以准备私有 typed 方法、兼容实现或实验性证据，但不能在插件中复制一份平行公共模型，也不能把尚未进入匹配 Core 版本的字段声明为 capability。现有 kind 的通用新接口按插件侧 Draft／Proposed 和 Core Accepted 流程处理；全新 kind 允许先用一个 manual-backed 目标建立最小 Identity 接入。

## Package anatomy

新驱动可以先以只有 `doc/` 的孵化目录整理手册和协议；建立 `pyproject.toml` 后才成为正式包。正式包位于 `packages/wavebench-*`，至少核对：

- `pyproject.toml`：build backend、distribution、版本、Core 依赖、entry point 与构建包含范围。
- `src/<module>/__init__.py`：只重导出 entry point 目标，不在导入时建立连接。
- `src/<module>/descriptor.py`：静态描述 production 合同，并把 transport 创建留给 factory。
- `src/<module>/driver.py` 及辅助模块：型号协议、解析、安全检查和状态语义。
- `tests/`：descriptor 导入、driver 行为、FakeTransport、失败路径、wheel 安装／发现／卸载，以及当前包已有的附加生命周期门禁。

`doc/`、`conformance/`、`tools/` 和额外模块按真实需求存在，不是新包的固定模板。先参考仪器类型相近且合同相近的包；不要复制某一型号的完整目录后再删。

## Metadata and entry-point alignment

对每个 `[project.entry-points."wavebench.instruments"]` 项逐项检查：

1. entry point 名称与 descriptor 的 `driver_id` 表达同一生产身份。
2. entry point 目标可导入且返回 `InstrumentDescriptor`；公共重导出与目标名称一致。
3. descriptor 的 `distribution`、`version` 与 `pyproject.toml` 一致。
4. descriptor 的 `source` 能追溯到对应 entry point。
5. `wavebench_min_version`、`wavebench_max_version` 与 Core dependency specifier 没有矛盾。
6. build 配置确实包含目标 Python 包、许可证和有意进入发行物的资源。

允许一个 distribution 暴露多个用途明确的 entry point，例如 legacy、opt-in 或 workspace 变体。验证实际集合，不能把「单 entry point」写成仓库级不变量。

版本或 entry point 变化后，还要检查开发环境状态、生成式插件目录、package check，以及包内针对 wheel、sdist 或生命周期的现有测试。

## Descriptor import boundary

导入模块、解析 entry point 和调用 `descriptor()` 都必须保持离线且确定：

- 不扫描 VISA、LAN、USB 或串口资源。
- 不打开 transport，不发送 query、write、trigger 或 capture。
- 不读取实验室配置、环境凭据或机器私有文件。
- 不依赖可变网络状态、当前工作目录或未声明的本地资料。
- 不在导入时执行会改变全局状态的注册或迁移。

factory 才能通过 `DriverContext.open_transport()` 取得 transport。选项必须从 `OptionSpec`、`context.options` 或 Core 明确提供的设置读取，并在建立 driver 前完成类型与范围检查。

为 descriptor 和实际 wheel 的发现过程保留「零仪器 I/O」回归测试。失败时修正导入边界，不用 mock 掩盖生产导入副作用。

## Capability declaration gate

### Mandatory Identity

每个正式 descriptor 必须先声明 `<kind>.idn`，其他 capability 不得绕过 Identity-first：

- Core 已注册对应 kind 和 Identity capability。
- 手册明确 query、响应边界和目标型号／系列时，可以使用 manual-backed identity。
- parser 必须严格匹配厂商、系列和型号，不从系列响应猜测未返回的具体型号。
- descriptor 与 factory 不得发起 Identity I/O；Identity query 只能经 `idn()` 实现路径发起，其他具有明确 I/O 合同的 driver 操作可以将其用于身份预检。
- FakeTransport 和实际 wheel 生命周期验证正常、畸形、错误目标与零 I/O 加载。
- 没有实机记录时明确标记 hardware-not-verified，不能把 manual-backed 写成实机通过。

### Other capabilities

production capability 至少需要同时满足：

1. 匹配的 Core 版本已经定义 operation、输入输出和错误语义。
2. production driver 实现完整路径，而不只是存在同名方法或实验 harness。
3. descriptor 中必要的 profile、限制、权限和配置字段准确表达边界。
4. 正常、拒绝、超时、解析失败、部分写入和恢复路径有与风险匹配的离线测试。
5. package README 或 `doc/README*` 指向一份项目原创的当前审计记录，其中分别记录 manual basis、离线实现、实机证据和 descriptor 准入；机器可读记录应由包级测试对照 descriptor。
6. 如果合同或声明内容要求型号级实机证据，证据已通过既有 harness 获取并限定到实际型号、固件、transport 与版本。

手册内容明确、Core 合同完整且离线故障测试通过时，可以声明 manual-backed、hardware-not-verified 的 capability。它不能声称物理效果、精度、性能、稳定性或具体固件行为已验证。Acceptance、milestone 和 archive 只记录证明与历史，不能自动提升 capability；Experimental 行为必须与 production descriptor 分离，并明确不可用于普通发现。

## New-package exit check

新包完成前确认：

- 源码安装和实际 wheel 均能发现预期 entry point。
- `<kind>.idn` 已通过 mandatory Identity 门禁，且证据状态准确。
- descriptor 加载不做仪器 I/O，身份与 metadata 一致。
- Core 版本门、Python 版本与 build metadata 一致。
- FakeTransport 覆盖协议正常路径和危险失败路径。
- wheel 与 sdist 只包含获准发布的代码、许可证、公开文档和显式证据。
- 隔离环境卸载后没有残留路由，Core 内建回退行为按当前合同恢复。
- `doc/vendor-local` 中的厂商原件和转换稿均未被跟踪，也未进入 wheel／sdist。
- 生成式插件目录无漂移；README 只摘要并链接权威来源。

到这里表示该包 `ready-to-merge`。本仓各包独立版本；只有 wheel 内容或安装合同变化的包才提升自身版本，不改动的包保持原版本。合并到 `main` 即视为发布，不要求 tag、GitHub Release 或 PyPI。
