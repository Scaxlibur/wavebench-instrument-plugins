# WaveBench SIGLENT SDS800X HD 插件

[English](README_EN.md)

面向 SIGLENT SDS800X HD 系列示波器的外置 WaveBench 驱动包。`0.3.0` 在严格身份和模拟通道耦合查询之外，新增保守的 `DMAX` 已停止记录读取。该波形路径已完成离线事务测试，尚未经过真实仪器验收。

## 当前状态

- Distribution：`wavebench-siglent-sds800x-hd` `0.3.0`
- Canonical driver ID：`siglent.sds800x-hd`
- 仪器类型：`scope`
- Backend：WaveBench 核心 `pyvisa` transport
- Resource scheme：`tcpip`、`usb`
- 已声明 capability：`scope.idn`、`scope.channel_coupling`、`scope.fetch_waveform`
- WaveBench：`>=0.8,<0.9`

descriptor 导入不执行仪器 I/O；factory 只通过 `DriverContext.open_transport()` 获取一个核心 transport。driver 发送 `*IDN?`，严格核对四字段、厂商、支持型号和 14 字符 ASCII 序列号，并缓存稳定身份。读取 coupling 前按型号限制二通道或四通道范围，再发送 `:CHANnel<n>:COUPling?`；只接受 `AC`、`DC` 或 `GND`。波形读取使用核心 `query_bin_block()`，返回核心 `WaveformData` / `WaveformHeader`。`close()` 幂等释放 transport。

## 产品范围

官方数据手册列出以下型号：

- 两通道：`SDS802X HD`、`SDS812X HD`、`SDS822X HD`；
- 四通道：`SDS804X HD`、`SDS814X HD`、`SDS824X HD`。

型号覆盖、LAN/USB 接口和 SCPI 远控能力来自 [SIGLENT SDS800X HD 产品资料](https://www.siglent.com/int/products-overview/sds800x-hd/)。当前 `idn_patterns` 只使用公开型号字符串；严格 identity parser 依据 CN11G 的四字段格式，但在获得脱敏实机 `*IDN?` 样本前，不把型号空格、大小写和固件格式视为实机验收结论。

官方数据手册说明该系列模拟输入为固定 `1 MΩ`，没有内部 `50 Ω` 端接，因此 descriptor 暂声明 `fixed-high-impedance`。在把波形读取视为实机可用前，仍需使用目标硬件复核 coupling 查询、探头衰减和外部端接条件。

## 当前能力

- `scope.idn`：返回经严格校验并在当前 driver 会话中缓存的原始 `*IDN?` 文本。
- `scope.channel_coupling`：返回大写 `AC`、`DC` 或 `GND`；无效类型、型号不存在的通道和未知响应均在 driver 边界拒绝。
- `scope.fetch_waveform`：读取已经停止的非 sequence 模拟通道记录；当前只支持 `points="dmax"`。

直接调用 `scope.channel_coupling` 时会先读取身份，以免在二通道型号上向不存在的 CH3 或 CH4 发送命令。WaveBench `status` fallback 在同一会话中先调用 `idn()`，因此不会重复身份查询。

波形读取不触发新的 acquisition，也不发送 `RUN`、`SINGLE` 或 `STOP`。driver 要求 `:TRIGger:STATus?` 返回 `Stop` 且 `:ACQuire:SEQuence?` 返回 `OFF`，随后保存 `SOURCE`、`START`、`INTERVAL`、`POINT`、`WIDTH` 和 `BYTEorder`。事务临时使用 `WORD`、`LSB`、`START 0`、`INTERVAL 1` 和 `POINT 0`，按 `MAXPoint?` 分块读取，成功或失败后均按依赖顺序恢复原 transfer 状态。

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
- `scope.capture_waveform` / `scope.capture_waveforms`
- `scope.screenshot`
- 其他状态、测量、数学、数字通道和历史帧能力

编程手册中的其他命令只有在完成格式审计、FakeTransport 测试和必要的受控实机验收后，才会进入 driver 和 descriptor。当前没有 raw SCPI 入口，也不推测其他 SIGLENT 系列的协议可以直接复用。`scope.fetch_waveform` 是读取现有记录，不等同于 `capture_waveform`。

## 编程手册投放位置

本地 `CN11G` 编程手册及转换结果保存在：

```text
doc/vendor-local/
```

当前转换因工具限制拆为三个目录。手册支持表将 SDS800X HD 的最低固件列为 `1.1.3.1`。官方入口为 [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/)，项目原创结论见[功能覆盖矩阵](doc/SDS800X_HD_COVERAGE_MATRIX.md)。

`doc/vendor-local/` 中除说明文件外的内容由仓库级 `.gitignore` 排除，整个目录也被 sdist 构建规则排除。厂商 PDF 不会随 Git push 或公开 distribution 发布；项目原创的协议摘要、能力矩阵和验收记录应另写入 `doc/`。

## 下一阶段门禁

1. 获取脱敏 `*IDN?` 样本，复核身份格式和二通道、四通道 coupling 返回。
2. 使用 TCPIP 与 USB 脱敏样本核对 binary block、分片、WORD 对齐、时基和 transfer 状态恢复。
3. 仅在取得明确协议或实机证据后评估 `DEF/MAX` 点数模式；不得猜测关键字。
4. `*OPC?` 等待和一次多通道 acquisition 经实机确认后，再评估 capture 与其他写能力。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地厂商手册不因此获得 MIT 授权，也不属于公开 distribution。
