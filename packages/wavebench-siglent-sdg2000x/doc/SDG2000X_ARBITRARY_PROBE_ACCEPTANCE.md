# SDG2000X 任意波只读探测验收

[English](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，`wavebench-siglent-sdg2000x` 0.8.0 的 `source.arbitrary_probe` 在一台 `SDG2122X` 固件 `2.01.01.39R7T2` 上完成双通道 A1 实机验收。CH1 与 CH2 的当前任意波选择、采样率模式和内置波形目录查询均由核心 `SourceService` 返回 `ArbitraryQueryProbeResult`，3 项全部 `accepted=True`。

正式轮次只有 6 次查询、0 次写入。两路输出在测试前后均为 OFF。该能力不上传、不删除、不覆盖波形，也不查询用户目录。

## 核心接口映射

插件精确实现主仓库协议：

```python
def probe_arbitrary_queries(
    self,
    channel: int,
) -> list[ArbitraryQueryProbeResult]: ...
```

固定白名单包含：

| 标签 | 查询 | 用途 |
| --- | --- | --- |
| `current_selection` | `C<n>:ARWV?` | 当前任意波索引与名称 |
| `sample_rate_mode` | `C<n>:SRATE?` | DDS/TARB 模式与可用采样率字段 |
| `builtin_catalog` | `STL? BUILDIN` | 内置波形目录 |

候选查询不可由调用方替换，因此不会演变成 raw SCPI 入口。SDG2000X 没有已确认可用的错误队列，结果中的 `errors` 明确为空；单项查询异常写入该项 `exception`，后续项继续执行。

## 实机结果

| 通道 | 当前选择响应 | 采样率响应 | 内置目录 |
| --- | --- | --- | --- |
| CH1 | 包含 INDEX 与 NAME，28 字符 | DDS，17 字符 | 199 项，2692 字符 |
| CH2 | 包含 INDEX 与 NAME，28 字符 | DDS，17 字符 | 199 项，2692 字符 |

内置目录实测索引范围为 0–198，共 199 项。E05C 的型号表写明 SDG2000X 内置索引为 2–198；实机仍返回索引 0 与 1。插件保留原始探测响应，不在公共结果中删改目录，也不把该差异外推到其它型号。

## Transport 审计

以 `read_only` 访问模式执行：

- 查询：6 次；
- 写请求：0 次；
- 已发送写入：0 次；
- 已完成写入：0 次；
- 写结果未知：0 次；
- 仪器状态变更写入：0 次。

验收结束后，公共 `source.status` 再次确认 CH1/CH2 均为 OFF。

## 离线验证

0.8.0 包级测试为 `323 passed`，覆盖：

- 核心结果类型与 descriptor capability；
- 两通道固定查询顺序；
- 单项异常记录后继续查询；
- 无错误队列时的空 `errors`；
- 无效通道在 I/O 前拒绝，包括 `True` 与 `1.0`；
- wheel 安装后的版本、entry point 与 capability。

## 覆盖边界

- 不查询 `STL? USER`，避免把用户波形名称作为默认探测结果输出。
- 不发送 `ARWV`、`SRATE`、`WVDT` 或文件系统写命令。
- 目录存在只证明设备声明了内置波形，不证明每个波形都已完成输出 A4。
- 实机证据只适用于当前 SDG2122X 固件；SDG2042X/SDG2082X 仅按同一手册查询合同放行。

