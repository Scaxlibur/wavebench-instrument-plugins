# SDS800X HD 的 Scope R1.3 Conformance 证据

> 状态：核心 `0.8.23` 公共合同 conformance；SDS 正式 capability 尚未 opt-in
>
> 对齐核心：`master@6cd2eb5`，WaveBench `0.8.23`
>
> 对齐说明：[核心实施说明](https://github.com/Scaxlibur/wavebench/blob/master/docs/project/rfcs/WaveBench_scope通用扩展接口RFC_核心实施说明.md)

本文记录 SDS800X HD 插件针对 Scope R1.3 公共合同的测试专用 adapter、fake backend 和脱敏
实机观察。它不是正式 driver 迁移说明，不改变 descriptor、WaveBench 最低版本或现有执行路径。

## 证据分层

| 层级 | 内容 | 可证明范围 |
| --- | --- | --- |
| 插件单元测试 | 现有 `FakeTransport`、waveform parser 和正式 driver 测试 | SDS 命令顺序、六项 transfer 恢复、多分块拼接、SINGLE/Stop 和 sequence 拒绝 |
| R1.3 conformance | [`tests/conformance/`](../tests/conformance/) 中的测试专用 descriptor、adapter 和 stateful backend | 核心 typed baseline、phase、binary ledger、cleanup 和 completion proof 如何消费 SDS 映射 |
| 脱敏实机观察 | [SDS804X HD TCPIP 脱敏清单](../tests/conformance/fixtures/sds804x_hd_tcpip_redacted.json) | 已观察的长度、状态、固件和恢复摘要；不证明尚未接通的 backend 合同 |

R1.3 conformance 使用核心 `0.8.23` 的稳定 `ScopeExtensionService` 与公共 model。旧核心缺少
R1.3 model 时会跳过该目录，因此未声明新 capability 的正式插件仍保持原行为。

## 运行方式

在插件仓库根目录运行：

```bash
WAVEBENCH_CORE_ROOT=/path/to/wavebench
PYTHONPATH="${WAVEBENCH_CORE_ROOT}/src" \
  .venv/bin/python -m pytest \
  packages/wavebench-siglent-sds800x-hd/tests/conformance -q
```

核心 `master@6cd2eb5` 下，SDS800X HD 全部测试为 `138 passed`，其中本目录
`15 passed`。旧核心下只跳过 R1.3 conformance，不改变正式能力。

## Transfer restore

测试专用 trace profile 按核心当前 operation spec 覆盖以下八个规范化字段：

| R1.3 字段 | SDS fixture 映射 | 边界 |
| --- | --- | --- |
| `scope.run_state` | `:TRIGger:STATus?` | fake 中恢复为 STOP/RUN；现有实机 transfer 证据未把它纳入同一 typed baseline |
| `scope.waveform_source` | `:WAVeform:SOURce?` | 已有成功和本地异常注入的实机恢复证据 |
| `scope.waveform_mode` | `:ACQuire:SEQuence?` | 用于拒绝 sequence；现有实机 transfer 恢复证据未把它纳入六项写回 |
| `scope.query_response_header` | 固定 `RAW_MESSAGE` token | CN11G 未提供可变 CHDR 等价设置；fixture 不发送虚构命令 |
| `scope.waveform_format` | `:WAVeform:WIDTH?` | 已有实机恢复证据 |
| `scope.waveform_byte_order` | `:WAVeform:BYTeorder?` | 已有实机恢复证据 |
| `scope.waveform_points` | `:WAVeform:POINt?` | 已有实机恢复证据 |
| `scope.waveform_transfer_window` | `START + INTERVAL` | 已有实机恢复证据 |

Conformance 覆盖成功恢复、主操作失败后恢复、fresh readback 和部分恢复失败。恢复缺一项时，
主异常仍保持主异常，cleanup artifact 标为失败，session 进入 `poisoned`，不会伪装成成功。
artifact 只保存 16 字符 nonce 摘要，不保存原始 baseline nonce。

## Binary framing

Waveform fixture 使用 SDS 形状的两块 little-endian WORD payload，并通过核心
`parse_definite_block_response()` 生成 `BinaryQueryResult`。测试核对 declared length、header
长度、payload 长度、consumed 等式、截断拒绝，以及同一 operation ledger 的累计 query/byte
扣减。

核心已经完成 PyVISA 与 RsInstrument 的离线 `query_binary()` conformance。现有 SDS 实机读取
仍走旧 `query_bin_block()`，公开记录只保留两块各 `5000000` 点、`10000000 bytes` 的 payload
摘要，没有保留 framing header。因此脱敏清单仍将 SDS 实机
`backend_query_binary_conformant` 固定为 `false`。

## Screenshot

CN11G 的 `:PRINt?` 直接接收图片格式和 NORMAL/INVerted 参数；当前没有已确认的菜单或颜色
持久状态需要临时修改。SDS profile 因此声明 `changed_fields=()`，测试覆盖：

- `MESSAGE` framing 的 raw response；
- IEND 后精确一个 `00` content trailing；
- content trailing 仍计入 `BinaryQueryResult.data` 和 binary budget；
- driver 完整校验后只把规范 PNG 交给 `ScopeScreenshot`；
- trailing 不匹配时失败，并保持零 restore/verify I/O。

这证明 SDS 的 stateless screenshot 分支；该命令不修改已知持久状态，因此不需要虚构非空
baseline。核心 A1 已包含其他 fixture 的有状态恢复证据。真实 SDS 截图的 EOM 边界仍须通过
核心 `query_binary()` 在目标仪器上验收，才能声明本插件 capability。

## Acquisition proof

SDS fixture 使用 `configure_then_arm` 和 `identity_semantics="unknown"`。有效 SINGLE 证据为
`arming -> stopped` 的完整 `state_transition`。`NUMACq` 只记录为诊断值，不参与 proof。

负向测试会拒绝以下结果，并验证 STOP、trigger setting、acquisition setting 的失败 cleanup
及 fresh readback：

- 只返回最终 Stop、没有新 acquisition transition；
- count 增加但缺少 `counter_epoch`；
- identity 变化但 profile 未证明 epoch 内唯一性。

现有实机记录已经观察到 SINGLE query-back、Arm 到 Stop 和正数 count，但 count 仍不能单独
证明完成。

## SDS 正式采用前仍需完成

- 目标 TCPIP/VXI-11 resource 的 MESSAGE EOM、长 payload 和下一次查询实机验证；
- SDS 八项 typed transfer baseline 的完整实机 fresh readback；
- acquisition 失败 cleanup、STOP、trigger/acquisition 设置恢复和 fresh readback 实机验证；
- 正式 driver 方法、descriptor profile、capability 和 `wavebench>=0.8.23,<0.9` 版本门；
- 新能力启用后的 package check、CLI artifact 和旧 capability 回归。

核心 R1.3 把 `SCOPE_TRACE_MAX_POINTS` 固定为 `8388608`。SDS804X HD 已验收的 `10M` 记录
超出该模型上限，只能继续由现有 `scope.fetch_waveform` 路径读取；在读取策略另行裁决前，
不得把这条实机记录宣称为 `scope.fetch_trace` 的完整迁移证据。

## 脱敏规则

仓库只保留固件、仪器族、resource class、framing/长度、规范化状态和恢复结果。真实地址、
序列号、原始图片、原始波形、完整命令日志和本地临时证据路径均不进入 Git。
