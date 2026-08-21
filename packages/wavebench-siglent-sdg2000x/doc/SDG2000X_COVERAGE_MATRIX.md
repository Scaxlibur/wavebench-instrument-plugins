# SDG2000X 功能覆盖矩阵

[English](SDG2000X_COVERAGE_MATRIX_EN.md)

## 当前结论

当前版本在 M3 输出控制基础上开放 `source.set_frequency`。离线测试覆盖三个登记型号、两通道、固定波形频率边界、Sweep→FIX 安全切换、写后漂移、歧义写入、OFF 恢复和会话锁止。`source.set_frequency` 的实机证据单独记录，不从 `SDG2122X` 外推到其它型号。

## 覆盖状态

| 命令域 | WaveBench capability | 当前状态 | 放行条件 |
| --- | --- | --- | --- |
| 仪器身份 | `source.idn` | `SDG2122X` / `2.01.01.39R7T2` 实机通过；其它型号待验收 | 按型号与固件补充脱敏证据 |
| 系统错误队列 | 无 | 未开放 | 确认查询命令、空队列语义和是否为消费型读取 |
| 通道基础状态 | `source.status` | SDG2122X 三轮只读结果一致；CH1/CH2 输出后均完成频率、Vpp 与均值物理交叉验收 | 其它型号与固件逐台验收 |
| 输出控制 | `source.output` | 三个型号通过离线合同矩阵；SDG2122X CH1/CH2 各完成一次 ON→采样→OFF，未知写结果为 0 | 补充 SDG2042X 与 SDG2082X 实机证据 |
| 固定波频率 | `source.set_frequency` | 三个型号通过离线合同矩阵；按正弦、方波、斜波、脉冲和任意波分别限制频率 | 补充 SDG2122X 双通道闭环证据；其它型号逐台验收 |
| 固定波函数、幅度与占空比 | 无 | 默认拒绝 | 参数范围、负载语义、安全限制和事务恢复均有证据 |
| 调制、Sweep 与 Burst | 无 | 未开放 | 每个子域单独形成只读 profile，再评估写 capability |
| 任意波形 | 无 | 默认拒绝 | 明确数据格式、易失内容、副作用、大小限制和恢复边界 |
| Counter | 无 | 未开放 | 先建立不改变计数器状态的严格只读 profile |

## 默认拒绝项

- 不发送 `*RST` 或其它全局预置命令。
- 输出开启只能经 `source.output` 和核心 `max_source_vpp` 上限执行；频率只经 `source.set_frequency` 修改，不发送 trigger、Burst 或任意波形写入。
- 不提供 raw SCPI 入口。
- 不把产品页列出的功能直接等同于已实现 capability。

## 事实源

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- 本地编程手册：`doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`，修订号 `PG02_E05C`
- [协议审计](SDG2000X_PROTOCOL_AUDIT.md)
- [只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)
- [输出控制实机验收](SDG2000X_OUTPUT_ACCEPTANCE.md)
- 当前 descriptor、driver 和 fake transport 测试
