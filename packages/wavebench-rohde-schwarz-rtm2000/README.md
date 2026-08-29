# WaveBench R&S RTM2000 插件

[English](README_EN.md)

面向 Rohde & Schwarz RTM2000 系列、当前以 RTM2032 为实机基线的 WaveBench 可执行示波器插件。

## 身份与开发基线

- distribution：`wavebench-rohde-schwarz-rtm2000`
- canonical driver ID：`rohde-schwarz.rtm2032`
- 开发基线：WaveBench `0.8.25`
- WaveBench：`>=0.8.25,<0.9`
- Python：`>=3.11`
- 默认 transport backend：核心提供的 `rsinstrument-socket`

本插件的 0.13.0 开发线对齐 WaveBench `v0.8.25`，不维护旧核心兼容矩阵，也不自动声明兼容未来 `0.9`。安装后，显式 canonical ID
`rohde-schwarz.rtm2032` 选择外置实现；短 alias `rtm2032` 始终选择内建 fallback。卸载
插件后，canonical ID 也回退内建实现。

## 能力与边界

- `*IDN?`、错误队列和显式 autoscale；
- 厂商专用只读 identity/options/health 快照，不消费 EVENT 寄存器或错误队列；
- RTM2032 CH1/CH2 类型化模拟通道、时基和探头元数据快照；
- 当前波形的类型化 X/Y 缩放、点数、量化位数和每采样值数量快照；
- RTM2032 CH1/CH2 基础 edge-trigger 类型化只读快照；
- 只读 average/segmented acquisition 状态，K15 专属查询受选件门控；
- 受控 average acquisition：调用方须明确确认 acquisition 已停止；仅暂时修改 average count、single count 和全局 channel arithmetic，成功或失败后均回读恢复，恢复不确定会锁存该实例后续 average 写入；
- RTM2032 CH1/CH2 的只读 K15 history 时间戳表；
- 显式确认已配置槽位后的自动测量只读统计；
- 现有 math、FFT、reference、cursor 状态的只读 metadata/readout；
- Scope V2 只读接口：通道输入状态、B1 门控的数字状态、严格的 identity 五字段 snapshot、
  仅支持 1–4 号槽且不含 buffer 的测量统计，以及已配置 FFT 的三字段状态；
- RTM2032 CH2 edge trigger 的厂商专用最小受控配置闭环；
- 当前波形读取与单次 acquisition；
- 一次 acquisition 后按通道读取多路波形；
- 通道 coupling 查询和 PNG 截图；
- `DEF` / `MAX` / `DMAX` 点数模式原样交给 RTM2000。

插件只负责 RTM2000 厂商 SCPI、header/REAL 波形解析和错误语义。RsInstrument 会话、超时、
高阻保护、Service、artifact、run plan 和实验级状态恢复留在核心。空列表、短列表、无效 header、
非 PNG 截图和 OPC 超时都显式失败，不补零、不伪造成功、不盲目重试。

`backend = "lan"` 按 descriptor 首选顺序使用 RsInstrument SocketIO，不依赖 VISA-C 或
pyvisa-py。诊断兼容性时可显式选择 `rsinstrument`、`rsinstrument-rsvisa` 或
`rsinstrument-pyvisa-py`；切换后端必须重新打开会话，读取失败后不会自动重放。插件仅对
`MAX` / `DMAX` 波形数据读取使用独立的长传输 timeout，并记录不含地址、序列号和波形内容的
分块进度、点数、字节数、耗时与吞吐 telemetry。

## 配置示例

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.60::INSTR"

[scope]
driver = "rohde-schwarz.rtm2032"
default_channel = 1
check_errors = true

[scope.options]
long_waveform_timeout_ms = 300000
```

示例使用 RFC 5737 文档地址。默认测试不扫描资源、不连接仪器，也不发送真实 SCPI。

## 编程手册投放位置

将 RTM2000 系列示波器编程手册放到：

```text
doc/vendor-local/RTM2000_programming_manual.pdf
```

也可以保留厂商原始文件名。`doc/vendor-local/` 中除说明文件外的内容会被 Git 忽略，整个目录也会从 sdist 排除，不会随仓库推送或公开发行包发布。项目根据手册整理的 SCPI 索引、能力矩阵和验收资料应另放在公开 `doc/` 中，并明确区分手册声明与实机验证结果。

当前手册命令面与插件、内建 fallback、实机证据的对照见 [RTM2000 手册功能覆盖矩阵](doc/RTM2000_COVERAGE_MATRIX.md)。

## 验收状态

0.1.0 已于 2026-07-24 完成真实 wheel 的受控 RTM2032 LAN/VXI-11 验收：受管安装与 healthy/load、
canonical 与短 alias 路由、双通道单次 acquisition、`DEF` / `MAX` / `DMAX` 完整波形、
autoscale、高阻 coupling 守卫、PNG 截图、20/20 双通道重复采集和空错误队列均通过。
`MAX` 每通道实测 10000000 点，`DMAX` 每通道实测 6250000 点；长记录使用独立 300 s
传输上限，不把统一 30 s 超时误判为协议失败。验收前保存了完整 setup 快照，结束后确认
setup blob、配置指纹和活动采集状态均恢复。验收未修改真实 `wavebench.toml`，未提交真实
地址、序列号、波形、截图、快照或命令日志。实验级快照与恢复仍属于核心/验收工具边界，
不进入厂商驱动。

0.2.0 将默认 LAN transport 改为 RsInstrument SocketIO，保留上述显式兼容后端。离线门禁
覆盖 descriptor 路由、调用级长传输 timeout、脱敏 telemetry 和 wheel 生命周期。RTM2032
实机已通过 SocketIO 的 DEF/MAX/DMAX、截图、autoscale、20/20 重复采集与空错误队列验收。
实验级 `SYST:SET` setup 恢复不属于插件驱动：SocketIO 写入曾出现只部分生效，因此验收工具
固定使用已验证的 VXI-11 512-byte 协议分片，并在重连后只读核对完整 blob、配置指纹和活动
采集状态。验收结束时快照已删除，真实地址、序列号、波形和命令日志均未进入提交。

0.3.0 开发线新增严格类型化的只读 identity/options/health 快照。health 快照只读取
`*STB?`、operation/questionable condition、acquisition available/count 和 sample rate；不读取会
消费状态的 EVENT 寄存器，也不自动清空错误队列。该厂商专用 API 不扩张 WaveBench 核心
capability 声明。0.3.0 还增加 RTM2032 CH1/CH2 的模拟通道、时基和探头元数据快照；
`FULL` 带宽、`UNKN` 阻抗和仪器不可用数值映射为 `None`；封闭枚举中的未知值、格式非法的
开放 token、非有限值、未加引号文本和 CH1/CH2 之外的索引均失败关闭。命令索引只证明命令面存在，返回类型来自 RTM2032
受控只读实测；不会外推为所有 RTM2000 型号的通用契约。实机已验证两路通道、当前时基和
无源探头状态，验收后 status byte 为 0；未读取 EVENT 或错误队列，也未发送设置命令。

0.4.0 增加厂商专用只读 `waveform_metadata_snapshot(channel)`。它交叉验证
`DATA:HEADER?`、`POINTs?`、X increment/origin，并返回 Y increment/origin、垂直量化位数和
每个 sample interval 的值数量；未知/非整数/非有限响应以及混合记录造成的 X 轴不一致均失败关闭。
RTM2032 CH2 实机只读验收返回 10000 点、200 ns X 步长、20 mV/bit 和 8-bit 分辨率；调用未发送
写命令、未产生 status/questionable 错误，也未改变 acquisition count。连续运行时 operation condition
会随正常触发周期在 waiting/non-waiting 间变化，因此不把它误作恒定前后条件。
`DATA:HEADER?` 第四字段不是 segment ID；history/segment identity 仍未实现，也不纳入本版本声明。

0.5.0 首个小步新增厂商专用只读 `edge_trigger_snapshot()`。当前类型域只覆盖 RTM2032 实机
证实的 `EDGE / CH1|CH2 / AUTO / POS / DC / hysteresis AUTO / holdoff OFF` 基线；未知 trigger
类型、source、模式、斜率、coupling 或 holdoff 均失败关闭，不推断手册索引未给出的返回域。CH2
校准方波只读验收得到 0.53 V trigger level 和 50 ns holdoff time；9 条查询前后 status byte、
questionable condition 和 acquisition count 保持健康，未读取 EVENT/error queue，也未发送写命令。

0.5.0 第二个小步新增 `configure_ch2_edge_trigger(level_v=...)`，但不声明通用 trigger capability。
它只接受已启用、未过载、高阻 `DCL/ACL` 的 RTM2032 CH2 基线和当前显示量程内的有限电平；
在实例级可重入 I/O 锁内固定写入 `EDGE / CH2 / AUTO / POS / DC / level`，随后逐字段回读，
确认未写入的 hysteresis/holdoff 保持原值，并复核非消费型 health 与 identity。写入开始后的任意
timeout、回读不符、健康异常或身份变化都会永久锁存该实例的 trigger 写路径，后续调用零 I/O
拒绝；不自动重试、回滚、find-level、autoscale、single、清错误队列或读取 EVENT。生产 setter
明确由调用方负责持久恢复；受控实机验收用私有 fsync journal 将 CH2 level 从 0.53 V 改为
0.65 V 后恢复至 0.53 V，前后 status byte/questionable condition 均为 0，acquisition count 均为 53。

0.6.0 将上述七类只读快照接入 WaveBench 0.8.1 的选择性 `scope.snapshot` 公共契约。
`get_snapshot(channel)` 在同一实例 I/O 锁内组合 identity、health、指定模拟通道、时基、
探头、波形元数据和 edge-trigger 快照；descriptor 仅为本 canonical 外置驱动声明该能力，
因此 `wavebench scope status --channel N` 可用，而不要求其他 scope 驱动实现。原有
`RTM2000*Snapshot` 导入名保留为公共模型的兼容别名。该聚合调用仍不读取 EVENT/错误队列，
也不发送设置命令；真实 RTM2032 的 identity、CH1/CH2 snapshot 与 acquisition status 组合路径已完成受控实机验收。

0.7.0 接入 WaveBench 0.8.2 的选择性 `scope.acquisition_status` 与
`scope.history_timestamps` 公共契约。两条路径均只查询；K15 专属查询必须由 `*OPT?`
精确返回 K15 token。时间戳按 oldest-to-newest 顺序严格合并 relative、absolute、date 三张
`:ALL?` 表，不选择 history segment、不启动采集，也不消费错误队列。RTM2032 已确认 K15 与
average/segmented 只读状态；history timestamp table 查询发生 timeout，未重试且仍属阻塞项。

0.8.0 新增 `scope.measurement_statistics`。调用方必须显式确认 1–4 号槽位已经配置；读取统计
buffer 时还必须显式确认 acquisition 已停止。实现不配置、启用或复位测量槽，也不读取或清空
错误队列。`NAN` 结果表示 unavailable；timeout 后结果状态为未知且不重试。RTM2032 上调用方
确认已配置的 CH2 frequency 槽已完成 actual/average/min/max/stddev/count 受控验收；STOP 状态
buffer 仍待验收。

0.9.0 新增只读分析状态面。math/reference 只读 metadata，不下载波形本体，也不修改全局传输
格式；FFT/cursor 必须由调用方显式确认已经在前面板配置。实现不定义 FFT expression、不移动
cursor、不 update/save/load reference、不启动采集，也不消费错误队列。RTM2032 的 math
metadata、FFT status 与 vertical cursor delta readout 已完成受控验收并恢复前面板状态；reference
存储为空，故 metadata 实机验收保持阻塞，未调用 `UPDATE` 制造测试数据。

0.10.0 接入 WaveBench 0.8.5 的 `scope.capture_average`。这是一条窄的、需要调用方显式
`--acquisition-stopped` 确认的受控写路径：预检既有 `REAL,32` / `LSBF` 传输格式，然后仅临时
写入 `ACQuire:AVERage:COUNt`、`ACQuire:NSINgle:COUNt` 和全局 `CHANnel:ARITHmetics`，执行
一次 `SINGle`，确认 `ACQuire:AVERage:COMPlete?` 后读取当前波形。它不写 `FORMat`、byte order、
point mode、时基、垂直档位、触发或 K15 history 状态。无论采集或波形读取成功与否，都会恢复并
回读三项配置；恢复失败或结果不一致会锁存该实例的 average 写路径，后续调用零 I/O 拒绝。该实现
目前有离线事务测试，尚无独立实机验收结论。任一配置写（包括第一条）超时都会按“结果未知”
处理：即使随后的恢复回读一致，也会永久锁存当前驱动实例，避免继续依赖一次无法证明结果的写事务。

0.11.0 新增 `scope.digital_status` 只读状态面。每次调用先用 `*OPT?` 精确确认 B1，再读取
D0–D15 中一个显式通道的 activity、display、technology、threshold、threshold coupling、
hysteresis、deskew、size、position 和 label。该路径不读取 `DIGital:DATA?`，不写阈值/显示/
传输格式，不启动或停止采集，也不消费错误队列。RTM2032 实机已完成 D0–D15 全通道验收：
单会话共发出 208 条 query，write 与 binary read 均为 0，四组映射和 D0 重复读取一致性通过；
CLI 的 D0/D15 端到端输出也通过。验收时全部数字通道均未显示、activity 为 LOW、阈值为
1.4 V；这些值只记录当时仪器状态，不构成数字探头电气输入或数字波形 payload 验收。

0.12.0 新增 `scope.digital_waveform` 只读数字波形面。调用方必须显式确认采集已经停止；
驱动先以 `*OPT?` 门控 B1，并要求仪器当前传输格式已经是 ASCII（手册记为 `ASC,0`；
RTM2032 实机会回读 `CSV,0`）。随后逐通道查询
`DIGital<n>:DATA:POINts?`、`HEADER?`、`XORigin?`、`XINCrement?` 与 `DATA?`，严格核对
所有通道的采样数和 X 轴，再在主机侧按 Dn→`uint16` bit n 合并。该路径不发送写命令，
不切换 STOP/RUN，不修改格式、点数、显示或阈值，也不读取错误队列。当前只有 FakeTransport
离线验收。RTM2032 只读预检已确认 B1 和 `CSV,0` 门控可通过，但当时 D0 未显示且
`DIGital0:DATA:POINts?` 返回 0，驱动在 `DATA?` 前拒绝继续；因此数字波形 payload 仍未验收。

0.13.0 将五类既有只读能力接入 WaveBench 0.8.25 的 Scope V2 契约。通道输入状态只从
`CHANnel<n>:COUPling?` 映射 coupling 与 termination，数值阻抗明确标记为 unavailable；数字状态
复用既有 B1 门控查询，未提供的 threshold scope 与 timing calibration 明确标记为 unavailable；
snapshot 固定为 identity 五字段、最多两次查询；测量统计只接受 1–4 号已配置槽位，不读取
buffer，并要求五个聚合值均为有限数；FFT 状态只提供 average complete、RBW 与 sample rate。
这些适配器不新增 SCPI 写入，不改变既有 V1 方法、FFT 数值分析或波形采集逻辑。
RTM2032 的 CH1/CH2 输入状态、CH1/CH2 identity snapshot 和 D0 数字状态已通过受控只读验收；
相关会话全部强制为 `read_only`，write request 与 binary write 均为 0。测量统计与 FFT V2
仍以离线等价测试和既有 V1 实机证据为边界；由于没有新鲜的前面板配置确认，本轮未冒充
`configured=True` 重跑。

## 开发验证

```bash
python -m pytest -q packages/wavebench-rohde-schwarz-rtm2000/tests
python -m ruff check packages/wavebench-rohde-schwarz-rtm2000
python -m wavebench plugin package check packages/wavebench-rohde-schwarz-rtm2000
```

真实地址、序列号、波形、截图和命令日志不得提交。本插件采用 [MIT License](LICENSE)。

## 来源

0.1.0 从 WaveBench 主仓库 `973fc88` 的内建 RTM2032 协议实现迁移，只把厂商驱动、
descriptor、entry point 和 FakeTransport 测试外置。
