# Packaging and lifecycle

在修改包 metadata、entry point、构建包含范围、editable 环境、wheel、sdist、安装、升级或卸载行为时读取本页。

## Development environment

先检查现有标准环境：

```bash
python3 scripts/dev_env.py check
```

`check` 验证 Core 与所有正式插件的 metadata 快照、editable 安装和 entry point，不访问软件源，也不连接仪器。失败信息如果说明包集合或 metadata 漂移，再考虑：

```bash
python3 scripts/dev_env.py sync
```

`sync` 会创建或修改 `.venv`，以 editable 方式安装相邻 Core 与所有正式包，且 pip 可能访问已配置的软件源。运行前必须说明这些影响。已有但未标记的环境只能在审阅后显式接管；不要绕过脚本对 WaveBench 受管插件账本或未完成事务的拒绝。

开发环境只提供快速反馈，不是发行验收环境，也不能与受管 install/remove 流程混用。

## Metadata changes

本仓各 distribution 独立版本，不使用整仓锁步版本。准备合并 `main` 时，先判断本次是否改变某个包的 wheel 内容或安装合同：

- 需要提升该包版本：生产源码、descriptor、entry point、依赖、进入 METADATA 的包 README、运行时资源或 wheel-bound evidence 发生变化。
- 不需要提升插件版本：只改测试、根文档、CI、仓库工具，或只改被 wheel／sdist 排除的本地厂商资料。
- 只提升实际变化的包；修改 DP800 不得顺带提升未改动的 RTM2000 或其他插件。

功能分支可以包含多个开发提交，只在准备合并时为每个受影响包提升一次。修改 `pyproject.toml`、entry point、Core dependency 或 descriptor 身份后：

1. 核对 distribution、version、Core 版本门、entry point 与 descriptor 字段。
2. 重新同步标准开发环境，避免旧 editable 状态伪造通过结果。
3. 更新生成式目录并检查工作树只包含预期变化：

```bash
python scripts/generate_plugin_catalog.py
python scripts/generate_plugin_catalog.py --check
```

4. 对源码包运行 WaveBench package check：

```bash
.venv/bin/python -m wavebench plugin package check packages/<package>
```

生成式目录是衍生物，不要手工修正版本、兼容范围或 capability 表格来掩盖源码不一致。

## Build artifacts

使用包已声明且受信任的 build backend 构建实际 wheel 和 sdist。优先运行包内现有构建测试，因为部分包对命令、临时环境、包含文件和 digest 有额外合同。

至少检查：

- wheel 的 distribution、version、`Requires-Python`、`Requires-Dist`、许可证和 entry point。
- wheel 只包含生产模块与明确获准的运行时资源。
- sdist 包含构建所需源码和公开材料，但排除 `vendor-local`、真实配置、采集数据和临时产物。
- 从构建产物加载 descriptor 不触发仪器 I/O。
- 源码检查与 wheel 检查得出相同 production 身份和 capability。

不要假定每个包都携带 conformance manifest，也不要把某个包的 wheel 内容清单复制为全仓模板。

## Isolated lifecycle gate

任何新增正式包或会改变正式 wheel 的改动，在合并前都必须使用一次性虚拟环境和真实 wheel，验证：

1. 安装前的 Core 路由基线。
2. wheel 安装成功且仅出现预期 entry point。
3. `plugin list/info/doctor` 等加载路径在禁止仪器 I/O 的探针下工作。
4. canonical 与 opt-in entry point 按当前包合同解析。
5. 升级或降级时受管状态、来源和版本正确。
6. 卸载后 entry point 消失，Core 内建或前一版本回退符合当前合同。
7. 临时环境、wheelhouse 和受管状态不会污染标准 editable `.venv`。

优先运行包内现有 `test_wheel.py`、`test_lifecycle.py` 或等价测试。没有通用 lifecycle 测试时，先补与包风险相称的最小测试，不建立未经需求证明的统一框架。

## Package-bound evidence

少数包会把 conformance manifest 绑定到 wheel 非 manifest 成员，或把 README 内容带入 METADATA。修改这些包的源码、README、构建包含范围或 manifest 时：

- 先读该包的 build 配置、digest 计算工具和对应测试。
- 用既有工具重建 binding，不手算或手改 hash。
- 验证 descriptor digest、wheel binding、manifest 自身 digest 与最终 wheel。
- 确认历史证据没有因此被误标为当前 production capability。

这不是所有包的固定步骤；由当前包测试与 build 配置决定。

## Main release boundary

本仓不以 Git tag、GitHub Release 或 PyPI 表示发布状态。插件变更合并到 `main` 即视为发布；因此分支或 PR 是 release candidate，合并前必须完成版本判断、真实发行物和隔离生命周期门禁。

验证通过不会自动授权 push 或合并。用户没有明确要求时，只报告 `ready-to-merge`；只有变更实际进入 `main` 后才能报告 `released`。tag、Release 和外部 registry 可以另行使用，但不是本仓发布事实源，也不要求补建。

交接时按包列出旧版本、新版本、是否改变 wheel、源码合同、wheel／sdist 和隔离生命周期结果，并区分 `ready-to-merge` 与 `released`。
