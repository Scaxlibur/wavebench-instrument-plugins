# RFC-0008：有界示波器波形块的尾随字节合同

状态：核心开发工作树已实现；插件完成受限 `DEF`、停止态 MAX/DMAX 与 bounded `DEF + BYTE` capture 实机验收

目标仓库：WaveBench core

2026-08-24 更新：core 当前工作树已实现标准 waveform 的
`ScopeWaveformBinaryProfile`、bounded driver Protocol、factory barrier 和 core-owned
restore/verify。实现使用 `query_binary()` 与 descriptor-owned profile，不采用本文早期的
`query_bin_block()` 新关键字草案。core 尚未形成独立发布版本；MSO8104 的受控 waveform/capture 验收已完成。

## 问题

现有基础示波器 waveform capability 让 driver 通过
`InstrumentTransport.query_bin_block(command)` 读取 IEEE definite-length block。该接口没有表达设备在 payload 后是否发送 transport trailing bytes，也不能为单次读取声明响应大小上限。

MSO8104 实机验收在 WaveBench `0.8.24`、LAN/PyVISA、固件 `00.02.02` 上读取
`:WAVeform:DATA?` 时已经得到有效十字段 preamble，声明 `1000` 个 BYTE 点。随后 legacy
`query_bin_block()` 在约 `5 s` 后发生 `VI_ERROR_TMO`。该路径会等待 PyVISA 的默认终止符；当前读取无法证明响应同步，core 因而把 session 标记为 `poisoned`，并按设计拒绝 driver 的 waveform-state restore 写入。

这不是把 timeout 增大即可安全解决的问题：若设备不发送 trailing termination，继续等待只会延长不确定窗口；若全局关闭 trailing 等待，又可能把带尾随字节的其他仪器响应留在 transport 中。

## 已知实机证据

- scope：RIGOL MSO8104，固件 `00.02.02`；
- transport：LAN/PyVISA，读取重试为 `0`；
- 输入：CH1 `DCL`、CH2 `ACL`，均为 core 高阻安全 token；
- source：Siglent SDG2122X，CH1/CH2 均已确认 OFF；
- `:WAVeform:PREamble?` 返回 `0,0,1000,1,5.000000E-5,-2.500000E-2,0.000000,8.7440E-04,-2,128`；
- `:WAVeform:DATA?` 的 legacy binary read 在约 `5.01 s` 超时；guard 的 session transition 为 `healthy → poisoned`，reason 为 `transport_synchronization_unproven`；
- 两路 source 随后以独立 Source V2 snapshot 确认 OFF、snapshot `consistent`、session `healthy`。

不提交真实资源地址、序列号、原始波形、完整命令日志或完整异常对象。

## 建议合同

以下 legacy `query_bin_block()` 关键字是历史候选方案，保留用于说明被拒绝的边界；当前 core
实现采用 descriptor profile 和受预算的 `query_binary()`：

```python
class InstrumentTransport(Protocol):
    def query_bin_block(
        self,
        command: str,
        *,
        expect_termination: bool = True,
        max_bytes: int | None = None,
    ) -> bytes: ...
```

最低要求：

- 默认 `expect_termination=True` 保持既有 driver 兼容；
- 仅有已验证设备可显式请求 `expect_termination=False`；
- `max_bytes` 在发送或分配大 payload 前强制执行；
- trailing 不是空时必须明确声明并精确消费，不能静默遗留字节；
- 任一 framing、长度或同步不确定都保留 `poisoned` 语义，不重放 binary query；
- 审计记录实际策略、声明长度、消费字节和同步结果。

core 当前工作树已让标准 waveform Service 在 binary budget 的操作上下文中使用
`query_binary(... framing=definite_block, max_bytes=...)`；trailing 由 descriptor profile 注入，driver
不能自行放宽。MSO8104 的受控实机读取确认 payload 后为一个 `LF` byte，而空 trailing profile 会安全失败。

## capability 影响

`0.9.0` 开发版本声明 `scope.fetch_waveform` 的受限 `DEF`、停止态 MAX 和停止态 DMAX：`LF` trailing、每响应 `250,000` bytes、每操作 `4,000,000` bytes、最多 16 次 binary query，以及 source/mode/format/points/window 五字段恢复。MAX/DMAX 在 transfer setup 前要求 STOP，读取 memory depth 后再把 points 限制为 memory depth、运行时总点数和 16 倍 chunk 的最小值。该声明只用于当前 core 工作树的离线和受控验收，不构成发布版兼容性结论。

插件同时声明 `scope.capture_waveform` 与 `scope.capture_waveforms`。capture 仅接受已停止、MAIN 时基的 `DEF + BYTE` baseline：单通道最多一次、双通道最多四次 binary query，并由 Core 恢复和新鲜验证 acquisition、trigger、时基、四路 display/vertical 与 transfer 的 13 个字段。首条 STOP 不构成 capture 新鲜性证据。

已完成的受控验证：

1. `DEF` + `LF` trailing block 成功读取，session 保持 healthy；
2. 1000-sample payload 与五字段 transfer state 恢复已由 core fresh readback 证明；
3. 在人工确认 acquisition、探头倍率、通道显示和接线后，完成 `1 kHz / 1 Vpp` 的 X/Y 换算和测量闭环；
4. 每轮开始和结束都独立确认 source 两路 OFF；
5. CH1/CH2 的停止态 MAX/DMAX 已在 source 双路 OFF、scope 高阻、scope stopped、当前 `10 kpts` memory depth 与 `20 kpts / 2.5 kpts chunk` 条件下各自返回 `10,000` 样本，并完成五字段 restore/fresh verify；
6. bounded 单通道与双通道 `DEF + BYTE` capture 已在低压步骤下返回每通道 `1,000` 样本，并完成 `WAIT → STOP`、恢复 `*OPC? 0 → 1` 与 13 字段 fresh verification；`TD → STOP` 已由独立 SINGLE control 验收确认。最终 source 两路 OFF、scope STOP、CH1/CH2 high_z。

## 不采用的方案

- 在插件中直接访问 PyVISA session 或自行解析 block：绕过 core lease、access guard、审计和 session health；
- 将 PyVISA 的全局 legacy binary 默认改为不等待 termination：会改变其他 RIGOL/R&S driver 的行为并可能遗留尾字节；
- 增大 timeout 或在失败后重试：不能证明同步，也可能读取下一条响应；
- 忽略 poisoned session 并继续 restore：违反 core 的 fail-closed session 合同。
