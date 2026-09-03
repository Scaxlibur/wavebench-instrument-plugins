# WaveBench SIGLENT SDS800X HD 插件

[English](README_EN.md)

面向 SIGLENT SDS800X HD 系列示波器的外置 WaveBench 驱动包。`0.6.0` 提供严格身份、模拟通道耦合、`DMAX` 波形读取与单次采集、只读测量统计、PNG 截图，以及独立采集运行状态与控制。当前公开能力均已在 SDS804X HD TCPIP/VXI-11 路径完成受控实机验收。

## 当前状态

- Distribution：`wavebench-siglent-sds800x-hd` `0.6.0`
- Canonical driver ID：`siglent.sds800x-hd`
- 仪器类型：`scope`
- Backend：WaveBench 核心 `pyvisa` transport
- Resource scheme：`tcpip`、`usb`
- 已声明 capability：`scope.idn`、`scope.channel_coupling`、`scope.fetch_waveform`、`scope.capture_waveform`、`scope.capture_waveforms`、`scope.measurement_statistics`、`scope.screenshot_profile`、`scope.screenshot_v2`、`scope.acquisition_run_state`、`scope.acquisition_control`
- WaveBench：`>=0.8.23,<0.9`

descriptor 导入不执行仪器 I/O；factory 只通过 `DriverContext.open_transport()` 获取一个核心 transport。driver 每次显式 `idn()` 都发送 `*IDN?` 并严格核对四字段、厂商、支持型号和 14 字符 ASCII 序列号；同一 operation 内复用已解析型号。读取 coupling 前按型号限制二通道或四通道范围，再发送 `:CHANnel<n>:COUPling?`；只接受 `AC`、`DC` 或 `GND`。波形读取使用核心 `query_bin_block()`，返回核心 `WaveformData` / `WaveformHeader`。`close()` 幂等释放 transport。

## 产品范围

官方数据手册列出以下型号：

- 两通道：`SDS802X HD`、`SDS812X HD`、`SDS822X HD`；
- 四通道：`SDS804X HD`、`SDS814X HD`、`SDS824X HD`。

型号覆盖、LAN/USB 接口和 SCPI 远控能力来自 [SIGLENT SDS800X HD 产品资料](https://www.siglent.com/int/products-overview/sds800x-hd/)。当前 `idn_patterns` 使用公开型号字符串；严格 identity parser 依据 CN11G 的四字段格式。SDS804X HD 已取得脱敏实机样本，其他五个型号的具体返回仍待补证。

官方数据手册说明该系列模拟输入为固定 `1 MΩ`，没有内部 `50 Ω` 端接，因此 descriptor 声明 `fixed-high-impedance`。SDS804X HD 已完成 coupling、`1×` 探头和高阻连接复核；其他型号仍待补证。

## 当前能力

- `scope.idn`：每次返回本 operation 内 fresh query 并严格校验的原始 `*IDN?` 文本。
- `scope.channel_coupling`：返回大写 `AC`、`DC` 或 `GND`；无效类型、型号不存在的通道和未知响应均在 driver 边界拒绝。
- `scope.fetch_waveform`：读取已经停止的非 sequence 模拟通道记录；当前只支持 `points="dmax"`。
- `scope.capture_waveform` / `scope.capture_waveforms`：执行一次 SINGLE acquisition，轮询到 Stop 后读取一个或多个模拟通道；当前只支持 `points="dmax"`。
- `scope.measurement_statistics`：只读查询已经配置并启用的高级测量槽位；不会创建槽位、开启统计或重置历史。
- `scope.screenshot_profile` / `scope.screenshot_v2`：通过核心 MESSAGE binary 边界读取 `1024×600` PNG，支持普通和反色输出；严格验证 IEND 后的单个 `0A` content trailing，不保存图片。
- `scope.acquisition_run_state` / `scope.acquisition_control`：读取触发运行阶段，支持 AUTO/NORMAL 连续启动、STOP 和 SINGLE；SINGLE 完成只使用状态迁移证明，失败时恢复 acquisition/trigger baseline 并 fresh readback。

直接调用 `scope.channel_coupling` 时会先读取身份，以免在二通道型号上向不存在的 CH3 或 CH4 发送命令。WaveBench `status` fallback 在同一会话中先调用 `idn()`，因此不会重复身份查询。

波形读取不触发新的 acquisition，也不发送 `RUN`、`SINGLE` 或 `STOP`。driver 要求 `:TRIGger:STATus?` 返回 `Stop` 且 `:ACQuire:SEQuence?` 返回 `OFF`，随后保存 `SOURCE`、`START`、`INTERVAL`、`POINT`、`WIDTH` 和 `BYTEorder`。事务临时使用 `WORD`、`LSB`、`START 0`、`INTERVAL 1` 和 `POINT 0`，按 `MAXPoint?` 分块读取，成功或失败后均按依赖顺序恢复原 transfer 状态。

单次采集设置并回读 `TRIGger:MODE SINGLE`，发送 `TRIGger:RUN`，轮询 `TRIGger:STATus?` 直到 Stop，再要求 `ACQuire:NUMACq? >= 1`。超时或模式写入未生效时会发送 `TRIGger:STOP`。多通道接口只执行一次 acquisition，随后逐通道读取同一份停止记录；不使用 `*OPC?` 代替物理触发完成条件。

测量统计要求调用方明确确认槽位已经配置。driver 还会回读高级测量模式、槽位开关和统计开关，只在三项均满足时查询当前值、均值、最小值、最大值、标准差和统计次数。历史缓冲区只在调用方明确确认 acquisition 已停止时读取；所有统计接口均为零写入。

CN11G 没有记录错误队列命令，因此此插件不声明 `scope.errors`。WaveBench 服务在 `scope.check_errors=true` 时会要求该 capability；使用波形读取必须显式配置：

```toml
[scope]
driver = "siglent.sds800x-hd"
check_errors = false

[waveform]
format = "real"
byte_order = "lsbf"
points = "dmax"
```

直接调用 driver 时，`check_errors=True`、`points="def"` 和 `points="max"` 均在任何仪器 I/O 前失败。CN11G 的 `WAVeform:POINt` 参数只记录整数 NR1；当前不把 WaveBench 的 `DEF/MAX` 映射成未经证明的仪器关键字。

## 暂不提供的能力

当前版本不声明以下 capability：

- `scope.errors`
- `scope.autoscale`
- `scope.trace_metadata` / `scope.fetch_trace`
- 测量配置、数学/FFT、数字通道和历史帧能力

编程手册中的其他命令只有在完成格式审计、FakeTransport 测试和必要的受控实机验收后，才会进入 driver 和 descriptor。当前没有 raw SCPI 入口，也不推测其他 SIGLENT 系列的协议可以直接复用。`scope.fetch_waveform` 是读取现有记录，不等同于 `capture_waveform`。

## 编程手册投放位置

本地 `CN11G` 编程手册及转换结果保存在：

```text
doc/vendor-local/
```

当前转换因工具限制拆为三个目录。手册支持表将 SDS800X HD 的最低固件列为 `1.1.3.1`。官方入口为 [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/)，项目原创结论见[功能覆盖矩阵](doc/SDS800X_HD_COVERAGE_MATRIX.md)、[实机验收记录](doc/SDS800X_HD_HARDWARE_ACCEPTANCE.md)和 [Scope R1.3 conformance 证据](doc/SDS800X_HD_R13_CONFORMANCE.md)。

`doc/vendor-local/` 中除说明文件外的内容由仓库级 `.gitignore` 排除，整个目录也被 sdist 构建规则排除。厂商 PDF 不会随 Git push 或公开 distribution 发布；项目原创的协议摘要、能力矩阵和验收记录应另写入 `doc/`。

## 下一阶段门禁

1. 使用其他 SDS800X HD 型号获取脱敏 `*IDN?` 样本，复核身份格式和二通道、四通道 coupling 返回。
2. 后续取得 USB 条件时，复核 binary block、WORD 对齐、时基和 transfer 状态恢复；TCPIP 真实多块已验收。
3. 仅在取得明确协议或实机证据后评估 `DEF/MAX` 点数模式；不得猜测关键字。
4. 截图和独立采集控制已按核心 `0.8.23` Scope R1.3 合同 opt-in；typed trace 受 `8388608` 点上限与现有 `10M` 记录的兼容性边界阻塞，math/FFT 等待后续通用扩展合同。不通过私有 raw SCPI 绕过核心。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地厂商手册不因此获得 MIT 授权，也不属于公开 distribution。
