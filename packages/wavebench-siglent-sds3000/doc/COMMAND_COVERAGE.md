# SDS3000 手册指令覆盖基线

[English](COMMAND_COVERAGE_EN.md)

## 结论

2026 年 2 月版手册中共有 578 个明确实体，其中 478 个可调用实体和 100 个 Automation 对象。所有实体都已获得唯一稳定 ID、来源页、调用方向、安全等级、WaveBench 映射和处置状态；当前未分类数量为 0。

完整机器可读目录见 [`command-catalog.json`](command-catalog.json)，确定性提取器见 [`../tools/manual_catalog.py`](../tools/manual_catalog.py)。目录只保留标识符和审计元数据，不复制厂商说明、示例或响应正文。

## 分母

| 类型 | 数量 | 是否可调用 |
| --- | ---: | --- |
| Part 7 legacy/IEEE 488.2 命令 | 164 | 是 |
| Part 4 Automation 对象 | 100 | 否 |
| Part 4 Automation Action | 216 | 是 |
| Part 4 Automation CVAR | 14 | 是 |
| Part 4 Automation Method | 4 | 是 |
| Part 5 Result Interface 属性 | 80 | 是 |
| 合计 | 578 | 478 个可调用实体 |

Automation 对象虽然不能直接调用，但它们决定名称空间、型号和选件适用性，因此保留在审计目录中。手册明确说明但没有逐项列出的其他 CVAR 不计入分母。

## 当前处置

M1 完成时的状态如下。后续里程碑会在保留稳定 ID 的前提下更新处置状态。

| 状态 | 数量 | 含义 |
| --- | ---: | --- |
| `planned` | 20 | WaveBench 现有接口可表达，已进入实现计划 |
| `core-gap-rfc` | 10 | 需要通用核心接口提案 |
| `firmware-unverified` | 336 | 手册晚于固件 `8.4.1`，尚未取得充分证据 |
| `option-absent` | 78 | 依赖未确认或不适用的选件 |
| `model-not-applicable` | 2 | 手册明确排除 WaveSurfer 或限定其他型号 |
| `unsafe-quarantined` | 132 | 可能改变持久状态、文件、网络、校准、供电或执行任意脚本 |
| `implemented` | 0 | M1 只冻结分母，不提前声称实现完成 |

「100% 覆盖」表示每个明确实体最终都必须有可复核的实现或处置证据，不表示强行执行所有指令。选件指令、型号不适用指令和危险指令也属于覆盖范围，但不会为了提高数字而在实机上执行。

## 手册异常

Part 7 的 164 行索引全部进入目录。`DD_PES_SETUP`（`DPSU`）在短命令索引和子系统表中出现，但正文没有对应命令标题；目录将其标为 `body-heading-not-present`，并依据索引明确给出的语义记录为 command/query 双向。

另有少量索引与正文标题在问号、星号或短命令拼写上不一致，例如 `3DB` 与正文中的 `D3D`。这些记录标为 `index-body-token-mismatch`，不会静默改写厂商标识符。提取器仍要求 164 个稳定 ID 唯一，防止转换错误导致漏项或合并。

## 安全边界

以下类别默认隔离，不进入自动实机测试：

- 恢复出厂、面板保存或召回、校准、自检；
- 文件、目录、邮件、打印和外部设备操作；
- 日期、网络、远程设置、选件激活和关机；
- 任意 `VBS`、Automation 反射或用户提供的脚本；
- 无法保证恢复状态的写入或读后清除寄存器。

插件可以在类型化 capability 内使用固定、受控的厂商命令序列，但不得公开任意 SCPI 或 VBS 执行入口。

## 复现与门禁

本地三段手册转换结果存在时，可在包目录运行：

```bash
python tools/manual_catalog.py --check
pytest tests/test_manual_catalog.py
```

提取器会先复核三段 PDF 的 SHA-256 和字节数，再解析转换后的 `content_list.json`。测试固定以下约束：

- 578 个实体、478 个可调用实体；
- Part 7 恰好 164 行；
- 每类计数保持一致；
- 稳定 ID 无重复；
- 可调用实体均有方向；
- 所有实体处置状态合法；
- 目录不包含厂商说明和示例正文；
- 本地手册可逐字节重建已提交目录。

CI 没有厂商资料时仍会校验已提交目录的结构和完整性；只有本地重建测试会跳过。
