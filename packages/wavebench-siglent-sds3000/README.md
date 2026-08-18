# WaveBench SIGLENT SDS3000 插件（开发中）

[English](README_EN.md)

本包提供早期 SIGLENT SDS3000 系列示波器的 WaveBench 外置驱动。该系列不包含名称带 `X` 或 `HD` 的后续产品。当前已建立可安装插件、严格身份门禁、错误寄存器读取、通道耦合映射和二进制波形读取；其他 capability 仍在开发。

首个验证目标为 SIGLENT SDS3054。其他同代型号只有在厂商资料与测试证据充分时才会加入兼容范围。

## 已确认的仪器身份

- 机身型号：SIGLENT SDS3054，500 MHz、4 GSa/s；
- 平台标识：`SIGLENT Powered by TELEDYNE LECROY`；
- 脱敏远程身份：`LECROY,SDS3054,<serial>,8.4.1`；
- 前面板远程模式：`TCPIP (VICP)`；
- 命令体系：Teledyne LeCroy MAUI/X-Stream Remote Command Set。

上述身份只用于约束 SDS3054 驱动，不表示可以接受任意 LeCroy 仪器，也不表示其他 SIGLENT SDS 系列使用相同协议。

## 当前状态

- 阶段：M4 波形传输；
- distribution：`wavebench-siglent-sds3000`；
- canonical driver ID：`siglent.sds3000`；
- 仪器类型：`scope`；
- 首版型号：`SDS3054`；
- WaveBench 兼容范围：`>=0.8.22,<0.9`；
- transport：WaveBench `pyvisa`，当前只接受 `tcpip` 资源；
- 已声明 capability：`scope.idn`、`scope.errors`、`scope.channel_coupling`、`scope.fetch_waveform`。

descriptor 加载和 driver 工厂阶段均不执行仪器 I/O。调用 `scope.idn` 时只发送一次 `*IDN?`，并严格接受 `LECROY,SDS3054,<serial>,8.4.1`；其他厂商、型号或固件均在零写入的情况下拒绝。

`scope.channel_coupling` 将 MAUI 的 `A1M`、`D1M`、`D50`、`GND` 分别映射为 WaveBench 的 `ACL`、`DCL`、`DC`、`GND`。仪器返回 `OVL` 时按 50 Ω 输入过载处理并拒绝继续。`scope.errors` 依次读取并清除 `CMR`、`EXR` 和 `DDR`；它是 WaveBench 已有的 `stateful_read`，不是普通无副作用查询。

`scope.fetch_waveform` 使用 WaveBench 已有的波形模型和 `query_bin_block()` transport 接口。读取前查询 `CHDR`、`CFMT`、`CORD` 和 `WFSU` 状态，临时切换为 `DEF9,WORD,BIN` 与低字节在前，只读取一个分段，然后按逆序恢复原状态。恢复失败时返回 `StateDriftError`。当前只实现 `WF?` 读取；`WF` 写回内部存储仍隔离，不会被误报为已支持。

## 编程手册投放位置

将厂商编程手册或其本地转换结果放在：

```text
doc/vendor-local/
```

当前本地资料为 2026 年 2 月版《Oscilloscopes Remote Control and Automation Manual》。上传转换系统将原始 411 页手册拆为 200、200、11 页三段，项目会在原创审计文档中记录三段的顺序与哈希。推荐保留厂商原始文件名；需要统一命名时，可使用：

```text
Oscilloscopes_Remote_Control_and_Automation_Manual_2026-02.pdf
```

该手册晚于实机固件 `8.4.1`，且部分内容明确以 MAUI `8.5.0.0+` 为基线。手册中明确列出的实体构成审计分母，但只有离线证据或安全实机测试确认后，才会计入固件 `8.4.1` 的已支持集合。型号操作手册、数据表和发行说明也可放入同一目录。

来源哈希、分段顺序、适用边界和覆盖口径见 [`doc/MANUAL_BASELINE.md`](doc/MANUAL_BASELINE.md)。

完整指令分母和处置状态见 [`doc/COMMAND_COVERAGE.md`](doc/COMMAND_COVERAGE.md)。当前目录已固定 578 个明确实体，其中 478 个可调用实体，未分类数量为 0。

`doc/vendor-local/` 中除说明文件外的内容由仓库级 `.gitignore` 排除。厂商资料不会进入 Git；项目原创的协议摘要、覆盖矩阵和验收记录后续另写入 `doc/`。

## 手册到位后的检查顺序

1. 登记手册名称、文档号、修订号、发布日期、适用平台和 SHA-256。
2. 区分 IEEE 488.2 legacy commands 与 `VBS app...` Automation 对象树，并确认固件 `8.4.1` 的版本边界。
3. 核对 VICP、VXI-11、USBTMC 等通信方式与 WaveBench 现有 transport 的实际兼容情况。
4. 审计终止符、通信头、错误语义、波形模板、二进制传输、截图及状态副作用。
5. 冻结 distribution、canonical driver ID、身份门禁和兼容型号范围。
6. 按 M3–M8 逐项加入通过 FakeTransport 和分级实机验收的 capability。

## 安全边界

- 不使用 SDS3000X、SDS3000X HD 或其他新款 SIGLENT SDS 系列的 SCPI 手册推断本机协议。
- 不为缺失能力创建脱离 WaveBench 的公共接口；核心接口不足时单独提交建议。
- descriptor 导入不得连接仪器、扫描端口、创建文件或修改全局状态。
- driver 只能通过 WaveBench `DriverContext.open_transport()` 获取核心 transport。
- 仪器写入、输出切换和 acquisition trigger 不做盲目重试。
- 真实设备地址、序列号、凭据、原始波形、截图和实验日志不得提交。

## 许可证边界

本目录中的项目原创文档由仓库根目录 MIT License 覆盖。放入 `doc/vendor-local/` 的厂商资料保留其原始权利状态，不因此获得 MIT 授权，也不属于公开 distribution。
