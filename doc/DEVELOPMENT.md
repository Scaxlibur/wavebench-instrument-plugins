# 插件开发环境

[English](DEVELOPMENT_EN.md)

本仓库使用一个独立的长期开发虚拟环境，将相邻的 WaveBench 核心源码和所有已经具有 `pyproject.toml` 的正式插件按标准 PEP 660 editable 方式安装。普通 Python 源码修改会直接生效，只需重启正在运行的 Python/CLI 进程，不需要再次安装。

## 首次同步

默认目录布局为相邻的 `wavebench/` 和 `wavebench-instrument-plugins/`：

```bash
cd wavebench-instrument-plugins
python3 scripts/dev_env.py sync
```

脚本会创建仓库内被忽略的 `.venv/`，汇总并安装各项目声明的 build-system 依赖，安装 `wavebench[dev]` 和所有正式插件的 editable metadata，并通过真实 `wavebench.instruments` entry point 与 registry 解析验证环境。`sync` 会调用 pip，首次运行可能访问配置的软件源并安装依赖；它不是离线发布门禁。

若核心仓库不在默认相邻位置，应显式指定：

```bash
python3 scripts/dev_env.py --wavebench-root <wavebench-source> sync
```

## 日常开发

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
python3 scripts/dev_env.py check
```

源码修改不需要重新运行 `sync`。只有下列内容变化时才需再次同步：

- `pyproject.toml` 中的版本、依赖或 entry point；
- 新增或移除带 `pyproject.toml` 的正式插件包；
- 切换到另一份 WaveBench 核心源码 checkout；
- 开发虚拟环境被删除或依赖需要更新。

`check` 不安装软件、不访问仪器，也不联网；它会比较已记录的项目元数据，确认核心和插件仍为 editable 安装，要求仪器 entry point 集合与当前正式插件集合精确一致，并通过 WaveBench registry 解析每个 canonical driver ID。再次运行 `sync` 时，脚本会依据这个专用环境自己的旧状态记录卸载已经从仓库移除的正式插件。只有文档、没有 `pyproject.toml` 的孵化目录会被明确跳过。

## 与正式验收的边界

editable 环境仅用于开发反馈，不代表可发布验收。提交或发布前仍需使用 WaveBench 的 `plugin package check`、真实 wheel、一次性虚拟环境和受管 install/remove 生命周期门禁。不要在同一虚拟环境中混用 editable 安装与 WaveBench 受管插件账本；脚本检测到账本或未完成事务时会拒绝操作。

插件 descriptor 导入仍不得打开 transport。默认测试不得扫描端口、连接仪器或发送 SCPI；实机测试必须另行获得明确授权并使用脱敏配置。
