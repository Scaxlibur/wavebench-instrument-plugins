# WaveBench SIGLENT SDS800X HD 插件

[English](README_EN.md)

面向 SIGLENT SDS800X HD 系列示波器的外置 WaveBench 驱动包。当前版本只建立可安装、可发现、可执行身份查询的 M0 开发骨架，不提供波形采集或仪器状态修改能力。

## 当前状态

- Distribution：`wavebench-siglent-sds800x-hd` `0.1.0`
- Canonical driver ID：`siglent.sds800x-hd`
- 仪器类型：`scope`
- Backend：WaveBench 核心 `pyvisa` transport
- Resource scheme：`tcpip`、`usb`
- 已声明 capability：`scope.idn`
- WaveBench：`>=0.8,<0.9`

descriptor 导入不执行仪器 I/O；factory 只通过 `DriverContext.open_transport()` 获取一个核心 transport。当前 driver 只发送 `*IDN?`，并提供 `close()` 释放 transport。

## 产品范围

官方数据手册列出以下型号：

- 两通道：`SDS802X HD`、`SDS812X HD`、`SDS822X HD`；
- 四通道：`SDS804X HD`、`SDS814X HD`、`SDS824X HD`。

型号覆盖、LAN/USB 接口和 SCPI 远控能力来自 [SIGLENT SDS800X HD 产品资料](https://www.siglent.com/int/products-overview/sds800x-hd/)。当前 `idn_patterns` 只使用公开型号字符串；在获得脱敏实机 `*IDN?` 样本前，不把这些模式视为完整身份认证。

官方数据手册说明该系列模拟输入为固定 `1 MΩ`，没有内部 `50 Ω` 端接，因此 descriptor 暂声明 `fixed-high-impedance`。进入波形采集阶段前仍需使用目标硬件复核 coupling 查询、探头衰减和外部端接条件。

## 暂不提供的能力

当前版本不声明以下 capability：

- `scope.errors`
- `scope.autoscale`
- `scope.fetch_waveform`
- `scope.capture_waveform` / `scope.capture_waveforms`
- `scope.screenshot`
- `scope.channel_coupling`
- 其他状态、测量、数学、数字通道和历史帧能力

编程手册中的命令只有在完成命令格式审计、fake transport 测试和必要的受控实机验收后，才会进入 driver 和 descriptor。不要用 M0 骨架执行裸 SCPI 或推测其他 SIGLENT 系列的协议可以直接复用。

## 编程手册投放位置

将本地编程手册放在：

```text
doc/vendor-local/SDS800XHD_Series_ProgrammingGuide.pdf
```

具体版本可按实际下载文件名保留。官方入口为 [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/)。

`doc/vendor-local/` 中除说明文件外的内容由仓库级 `.gitignore` 排除，整个目录也被 sdist 构建规则排除。厂商 PDF 不会随 Git push 或公开 distribution 发布；项目原创的协议摘要、能力矩阵和验收记录应另写入 `doc/`。

## 下一阶段门禁

1. 放入并登记编程手册版本。
2. 核对通信终止符、错误队列、截图和波形二进制块格式。
3. 获取脱敏 `*IDN?` 样本，收紧身份模式。
4. 先实现只读错误队列和当前波形读取，再评估 acquisition 与写能力。
5. 每项 capability 分别补齐 fake transport 测试和受控实机证据。

## 许可证

本目录中由项目原创的代码和文档采用 [MIT License](LICENSE)。本地厂商手册不因此获得 MIT 授权，也不属于公开 distribution。
