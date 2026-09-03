---
name: wavebench-plugin-development
description: >-
  Develop, review, package, and validate production instrument plugins in the
  wavebench-instrument-plugins monorepo. Use when work primarily changes a
  plugin descriptor, driver, parser, profile, tests, entry point, build
  metadata, package build or isolated lifecycle validation, conformance
  manifest, hardware-evidence tooling, or repository-wide plugin development
  scripts. Do not use for runtime plugin installation or removal without
  repository changes, ordinary WaveBench operation, WaveBench Core
  implementation, documentation-led work, or unrelated VISA/SCPI projects.
license: MIT
metadata:
  author: "WaveBench maintainers"
  version: "1.0.0"
  project: "wavebench-instrument-plugins"
  specification: "https://agentskills.io/specification"
---

# WaveBench plugin development workflow

## Core objective

以可安装、可发现、可离线验证且不意外接触仪器的状态交付 WaveBench 生产插件。优先修改最小范围，并让包元数据、production descriptor、实现、测试与发行产物表达同一套事实。

本流程面向 Codex 或兼容 Agent Skills 的宿主，仓库要求 Python 3.11+。验证使用已同步的 WaveBench 开发环境；实时仪器工作还需要明确授权、已确认接线和 Core 安全流程。

## Invocation boundary

仅在插件仓的生产交付物是主要任务时使用本 Skill，例如修改 `packages/wavebench-*` 下的 driver、descriptor、parser、profile、测试或打包配置，或者修改仓库级开发、目录生成、conformance 与实机证据工具。

以下任务不属于本 Skill：

- 只安装、配置、查询或操作现有 WaveBench 插件：交给 WaveBench 操作流程；宿主提供 `$wavebench` 时使用它。
- 主要交付物是文档审计、信息架构或页面改写：交给文档工作流；宿主提供 `$wavebench-docs` 时使用它。
- 修改 WaveBench Core 的公共模型、CLI 或运行时：在 Core 仓按 Core 开发流程处理。
- 与本仓无关的 VISA、SCPI 或电子学任务。

如果插件开发包含实时仪器验收，本 Skill 负责仓库代码、包、harness 和证据格式；实时授权、接线、写入、恢复与最终设备状态同时服从 WaveBench Core 安全合同。宿主提供 `$wavebench` 时同时加载；未提供时停止在离线阶段。

## Start every task

1. 用 `git rev-parse --show-toplevel` 确认位于 `wavebench-instrument-plugins` 根目录，并执行 `git status --short --branch`。保留无关用户改动，禁止隐式清理、reset 或覆盖。
2. 将任务归为离线评审、离线代码修改、包与生命周期、只读实机证据或受控实机写入。默认只做离线工作。
3. 读取受影响包的 `pyproject.toml`、production descriptor、实现入口和聚焦测试；涉及 Core 类型或语义时，再读取匹配版本的 Core 模型与测试。
4. 若仓库有 `.codegraph/`，先用 CodeGraph 定位符号、调用方和测试，再完整读取即将修改的文件。
5. 安装依赖、同步 `.venv`、构建发行产物或连接仪器前，说明影响范围、预期结果和停止条件。

## Risk classes

| 类别 | 典型操作 | 默认处理 |
| --- | --- | --- |
| 离线评审 | 检查 descriptor、parser、测试、diff | 可直接进行，不加载插件、不连接仪器 |
| 离线代码 | driver、profile、FakeTransport、仓库脚本 | 先跑聚焦测试，再扩大验证范围 |
| 包与生命周期 | metadata、entry point、wheel、sdist、安装和卸载 | 使用隔离环境，检查发现、导入和卸载回退 |
| 实机证据 | conformance、只读查询、受控写入 | 需要单独授权；先过离线门禁和 Core 安全门禁 |

## Non-negotiable contracts

- 包内 `pyproject.toml` 与 production descriptor 是版本、entry point、兼容范围、型号和 capability 的权威来源。生成式目录只能读取并呈现这些事实。
- entry point、`driver_id`、distribution、version 与 `source` 必须一致；一个包可以有多个用途明确的 production entry point，不能假定所有包只有一个。
- descriptor 模块导入和 `descriptor()` 调用不得扫描资源、打开 transport、执行协议命令或读写文件。仪器 I/O 只能在 factory 通过 `DriverContext.open_transport()` 开始。
- 方法存在、README、milestone、测试草案或历史证据都不能单独提升 production capability。声明前必须核对 Core 合同、生产实现、profile、安全语义和与风险匹配的验证。
- 测试默认使用 FakeTransport 或等价离线替身。禁止用真实实验室地址、串口、序列号、凭据、原始波形、截图或命令日志填充跟踪文件或发行产物。
- 不盲目重试写入、触发、采集或结果不明的操作。未知写入结果必须 fail closed，并由 latch、停止策略或上层恢复合同处理，同时覆盖测试。
- 不假定所有包拥有相同的 conformance、恢复、wheel 内容或发布流程。先检查当前包已有合同和测试。
- 本仓当前没有统一的发布流水线。包元数据描述可构建合同；tag、release、上传、push 或发布都需要单独请求和授权。

## Load only the relevant reference

触发 Skill 后只读取与当前任务匹配的文件：

| 任务 | 追加读取 |
| --- | --- |
| 新包、descriptor、entry point、兼容范围、capability | [repository-contract.md](references/repository-contract.md) |
| driver、parser、profile、测试、修复、重构或代码评审 | [development-validation.md](references/development-validation.md) |
| editable 环境、metadata、wheel、sdist、安装或卸载 | [packaging-and-lifecycle.md](references/packaging-and-lifecycle.md) |
| conformance、实机 harness、证据升级、隐私或恢复 | [conformance-and-hardware-evidence.md](references/conformance-and-hardware-evidence.md) |
| Skill 本身的维护或触发回归 | [eval-prompts.md](references/eval-prompts.md) |

Reference 只从本入口直接链接，保持一层目录。不要为普通 driver 修改预加载打包或实机章节。

## Baseline validation

按改动风险逐层增加验证，不把全仓测试当作每次修改的起点：

```bash
python3 scripts/dev_env.py check
.venv/bin/python -m pytest -q packages/<package>/tests/<focused-test>.py
.venv/bin/python -m ruff check <changed-paths>
python scripts/generate_plugin_catalog.py --check
.venv/bin/python -m wavebench plugin package check packages/<package>
git diff --check
```

只运行与改动相关的命令。metadata、descriptor 或正式包集合变化后，开发环境和生成式目录可能需要更新；先按对应 reference 核对，不能把旧 `.venv` 的通过结果当作当前源码的证明。

## Handoff

交接先说明生产行为是否完成，再列出：改动包和 entry point、运行的离线测试与结果、生成或检查的发行产物、跳过或失败的门禁、Core 兼容假设，以及是否改动虚拟环境、本地配置或真实仪器。若接触过硬件，还必须记录最终设备状态、未恢复设置和证据位置。
