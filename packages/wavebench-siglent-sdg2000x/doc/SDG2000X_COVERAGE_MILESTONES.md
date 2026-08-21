# SDG2000X 覆盖里程碑

[English](SDG2000X_COVERAGE_MILESTONES_EN.md)

## M0：开发基线

- [x] 建立独立 distribution、canonical driver ID 和 MIT 许可证。
- [x] 提供中英文 README、覆盖矩阵和本地手册目录。
- [x] 实现 query-only `source.idn`，支持两种已记录的身份返回格式。
- [x] 使用 fake transport 验证无写入、错误型号拒绝、factory 和 close 生命周期。
- [x] 验证 wheel entry point、许可证、sdist 排除和隔离安装发现。

## M1：编程手册审计

- [x] 将 `PG02_E05C` 版 SDG Series Programming Guide 放入 `doc/vendor-local/`。
- [x] 记录通信接口、命令终止符和 transport 归属；确认手册未定义错误队列查询。
- [x] 按数据手册冻结三个支持型号，并记录两种 `*IDN?` 响应格式。
- [x] `SDG2122X` 固件 `2.01.01.39R7T2` 的 `*IDN?` 已完成脱敏实机记录；其它型号待补。
- [x] 将通道、输出、固定波、调制、Sweep、Burst、任意波和 Counter 命令分域登记。

## M2：严格只读状态

- [x] 实现 CH1/CH2 `SourceStatus`，不发送写命令。
- [x] 对数值单位、枚举、通道目标和关系约束进行 fail-closed 解析。
- [x] 在 fake transport 守卫下证明完整状态读取为零写入。
- [x] `SDG2122X` CH1/CH2 连续三轮读取稳定，transport 审计确认 0 次写请求；结论不外推。
- [x] 输出开启后使用 RTM2032 交叉验证 CH1/CH2 实际频率、Vpp 与均值。

## M3：基础写事务

- [x] 单独评估并开放 `source.output`；频率、函数、幅度和占空比继续分项评估。
- [x] 写前读取完整状态；输出开启要求 FIX、Sweep OFF、Vpp 幅度和偏置均已知。
- [x] 目标写入只发送一次，并通过独立完整状态查询回读。
- [x] 写后失败锁住后续 ON；执行 OFF 恢复，恢复失败时明确报告状态不确定。
- [x] `SDG2122X` CH1/CH2 完成 4 Vpp 高阻闭环验收，最终两路均为 OFF。
- [x] `source.set_frequency` 已单独开放；按型号和波形限制频率，写入遵循完整安全快照、单写回读、OFF 恢复和会话锁止。
- [ ] 函数、幅度与占空比写事务另行立项。

## M4：高级命令域

- [ ] 调制、Sweep、Burst、任意波和 Counter 各自立项，不合并成万能 SCPI 接口。
- [ ] trigger 和任意波上传必须单独说明不可逆或易失副作用。
- [ ] 只有公共 WaveBench model 与 Service 消费路径已经明确时才声明 capability。

## 实机门禁

任何实机任务开始前必须记录：目标型号、固件、脱敏 resource、初始输出状态、允许命令、禁止命令、成功标准和恢复步骤。2026 年 8 月 21 日的 M3 验收明确限制最大 10 Vpp，实际使用 4 Vpp；每路仅执行一次 ON 和一次 OFF，并以独立新会话确认两路最终 OFF。
