# Instrument driver workflow

在从厂商手册准备新驱动、新型号、新协议或新 capability，以及判断 WaveBench Core 缺少接口或仪器类型时读取本页。普通实现 bug 只复核受影响协议，不重新审计整本手册。

## Delivery model

驱动以 capability 纵向切片交付，不以「尽量写完手册命令」为目标：

```text
本地厂商资料
→ 项目原创协议审计
→ Core fit 判断
→ Identity-first
→ capability 实现与离线故障测试
→ 按需的实机证据
→ wheel 安装、发现与卸载
→ 受影响包独立提升版本
→ 合并 main 即发布
```

新包可以先只有 `doc/`，不创建 `pyproject.toml`。这类目录处于孵化状态，不会被仓库开发环境当作正式 distribution。手册范围与 Identity 合同完成后再建立正式包。

## Stage 0 — Local vendor material

每个新驱动先建立 `packages/<package>/doc/vendor-local/README.md`，登记建议文件名、来源、语言、版本与适用型号。该 README 可以提交；其余厂商原件和转换产物不得跟踪。

本地输入可以包括 PDF、CHM、展开的 HTML，以及 MinerU 产生的 `full.md`、图片、layout／block／content-list JSON 和原始 PDF 副本。转换结果只用于搜索和提取，不自动成为可靠事实；SCPI token、问号、负号、单位、表格、上下标与分页接缝必须回到原件核对。

开始公开整理前确认：

1. 登记手册标题、文档号、修订号、发布日期、语言、适用系列／型号和官方来源。
2. 记录原件 SHA-256；转换被分段时记录顺序、页数和连续性。
3. 使用 `git check-ignore` 验证每个非 README 输入确实被忽略，并确认没有厂商文件已经被 Git 跟踪。禁止 `git add -f`。
4. 若该目录已经有 `pyproject.toml`，确认 sdist 配置排除 `/doc/vendor-local`；只有 `doc/` 的孵化目录将实际构建检查推迟到正式包合并门。
5. 不在该目录混入真实资源地址、序列号、凭据、波形、截图、命令日志或恢复 journal。

CI 没有本地厂商资料时，只验证已提交审计的结构与一致性；本地有资料时，才执行 hash、目录重建或提取器复现检查。

## Stage 1 — Project-authored audit

编码新协议前，将本次开发范围整理成项目原创文档。简单插件可以把手册基线、协议审计和 capability 处置合在一页；只有手册庞大、方向复杂或需要完整性分母时，才拆分机器可读 command catalog、coverage matrix 或 certification plan。

每个目标命令或协议族至少记录：

- 稳定标识、原件位置和 command／query 方向。
- 参数、响应、单位、终止／framing 和大小上限。
- 型号、固件、选件、backend 与 transport 条件。
- 会读取、清除、改变或耦合的设备状态。
- 安全等级、恢复边界和不可重试条件。
- 对应的 Core kind、capability、typed model 与处置。
- 手册歧义、冲突、OCR／转换疑点和明确非目标。

退出门是「本次开发范围没有未分类事实」，不是强迫整本手册达到 100% 实现。覆盖可以用以下处置：planned、Core gap、firmware-unverified、option-absent、model-not-applicable、unsafe-quarantined 或明确 unsupported；不得用 raw SCPI passthrough 虚构覆盖率。

## Stage 2 — Core fit decision

按以下顺序判断：

```text
目标操作
├─ 现有 kind、capability 和消费路径能完整表达
│  └─ 只改插件
├─ 现有 kind，但缺少公共接口
│  ├─ 只有单一厂商意义
│  │  └─ 保留私有 typed 方法／实验 harness，不声明未知 capability
│  └─ 可跨仪器复用
│     └─ 插件仓 Draft RFC → 证据 → Core Accepted → 插件声明
└─ WaveBench 没有这种 instrument kind
   └─ 先在 Core 建立最小 Identity 接入，再开发正式插件
```

「消费路径」不仅指 capability 名称，还包括当前用户任务实际需要的 Service、OperationSpec、配置、安全和恢复表达。CLI、run plan 与 artifact 只有真实用户任务需要时才增加。

本 Skill 在插件仓负责手册审计、Core fit、Draft RFC、插件证据和回归准备。判断需要修改 Core kind、capability、typed model、config、doctor、Service 或其他运行时后，停止插件实现并移交 Core 开发流程；Core 合同进入可用版本后，再回到本仓完成插件声明和包验证。

### Existing kind, missing interface

插件仓 `doc/rfcs/` 先保存 `Draft`，不得据此声明 Core capability。达到两个独立仪器族或两种 backend 行为的证据后可进入 `Proposed`。Core 接受后：

1. 移交 Core 开发流程，在 Core 冻结 capability 名、driver method、typed request/result 和错误语义。
2. 需要静态型号约束时增加 append-only profile 与 validator。
3. 注册 capability-method 映射；需要公共操作时增加 OperationSpec 与 Service。
4. 仅在实际用户流程需要时增加 CLI、run-plan step、artifact、bench 级 config 或恢复策略。
5. Core 合同进入 Core 的可用版本后，插件再提高 Core 下限并声明 capability。

已经 Accepted 的公共合同只在 Core 维护；插件仓保留评审历史和型号证据，不维护平行当前副本。

### Entirely new instrument kind

新 kind 允许由一个明确、可 manual-backed 的目标仪器 bootstrap，避免因缺少第二个正式插件形成循环。插件仓先形成手册审计和 Identity bootstrap 需求，然后停止并移交 Core 开发流程。最小 Core Identity 接入至少包括：

- `PluginKind`／有效 kind 集合。
- `<new-kind>.idn` 与 `idn()` 方法映射。
- 可配置的 driver／resource section 与验证。
- doctor 的 Identity 路径。
- 通用 registry、factory、descriptor、配置和 doctor 测试。

外置插件仍使用通用 `wavebench.instruments` entry point 和 `DriverContext.open_transport()`；不要为新 kind 复制 registry 或 transport 工厂。

Identity bootstrap 不自动授权完整 Service、CLI、run plan、artifact 或安全恢复模型。第一个真实用户操作出现后再增加最小消费路径；更丰富的通用 capability 继续使用两个仪器族或两种 backend 的 `Proposed` 门槛。

## Stage 3 — Mandatory Identity

任何其他 production capability 之前必须完成：

1. `<kind>.idn` 已在 Core 注册，production descriptor 已声明。
2. driver 使用手册规定的标准 Identity query，并有明确、有界的响应解析。
3. 厂商、系列与型号匹配 fail closed；不得从系列字符串猜测未返回的子型号。
4. descriptor 导入与调用零 I/O；factory 只打开一个 Core transport。
5. FakeTransport 覆盖正常、畸形、timeout、错误型号与 `close()`。
6. 实际 wheel 可以安装、发现、解析并卸载，加载 descriptor 时禁止 transport open。

手册足以描述 query、响应和目标范围时，Identity 可以标为 `manual-backed` 并进入 production；没有实机记录时必须同时标为 `hardware-not-verified`。后续实机 IDN 只提升证据状态，不改变 Identity-first 是否已经通过。

## Stage 4 — Capability slice

每次只实现一个用户可感知操作或不可拆分的小事务：

```text
更新协议审计
→ 核对 Core 合同
→ 先写失败用例
→ parser／driver
→ FakeTransport 正常与故障路径
→ 必要的 profile
→ production descriptor 最后声明
```

至少分别记录四个维度，不把它们压成一个含混的「支持」状态：

| 维度 | 候选值 |
| --- | --- |
| Manual basis | exact／ambiguous／unavailable |
| Implementation | offline-verified／not-implemented |
| Hardware evidence | not-run／verified／failed／limited |
| Public admission | descriptor-declared／not-declared |

每个包必须从 package README 或 `doc/README*` 指向一份项目原创的当前审计记录，作为新增或修改 capability 的四维状态承载。文件名和格式不统一强制：小包可以使用 Markdown 表格，复杂包可以使用机器可读目录及其说明页。存在机器可读记录时，添加包级测试，验证 `public admission = descriptor-declared` 的集合与 production descriptor 一致；不要为解析任意 Markdown 另造通用框架。

允许 `manual basis = exact`、`implementation = offline-verified`、`hardware evidence = not-run`、`public admission = descriptor-declared`。此时公开页面必须写明 manual-backed／hardware-not-verified，不能声称物理效果、精度、性能、稳定性或具体固件行为已经实测。

手册不能关闭响应结构、framing、单位、Core 必填字段、型号／选件适用性、副作用或恢复语义时，不得用默认值和猜测凑齐合同。保留为未声明、Experimental 或 Core gap。

是否需要实机证据由该 capability 的 Core 合同、风险与声明内容决定，没有全仓统一的「上机后才能实现」规则。需要实时测试时，先完成全部离线门禁，再取得单独授权并服从 Core 安全流程。

## Stage 5 — Merge gate and release

正式包在合并前必须证明：

- 包级测试、Ruff、metadata／descriptor／catalog 一致性通过。
- `plugin package check` 和真实 wheel／sdist 构建通过。
- wheel 在一次性环境中安装、发现和加载，descriptor 加载零仪器 I/O。
- 卸载后 entry point 消失，或按既有合同恢复 Core 路由。
- sdist 不含 `doc/vendor-local`、厂商资料、真实配置和实验室数据。
- 包有 conformance binding 时，使用既有工具更新并验证 digest。

本仓采用独立包版本。只有本次会改变 wheel 内容或安装合同的包才提升版本：源码、descriptor、entry point、依赖、进入 METADATA 的 README、运行时资源或 wheel-bound evidence 均属于这一类。仅测试、根文档、CI、仓库工具或被排除的本地资料发生变化时，不联动提升任何插件；一个包变化也不提升未改动的其他包。

合并到 `main` 即为本仓发布事件，不要求 tag、GitHub Release 或 PyPI。分支可以包含多个开发提交，只在准备合并时为每个受影响包提升一次版本。没有合并权限时只报告 `ready-to-merge`，不得声称 `released` 或自行 push／merge。

## Completion record

交接记录：手册基线与审计位置、Core fit 结论、Identity 依据、每项 capability 的四维状态、受影响包版本、离线和实机门禁、wheel／sdist 与生命周期结果，以及当前是 incubating、ready-to-merge 还是 released。
