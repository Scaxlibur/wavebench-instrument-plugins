# SDS3054 实机验收

[English](HARDWARE_ACCEPTANCE_EN.md)

## 结论

SDS3054 固件 `8.4.1` 已通过 VICP 文本、二进制波形、单次 acquisition 和双通道同次采集的受控验收。DG4202 CH1 同时接入 SDS3054 CH1/CH2；正式采集信号为 1 kHz、1 Vpp、0 V 偏置正弦波，两路示波器输入均为 1 MΩ 高阻。

机器可读脱敏证据见 [`hardware-acceptance.json`](hardware-acceptance.json)。该文件只包含汇总指标，不含资源地址、序列号、原始波形、截图、命令日志或恢复 journal。

## 安全门禁

首次预检发现示波器 CH1 处于 50 Ω，而发生器输出恰好处于 5 Vpp 上限并已开启。验收立即通过 WaveBench 关闭发生器输出，没有继续读取波形或尝试远程改变示波器阻抗。CH1 经前面板人工改为 1 MΩ 后，发生器保持 OFF，CH1/CH2 连续三轮均返回 `DCL`，才进入后续测试。

发生器完整 profile 显示负载为高阻。正式输出前依次执行：

1. 确认输出 OFF；
2. 将函数、频率和幅度设置为 `SIN / 1 kHz / 1 Vpp`，偏置保持 0 V；
3. 再次确认 CH1/CH2 高阻；
4. 开启输出并开始采集；
5. 任意异常均先关闭输出，再恢复原 profile。

## M4：波形传输

发生器保持 OFF 时，CH1 与 CH2 均成功读取 100,002 点。每次事务先快照 `CHDR/CFMT/CORD/WFSU`，临时进入 `DEF9,WORD,BIN`、低字节优先和单分段传输，完成后恢复。新会话确认以下值与事务前一致：

```text
CHDR  SHORT
CFMT  DEF9,BYTE,BIN
CORD  LO
WFSU  SP,0,NP,0,FP,0,SN,0
```

CH1 和 CH2 的实际 `WAVEDESC`、100,002 点 payload、缩放与时间轴均能由当前 parser 处理。验收未保存波形数组。

## M5：双通道同次采集

每轮只执行一次 acquisition，随后在同一采集状态下读取 CH1 和 CH2。验收限值为：频率 1 kHz ±2%，Vpp 1 V ±10%，两路 Vpp 差异不超过 5%，归一化相关系数不低于 0.98。

| 轮次 | CH1 频率 | CH1 Vpp | CH2 频率 | CH2 Vpp | Vpp 差异 | 相关系数 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 999.900 Hz | 1.013335 V | 1000.200 Hz | 1.006668 V | 0.6601% | 0.999946 |
| 2 | 1000.000 Hz | 1.013335 V | 1000.200 Hz | 1.006668 V | 0.6601% | 0.999946 |
| 3 | 1000.000 Hz | 1.013335 V | 1000.100 Hz | 1.006668 V | 0.6601% | 0.999947 |

每轮每通道 100,002 点，质量告警为空。每轮审计为 33 次文本查询、4 次二进制查询、18 次状态事务写入；18 次写入全部完成，blocked request 和 binary write 均为 0。每轮都精确恢复 trigger mode、timebase、两路 V/div、trace 开关和传输状态。

`scope.capture_waveform` 委托给同一事务的单通道形式；`scope.capture_waveforms` 的双通道路径已直接实机验收。

## 独立收尾复核

验收脚本结束后使用新的只读会话复核，而不是依赖原会话自报：

- DG4202 输出为 OFF，原 5 Vpp 设置值和完整 channel profile 已恢复；
- SDS3054 CH1/CH2 均为 `DCL`；
- trigger mode 为 `AUTO`，timebase 为 `1E-3 S`；
- CH1/CH2 分别为 `360E-3 V` 与 `200E-3 V`；
- CH1 trace 为 ON，CH2 trace 为 OFF；
- `CHDR/CFMT/CORD/WFSU` 与 M4 记录一致；
- 收尾会话完成 13 次查询、0 次写入。

## 证据边界

验收只证明 SDS3054 固件 `8.4.1`、当前 VICP 路径和已声明的 6 项 capability。它不把 2026 年滚动手册中的其他型号、选件、Automation 对象或危险指令升级为当前实机支持。
