# SDG2000X 功能覆盖矩阵

[English](SDG2000X_COVERAGE_MATRIX_EN.md)

## 当前结论

当前版本已开放主仓库现有五项基础 Source 写 capability。频率、函数、幅度、方波占空比和输出事务均覆盖三个登记型号、两通道、写后漂移、歧义写入、OFF 恢复和会话锁止。`SDG2122X` CH2 已完成周期波闭环；Noise/DC 仅完成 OFF 配置回读。高级模式继续分域开发，不提供 raw SCPI 旁路。

## 覆盖状态

| 命令域 | WaveBench capability | 当前状态 | 放行条件 |
| --- | --- | --- | --- |
| 仪器身份 | `source.idn` | `SDG2122X` / `2.01.01.39R7T2` 实机通过；其它型号待验收 | 按型号与固件补充脱敏证据 |
| 系统错误队列 | 无 | 未开放 | 确认查询命令、空队列语义和是否为消费型读取 |
| 通道基础状态 | `source.status` | SDG2122X 三轮只读结果一致；CH1/CH2 输出后均完成频率、Vpp 与均值物理交叉验收 | 其它型号与固件逐台验收 |
| 输出控制 | `source.output` | 三个型号通过离线合同矩阵；SDG2122X CH1/CH2 各完成一次 ON→采样→OFF，未知写结果为 0 | 补充 SDG2042X 与 SDG2082X 实机证据 |
| 固定波频率 | `source.set_frequency` | 三个型号通过离线合同矩阵；SDG2122X CH2 的 2 kHz OFF 写入与 5 kHz ON 写入通过 RTM2032 闭环 | 补充 SDG2122X CH1 及其它型号实机证据 |
| 固定波幅度 | `source.set_amplitude_vpp` | 三个型号通过离线矩阵；SDG2122X CH2 的 2/3 Vpp OFF/ON 写入通过闭环 | 补充 CH1 和其它型号实机证据 |
| 固定波函数 | `source.set_function` | 四种周期波在 SDG2122X CH2 实时闭环通过；Noise/DC 仅完成 OFF 配置回读 | Noise/DC 等待可复用安全模型；补充其它型号 |
| 方波占空比 | `source.set_square_duty_cycle` | 20%/80% 在 SDG2122X CH2 实测高电平占比 0.200/0.800 | 补充频率相关点、CH1 和其它型号 |
| 谐波 | 无损 capability 暂缺 | SDG2122X H2–H16 槽位通过；H2/H3 幅度、H2 相位和 ALL/EVEN/ODD 通过 A4 频谱 | 采用 Source V2 变长/selected-only 模型后再声明 capability |
| 调制、Sweep 与 Burst | 无 | 未开放 | 每个子域单独形成只读 profile，再评估写 capability |
| 任意波形 | 无 | 默认拒绝 | 明确数据格式、易失内容、副作用、大小限制和恢复边界 |
| Counter | 无 | 未开放 | 先建立不改变计数器状态的严格只读 profile |

## 默认拒绝项

- 不发送 `*RST` 或其它全局预置命令。
- 输出开启只能经 `source.output` 和核心 `max_source_vpp` 上限执行；频率与幅度只经对应公开 capability 修改，不发送 trigger、Burst 或任意波形写入。
- 不提供 raw SCPI 入口。
- 不把产品页列出的功能直接等同于已实现 capability。

## 事实源

- [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT Waveform Generator 文档下载页](https://siglentna.com/resources/documents/waveform-generators/)
- 本地编程手册：`doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`，修订号 `PG02_E05C`
- [协议审计](SDG2000X_PROTOCOL_AUDIT.md)
- [只读实机验收](SDG2000X_READONLY_ACCEPTANCE.md)
- [输出控制实机验收](SDG2000X_OUTPUT_ACCEPTANCE.md)
- [频率写入实机验收](SDG2000X_FREQUENCY_ACCEPTANCE.md)
- [基础写入实机验收](SDG2000X_BASIC_WRITE_ACCEPTANCE.md)
- 当前 descriptor、driver 和 fake transport 测试
