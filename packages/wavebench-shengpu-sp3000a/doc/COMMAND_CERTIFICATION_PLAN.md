# SP30120 命令认证计划

[English](COMMAND_CERTIFICATION_PLAN_EN.md) | [命令矩阵](COMMAND_CERTIFICATION_MATRIX.md)

本文定义当前实验室 SP30120 的逐命令认证规则。厂商资料描述的是 SP3000A 系列，并列出 SP30120A；系列级 `*IDN?` 不能把当前无 A 后缀设备转换成 SP30120A。所有结论都限定到当前设备和当前固件行为。

## 认证状态

|状态|含义|驱动处理|
|---|---|---|
|`verified-read`|查询至少三轮稳定，边界、语义和副作用明确|允许加入类型化只读 API|
|`verified-control`|快照、写入、回读、独立效果、恢复和恢复回读均通过|允许加入有边界的类型化控制 API|
|`manual-only`|只允许人工、受控实验；包括已有观察但语义未关闭的返回|保留证据，不声明 capability|
|`unsupported-firmware`|规范语法和正确前置状态下返回错误、超时或没有可见效果|不发送；文档记录型号/固件边界|
|`unsafe-quarantined`|造成失联、前面板卡死或无法可靠恢复|静态隔离，永不自动重试|
|`option-absent`|依赖未安装选件|不声明该 capability|
|`doc-ambiguous`|手册语法、型号或返回结构不足以安全认证|fail closed|
|`untested`|尚未进入实机矩阵|不进入驱动|

## 通用门禁

每个查询从静默串口边界开始，只发送 canonical 手册语法，累计读取到 LF 或有界上限；不能把一次底层 `read()` 当成完整响应。目标查询后必须重新确认系列身份和核心状态指纹。错误、超时和无响应均不自动重试。

每个写操作必须执行：

1. 确认串口静默、身份正常且 RF 为 OFF；
2. 将原值、精确目标命令、精确恢复命令和阶段写入私有恢复 journal；
3. 只发送一条目标写命令；
4. 使用独立 query 或状态快照确认结果；
5. 恢复原值并再次回读；
6. 确认身份、RF OFF 和核心指纹仍正常；
7. 连续三个完整循环一致后才可成为 `verified-control`。

写操作没有 ACK 不自动判失败，因为当前固件上的 `TRIM SING/CONT` 已观察到静默成功；但没有可验证回读或独立效果时绝不判通过。任何失联、非静默边界、状态无法恢复或前面板卡死都会立即终止本轮并请求人工电源循环。

## M0–M3 范围

### M0：台账和工具

- 去重手册命令、查询、参数范围、选件依赖和 OCR 歧义；
- 建立逐命令状态矩阵；
- 私有探针必须由调用方显式提供资源，不得硬编码设备路径；
- 一次只认证一个目标命令；
- 写前 journal、RF-OFF 互锁、身份/指纹检查和危险命令隔离必须由测试覆盖。

### M1：只读查询

覆盖仍属于 M0–M3 安全边界、且有明确有界响应规则的手册 query。Marker 无活动数据和选件未安装必须分别记录，不能合并成“命令失败”。语义已属于 M5 Marker 测量或 M6 存储的 query 不会仅因语法上只读就提前执行。`OUTPRFORM?` 与 `OUTSTATEC?` 沿用已有受限证据，但不会因此开放 trace 或通用 snapshot。

### M2：低副作用可逆状态

仅认证具有可靠原值 query 和恢复 query 的蜂鸣器、显示、参考位置、时钟显示、语言、扫描单次/连续、内/外触发及低副作用 Marker 显示/选择。日期和时间只有在完整回读与恢复可证明时执行。`SYSTem:LOCal` 作为独立会话行为认证，不与其它写操作混用。

### M3：RF-OFF 扫频和测量配置

RF 必须在整个阶段保持 OFF。认证 CW/SWEEP、频率窗口、点频、频偏、扫频时间/自动、平均、输入阻抗/量程和幅相测量等配置。数值命令采用当前安全原值附近的最小变更，不测试型号极限。已经明确失败的 trace 配置不重复碰撞；`SWET:MODE LOG` 永久隔离。

## 本轮明确不执行

- RF ON、输出电平和输出阻抗的真实输出认证；
- `*RST`、`PRES`、保存/调出或覆盖存储槽；
- 自动 Marker 搜索、带宽/Q/反射/驻波比测量；
- 外检波、鉴频或 GPIB 等未确认选件写入；
- USB、LAN 或 GPIB transport；
- 已知危险命令及任何猜测式别名笛卡尔积。

这些项目分别属于后续受控 RF、Marker/分析、存储/复位、选件和 transport 阶段。

## 2026-07-25 实机认证结果

本轮在 RF 始终为 OFF 的前提下完成。16 个低副作用查询各取得至少 5 轮完整成功 journal：`CENT?`、`SPAN?`、`STOP?`、`INPLSW?`、`FMT?`、`SETSCALE?`、`SETREFL?`、`SETREFP?`、`SETCTIME?`、`CLOCKSW?`、`LANGSEL?` 和 `MARK1?` 至 `MARK5?`。每轮均从静默边界开始，并在目标响应后重建完整核心指纹。

以下可逆控制各完成连续 3/3 的“写前持久化 journal → 单条写入 → 独立 query → 完整指纹 → 恢复 → 恢复 query → 原始指纹”闭环：

- `TRIM CONT→SING→CONT`；
- `SETREFP 4→5→4`；
- `CLOCKSW ON→OFF→ON`；
- `LANGSEL CHINESE→ENGLISH→CHINESE`；
- `EXTT OFF→ONSWEE→OFF`。

最终状态逐项复核为 RF OFF、TRIM CONT、参考位置 4、时钟显示 ON、中文界面、外触发 OFF；无活动隔离。RF OFF 只完成了从 ON 到 OFF 的一次单向安全操作，不据此开放通用 RF 控制。

当前仍不把这些私有认证操作接入生产 descriptor/driver。频率窗口、显示刻度、日期时间写入、Marker 显示、阻抗、FUNC、幅相和 trace 配置因联动状态、异常回读、无回读或固件失败而保持未认证或更严格状态。

## 代码准入

实机通过不等于自动声明通用 capability。准入顺序是：精确协议与错误映射、类型化厂商驱动方法、离线 FakeTransport/恢复测试，最后才是 WaveBench descriptor capability。驱动不提供任意 SCPI passthrough；所有写方法都必须有参数边界、RF 互锁、确认、恢复顺序和不可重试错误语义。

公开提交不得包含真实资源、序列号、原始响应、实验室地址或恢复 journal。原始证据仅存放在被忽略的私有目录。每个功能族使用独立签名本地提交，不自动 push、tag 或发布。
