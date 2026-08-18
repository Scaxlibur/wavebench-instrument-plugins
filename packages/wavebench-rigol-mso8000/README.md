# WaveBench RIGOL MSO8000 插件（开发中）

该目录为 RIGOL MSO8000 系列的 WaveBench 插件开发起点，当前以 MSO8104 为首个目标型号。MSO8104 是 1 GHz、4 个模拟通道的混合信号示波器；系列编程手册还覆盖 MSO8064 和 MSO8204。

## 当前状态

M0 合同与发行边界已经形成，M1 身份插件尚未激活。当前目录暂不提供可安装 distribution，也不声明已经实现的 capability。目录暂时不放 `pyproject.toml`，仓库级 `scripts/dev_env.py` 会跳过它，避免未完成的 descriptor 被发现或安装。

本轮开发只使用手册审计、FakeTransport、故障注入、构建和安装生命周期验证，不连接真实仪器。所有型号、固件、transport、吞吐、恢复和测量结论均保持「未实机验证」。

计划中的身份信息如下，待手册整理和最小 FakeTransport 测试完成后再冻结：

- distribution：`wavebench-rigol-mso8000`
- canonical driver ID：`rigol.mso8104`
- kind：`scope`
- 目标型号：`MSO8104`
- Python：`>=3.11`
- WaveBench：`>=0.8.22,<0.9`

## 目录说明

- `doc/vendor-local/`：本地厂商手册。原始 PDF 和转换后的 Markdown 都放在这里；除说明文件外的内容会被 Git 忽略，也不会进入发行包。
- `src/wavebench_rigol_mso8000/`：descriptor 和 driver 的开发占位文件。
- `tests/`：后续放 FakeTransport 单元测试；默认测试不得连接真实仪器。
- `pyproject.toml.example`：插件正式激活时使用的元数据和 entry point 模板。完成 descriptor、driver 和测试后，再复制为 `pyproject.toml`，并同步仓库级包清单与门禁测试。
- `doc/`：公开覆盖矩阵和验收记录；厂商原文不要放到公开文档目录。

## 设计文档

- [MSO8104 功能覆盖里程碑](doc/MSO8104_COVERAGE_MILESTONES.md)
- [MSO8104 编程手册功能覆盖矩阵](doc/MSO8104_COVERAGE_MATRIX.md)

## 推荐开发顺序

1. 从手册整理 `*IDN?`、错误队列、波形前导码与数据读取、数字通道和 transport 约定；手册命令目录不直接等同于已实现 capability。
2. 先实现 `scope.idn` 和 `close()`，用 FakeTransport 固定命令、响应解析与错误映射。
3. 输入阻抗安全适配、消费型错误查询和深存储上限按里程碑分别处理。
4. 每增加一项 capability，补齐离线测试、写入副作用和恢复边界，再决定是否进入 descriptor。
5. 完成最小可安装包后，复制 `pyproject.toml.example`，再运行 editable 同步、Ruff、包检查和 wheel 生命周期门禁。

## 安全边界

descriptor 导入不得打开 transport、扫描端口、发送 SCPI 或创建文件。真实资源、序列号、凭据、波形、截图和命令日志不得提交。仪器写入和 acquisition trigger 不做盲目重试。核心缺少必要安全接口时，先写 RFC 并跳过对应 capability，不在插件中增加 raw SCPI 入口。

## 开发手册位置

本地厂商资料的具体放置规则见 [`doc/vendor-local/README.md`](doc/vendor-local/README.md)。
