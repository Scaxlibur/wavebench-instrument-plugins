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
- [ ] 实机 `*IDN?` 样本延后到受控实机阶段，公开材料只保留脱敏形式。
- [x] 将通道、输出、固定波、调制、Sweep、Burst、任意波和 Counter 命令分域登记。

## M2：严格只读状态

- [ ] 先实现 CH1/CH2 `SourceStatus`，不发送写命令。
- [ ] 对数值单位、枚举、通道目标和关系约束进行 fail-closed 解析。
- [ ] 在 transport 守卫下证明完整 profile 为零写入。
- [ ] 受控实机连续读取并确认结果稳定，不外推到未验收型号或固件。

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

任何实机任务开始前必须记录：目标型号、固件、脱敏 resource、初始输出状态、允许命令、禁止命令、成功标准和恢复步骤。未经明确授权不连接仪器。
