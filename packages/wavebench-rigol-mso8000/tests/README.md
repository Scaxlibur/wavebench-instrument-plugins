# 离线测试

本目录只使用 FakeTransport、故障注入、构建产物和一次性虚拟环境，不扫描端口或连接真实仪器。

本目录中的测试不构成实机证据。测试中的身份、资源、序列号、波形和截图均为虚构数据；受控实机结论记录在 `doc/`。

M3 波形测试只向状态化 FakeTransport 发送命令，并覆盖传输状态恢复、二进制故障不重放、恢复失败锁存和并发串行化。

M4 采集测试使用触发状态序列和小型分块 payload，覆盖一次 SINGLE、模式读回、终态／状态迁移 proof、MAX/DMAX、总点数预算与部分结果；测试点数不是实机吞吐证据。

采集控制与 bounded capture 测试覆盖 `scope.acquisition_run_state` 的单条 trigger-status 映射、SINGLE 后的 `SING` 模式读回、terminal STOP、`WAIT/TD → STOP`、失败 cleanup、恢复 `*OPC?` 轮询，以及 13 字段 fresh verification。正式 descriptor 已声明 `scope.acquisition_control`、`scope.capture_waveform` 和 `scope.capture_waveforms`；离线测试不替代受控实机验收。

错误队列 drain 测试覆盖有符号状态码、含逗号 message、精确 `0,"No error"` 终止、每条消费型 query 的 `ReplayPolicy.NO_REPLAY`、格式异常、通信失败、最大记录数和 overflow。公开有界 fetch/capture 的 `scope.check_errors=true` 路径还验证 Core 在主操作前后执行 drain；离线测试不替代非零记录与 overflow 的实机证据。

M7 autoscale 测试覆盖系统使能预检、一次写入、`OPC=0 → 1` 的有界轮询、超时／异常回包锁存和可选跳过等待；不会产生真实波形，也不证明自动设置效果。

M7 数学元数据测试通过 MATH 显示预检和状态化 FakeTransport 验证 NORM/BYTE preamble、六字段传输状态恢复、错误锁存与零数据读取；不证明数学运算结果或 FFT 精度。

M7 cursor 测试只覆盖预先配置的手动同源 `TIME + SEC` 与 `AMPL + SOUR` 读取，以及其余模式和单位的默认拒绝；不移动光标，也不证明读数准确度。

统计测量 V2 测试覆盖显式 `item + sources` selector、6 条固定纯读取查询、双 source 延时/相位项、允许的数字周期 source、无 buffer 预检、有限数和整数 count 解析，以及失败后的停止查询行为；不配置统计项、不清零设备历史，也不证明统计准确度。

FFT 状态 V2 测试覆盖目标 math slot 的 `FFT` operator 前置、6 条固定纯读取 query、source/window/unit/频率范围解析、无合同字段的精确 unavailable、非 FFT 或非法回包的停止查询行为，以及零写入；不配置或移动 FFT、Math、波形传输状态，也不证明 FFT 测量准确度。

采集状态 V2 测试覆盖固定 type/sample rate/memory depth query、AVER 模式的条件平均次数 query、父级 average 分区的 not applicable 语义、无合同字段的 unavailable、严格数值范围与幂次平均次数解析、失败后的停止查询和零写入；不读取 trigger、OPC、状态寄存器或错误队列，也不证明平均完成或采集完成。

数字状态 V2 测试覆盖 D0～D15 的零 I/O 参数门、LA 模块缺席时不发送 `:LA:*?`、D0/D7/D8/D15 的 POD 映射、显示/标签/POD 阈值/timing calibration/size 的严格解析、固定查询顺序、无合同字段的精确 unavailable、非法回包后的停止查询和零写入；不读取数字 waveform，也不推断逻辑活动、电气阈值或编码。

快照 V2 测试覆盖 CH1～CH4 的零 I/O 参数门、identity profile 的精确字段集、一次 `*IDN?` 与完整 13 项授权选件状态查询、空 options 只能来自全量未安装回包、稳定的 55 项 unavailable、无效 identity/选件回包后的停止查询和零写入；不读取状态寄存器、错误队列、trigger、波形或二进制数据。
