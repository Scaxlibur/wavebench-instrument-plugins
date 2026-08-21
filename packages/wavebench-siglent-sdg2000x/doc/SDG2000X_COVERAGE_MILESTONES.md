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
- [ ] 输出开启后使用示波器交叉验证实际频率、Vpp 与偏置。

## M3：基础写事务

- [ ] 单独评估频率、函数、幅度、占空比和输出 capability。
- [ ] 写前读取可恢复状态；输出相关实验默认先确认 OFF。
- [ ] 每个写入只发送一次，并通过独立查询回读。
- [ ] 对歧义失败锁住后续写入；恢复失败时明确报告状态不确定。

## M4：高级命令域

- [ ] 调制、Sweep、Burst、任意波和 Counter 各自立项，不合并成万能 SCPI 接口。
- [ ] trigger 和任意波上传必须单独说明不可逆或易失副作用。
- [ ] 只有公共 WaveBench model 与 Service 消费路径已经明确时才声明 capability。

## 实机门禁

任何实机任务开始前必须记录：目标型号、固件、脱敏 resource、初始输出状态、允许命令、禁止命令、成功标准和恢复步骤。2026 年 8 月 21 日的只读验收仅允许身份与状态查询，两路输出均保持 OFF；后续输出开启和示波器采集仍需单独授权。
