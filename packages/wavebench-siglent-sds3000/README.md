# WaveBench SIGLENT SDS3000 插件（孵化）

[English](README_EN.md)

本目录用于准备早期 SIGLENT SDS3000 系列示波器的 WaveBench 外置驱动。该系列不包含名称带 `X` 或 `HD` 的后续产品。当前仅建立协议资料入口，不包含可执行插件、entry point 或已声明 capability。

首个验证目标为 SIGLENT SDS3054。其他同代型号只有在厂商资料与测试证据充分时才会加入兼容范围。

## 已确认的仪器身份

- 机身型号：SIGLENT SDS3054，500 MHz、4 GSa/s；
- 平台标识：`SIGLENT Powered by TELEDYNE LECROY`；
- 脱敏远程身份：`LECROY,SDS3054,<serial>,8.4.1`；
- 前面板远程模式：`TCPIP (VICP)`；
- 命令体系：Teledyne LeCroy MAUI/X-Stream Remote Command Set。

上述身份只用于约束 SDS3054 驱动，不表示可以接受任意 LeCroy 仪器，也不表示其他 SIGLENT SDS 系列使用相同协议。

## 当前状态

- 阶段：已收到 2026 年 2 月版 MAUI 编程手册，正在建立协议审计基线；
- 候选 distribution：`wavebench-siglent-sds3000`；
- 候选 canonical driver ID：`siglent.sds3000`；
- 候选仪器类型：`scope`；
- 初始候选型号：`SDS3054`；
- `pyproject.toml`：尚未创建，仓库级开发环境会跳过本目录；
- 可执行代码与 capability：无。

候选标识只用于组织孵化目录，不构成公开兼容承诺。正式型号范围、transport、WaveBench 版本范围和 capability 必须以手册、脱敏身份样本及测试结果为依据。

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

`doc/vendor-local/` 中除说明文件外的内容由仓库级 `.gitignore` 排除。厂商资料不会进入 Git；项目原创的协议摘要、覆盖矩阵和验收记录后续另写入 `doc/`。

## 手册到位后的检查顺序

1. 登记手册名称、文档号、修订号、发布日期、适用平台和 SHA-256。
2. 区分 IEEE 488.2 legacy commands 与 `VBS app...` Automation 对象树，并确认固件 `8.4.1` 的版本边界。
3. 核对 VICP、VXI-11、USBTMC 等通信方式与 WaveBench 现有 transport 的实际兼容情况。
4. 审计终止符、通信头、错误语义、波形模板、二进制传输、截图及状态副作用。
5. 冻结 distribution、canonical driver ID、身份门禁和兼容型号范围。
6. 建立只读 M0 插件骨架、FakeTransport 测试和 wheel 生命周期门禁。

## 安全边界

- 不使用 SDS3000X、SDS3000X HD 或其他新款 SIGLENT SDS 系列的 SCPI 手册推断本机协议。
- 不为缺失能力创建脱离 WaveBench 的公共接口；核心接口不足时单独提交建议。
- descriptor 导入不得连接仪器、扫描端口、创建文件或修改全局状态。
- driver 只能通过 WaveBench `DriverContext.open_transport()` 获取核心 transport。
- 仪器写入、输出切换和 acquisition trigger 不做盲目重试。
- 真实设备地址、序列号、凭据、原始波形、截图和实验日志不得提交。

## 许可证边界

本目录中的项目原创文档由仓库根目录 MIT License 覆盖。放入 `doc/vendor-local/` 的厂商资料保留其原始权利状态，不因此获得 MIT 授权，也不属于公开 distribution。
