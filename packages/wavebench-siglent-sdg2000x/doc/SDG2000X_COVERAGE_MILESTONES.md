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
- [x] `SDG2122X` CH2 已完成 2 kHz 输出 OFF 写入和 5 kHz 输出 ON 实时写入闭环，最终恢复 1 kHz 且两路 OFF。
- [x] `source.set_amplitude_vpp` 已单独开放；限制为 2 mVpp 至 10 Vpp，并联合检查偏置包络。
- [x] `source.set_function` 已单独开放；四种有界周期波允许实时切换，Noise/DC 只允许输出 OFF 配置。
- [x] `source.set_square_duty_cycle` 已单独开放；只接受 FIX 模式方波和 0.001% 至 99.999%，钳位值由独立回读拒绝。
- [x] `SDG2122X` CH2 已完成频率、幅度、四种周期波函数和 20%/80% 方波占空比闭环；最终恢复 Sine / 1 kHz / 4 Vpp 且两路 OFF。
- [x] 五项基础写能力最终均通过核心 `SourceService` 的 CH1/CH2 A4 闭环；23 次写入全部完成，未知结果为 0。

## M4：高级命令域

- [x] 谐波 H2–H16 槽位、H2/H3 幅度、H2 相位及 ALL/EVEN/ODD 完成 SDG2122X A4 频谱验收；现有核心模型不可无损映射，暂不声明 capability。
- [x] 内部 AM、DSB-AM、FM、PM、PWM、ASK、FSK、PSK 完成 SDG2122X 输出 OFF 协议轮询与 A4 波形验收；外部源未接线。
- [x] Sweep LINE/LOG/STEP、UP/DOWN/UP_DOWN、INT/MAN 完成 SDG2122X 协议与 A4 波形验收；EXT 与 Trigger Out 未接线。
- [x] Burst 有限 INT/MAN 完成 SDG2122X 协议与 A4 周期数验收；EXT/Gate 仅回读，INF 物理判据未通过。
- [x] Pulse WIDTH/DUTY/RISE/FALL 完成 SDG2122X 协议与 A4 波形验收；DLY 仅 A3，hold 无权威查询字段。
- [x] `source.arbitrary_probe` 完成 SDG2122X CH1/CH2 核心 Service 零写入验收；内置目录实测 199 项。
- [x] SDG2122X 内置任意波目录 199/199 完成 DDS 选择、回读与 A4 非平坦输出冒烟验收；未发送上传或文件写入。
- [x] Noise、-1/0/+1 V DC 与 TARB 1 MSa/s 完成 A4；Noise Add 在当前固件上完成稳定负向验收。
- [x] Combine 双向异频合成、`EQPHASE`、CH1/CH2 Invert 完成 A4。
- [x] TRACE、F/P/A coupling、双向 PACP 完成协议验收；主要方向完成 A4；`TRDUCH` CH2→双路 Burst 完成重复 A4。
- [x] Sync、Counter、参考时钟、保护、系统设置与 Cascade 完成 18 查询、0 写入的 A3 验收。
- [x] 调制、Sweep、Burst、任意波和 Counter 保持独立分域，不合并成万能 SCPI 接口。
- [x] Trigger、任意波上传、参考时钟与全局状态的易失/外部副作用已明确记录；不执行用户波形上传或文件写入。
- [x] 只有公共 WaveBench model 与 Service 消费路径已明确时才声明 capability；其余结果保留为证据和通用 RFC 输入。

## M5：覆盖率与发行收尾

- [x] 版本 `0.8.0` 的 SDG 插件测试达到 348 项；源码 620/620 statements、244/244 branches，均为 100%。
- [x] 响应结构、数值边界、复合模式门禁、写后漂移、恢复不收敛和会话锁止均有语义测试。
- [x] 仓库全量 `895 passed, 2 skipped`；Ruff、插件 package check 与 `pip check` 通过。
- [x] 独立最终只读会话确认信号源 27 查询、示波器 54 查询、双方 0 写入；两路输出 OFF，RTM2032 AUTO 且无过载。
- [x] `SDG2042X` 与 `SDG2082X` 按共同手册协议和离线型号矩阵放行；不伪造其它型号 A4 证据。

## M6：Source V2 A0 离线适配

- [x] 声明 `source.snapshot_v2`、`source.basic_configure_v2` 与 `source.output_v2`，并将最低核心版本提高到 `0.8.24`。
- [x] 以纯读取 anchor/facet/anchor 计划读取 CH1/CH2；两个 Sine fixture 通道完成 38 次查询、0 次写入，低于 42 次声明上限。
- [x] Basic 与 Output 的 V2 MAIN 阶段各只允许一条已审计写命令，随后由核心独立快照回读。
- [x] 离线验证 V2 Basic 的 CH1/CH2 频率写入、Vpp、函数、方波占空比、写后回读不匹配的一次 OFF 恢复、未知写结果的零追加 I/O、Output ON/OFF、描述符/轮包交叉校验，以及 V1 Noise/DC 函数路径兼容。
- [ ] A1：未在实机确认 V2 快照响应、查询预算和型号/固件适用性。
- [ ] A2：未在实机确认 V2 Basic/Output 的回读、拒绝分支和失败恢复。
- [ ] A3：未通过授权示波器通道环回确认 V2 Basic 的频率、Vpp、函数和占空比；尚未记录偏置、端接、容差和最终 OFF 状态。

Noise 的 `STDEV` 与缺少最终 Vpp/Offset 的 DC/Noise 状态不被伪装成 Vpp。此类旧 `set_function`
调用保留 V1 的输出 OFF 事务；该规则不引入 RMS、峰值因子或统计模型。

## M7：Source V2 插件 opt in

- [x] A0：完成 `source.snapshot_v2`、`source.basic_configure_v2` 和 `source.output_v2` 的离线适配；覆盖 CH1/CH2 Basic 的函数、频率、Vpp、方波占空比、拒绝 `offset_v`、写后不匹配的一次 OFF 恢复、未知写结果的零追加 I/O，以及独立双通道 ON/OFF 的核心事务。
- [ ] A1：在授权实机上确认 V2 快照响应、查询预算、型号和固件适用性。
- [ ] A2：在授权实机上确认 V2 Basic/Output 的回读、拒绝分支、OFF 恢复和独立通道同时 ON。
- [ ] A3：通过授权示波器通道环回确认 V2 Basic 的频率、Vpp、函数和占空比，并记录偏置、端接、容差和最终 OFF 状态；不以 fake transport 替代该证据。

## C3：稳定发布审计

- [x] 完成离线审计准备：版本、描述符、发行元数据、文档、sdist 文件清单和 A0 测试边界一致。
- [ ] 在 A1–A3、稳定核心版本和最终发行包确定后完成签核；此前不得将 Source V2 写 capability 作为已发布能力。

## 实机门禁

任何实机任务开始前必须记录：目标型号、固件、脱敏 resource、初始输出状态、允许命令、禁止命令、成功标准和恢复步骤。2026 年 8 月 21 日的完整验收限制最大 10 Vpp，并在 9 Vpp 设置主动停止线；最大实测 4.24 Vpp。最终独立新会话确认两路 Sine / 1 kHz / 4 Vpp / OFF，除 Harmonic 按原状态恢复外，其余复合模式关闭。

未接线的 Sync、Counter、外部 Trigger/Gate、外部参考与多机 Cascade 只保留 A3 或明确未验收，不以软件覆盖率替代电气证据。
