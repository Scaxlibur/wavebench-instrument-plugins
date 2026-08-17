# SDG2000X 功能覆盖矩阵

[English](SDG2000X_COVERAGE_MATRIX_EN.md)

## 当前结论

当前运行时仍为 M0 身份查询基线，M1 离线协议审计已经完成。`source.status` 已具备明确的主仓库模型映射，可进入 M2 实现；其余命令域继续保持关闭。

## 覆盖状态

| 命令域 | WaveBench capability | 当前状态 | 放行条件 |
| --- | --- | --- | --- |
| 仪器身份 | `source.idn` | 已实现；支持编程手册记录的两种返回格式 | 受控实机确认型号、固件和终止符 |
| 系统错误队列 | 无 | 未开放 | 确认查询命令、空队列语义和是否为消费型读取 |
| 通道基础状态 | `source.status` | 已审计，待实现 | CH1/CH2 fake transport 严格解析和零写入测试通过 |
| 输出控制 | 无 | 默认拒绝 | 写前状态、显式 OFF、写后回读和失败恢复均有测试 |
| 固定波配置 | 无 | 默认拒绝 | 参数范围、负载语义、安全限制和事务恢复均有证据 |
| 调制、Sweep 与 Burst | 无 | 未开放 | 每个子域单独形成只读 profile，再评估写 capability |
| 任意波形 | 无 | 默认拒绝 | 明确数据格式、易失内容、副作用、大小限制和恢复边界 |
| Counter | 无 | 未开放 | 先建立不改变计数器状态的严格只读 profile |

## 默认拒绝项

- 不发送 `*RST` 或其它全局预置命令。
- 不发送输出开启、trigger、Burst、Sweep 或任意波形写入。
- 不提供 raw SCPI 入口。
- 不把产品页列出的功能直接等同于已实现 capability。

## 事实源

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- 本地编程手册：`doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`，修订号 `PG02_E05C`
- [协议审计](SDG2000X_PROTOCOL_AUDIT.md)
- 当前 descriptor、driver 和 fake transport 测试
