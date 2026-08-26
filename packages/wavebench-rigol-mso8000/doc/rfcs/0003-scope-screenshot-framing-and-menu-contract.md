# RFC-0003：示波器截图 framing 与菜单合同

状态：Core 当前分支已实现；插件受限实机验收完成

目标仓库：WaveBench core

## Core 已解决的合同

Core R1.3 已采用 `query_binary()`、`ScopeScreenshotProfile` 与 `scope.screenshot_v2`，因此本 RFC 的原始 `query_raw_bytes_once()` 建议不再适用。截图请求现在使用精确 tuple：

```text
format = png
menu_mode = device | include | exclude
color_mode = device | color | monochrome | inverted
```

这足以安全表达 MSO8000 的两条路径之间的 framing 差异与菜单不可控制的情形：插件可只声明 `menu_mode="device"`，不把未知菜单状态伪装为 `exclude`。Core 同时负责有界二进制 I/O、PNG 完整性、状态恢复和新鲜验证。

`:DISPlay:DATA?` 仍不适用：手册只称其返回 PNG 数据流，没有定义 IEEE/TMC block 或可证明的 message boundary。`:SAVE:IMAGe <path>` 会在仪器或外部存储中创建或覆盖文件，仍不属于可接受的替代路径。

## 已解决：截图预算

`:SAVE:IMAGe:DATA?` 明确返回 TMC definite block、屏幕图像数据和结束符。手册给出的单个示例 payload 为 `387,356` bytes。Core 当前分支已将截图 V2 response 和 operation 硬上限提高到 `8,388,608` bytes，覆盖该示例。

插件的唯一 variant 采用 Core 的 `8,388,608`-byte 最大预算。该值不是对所有屏幕、固件、颜色或菜单状态的吞吐承诺；超出此预算的响应继续 fail closed。

保留以下安全限制：

- 一次 operation 仅允许一次 binary query；
- transport resynchronization 预算仍为 `0`；
- profile 不得声明超过 Core 全局上限；
- `DEFINITE_BLOCK`、精确 trailing 和 PNG 校验要求不变；
- 超出上限的响应继续 fail closed。

## 插件采用范围

MSO8104 首版受控声明 V2：

- capability 为 `scope.screenshot_profile` 与 `scope.screenshot_v2`，不恢复 legacy `scope.screenshot`；
- 仅使用 `:SAVE:IMAGe:DATA?` 和 `DEFINITE_BLOCK`；
- 仅声明 `png/device/device`，不写 `TYPE`、`INVert` 或 `COLor`；
- 先只读确认 `:SAVE:IMAGe:TYPE?` 为 `PNG`，否则在 binary query 前拒绝；
- 不使用 `:DISPlay:DATA?`、不创建仪器文件、没有临时状态写入，故变更字段与恢复步骤均为空；
- 记录固件的 `TYPE?` 回读 `PNG`，但 DATA payload 为无压缩 BMP24。driver 只接受固定 40-byte DIB、24 位、无压缩、完整像素数据的 BMP，并在内存中转换为 PNG；不支持的 BMP、JPEG、TIFF 与未知数据仍拒绝。
- 公开实机调用返回 `1024 × 600`、`47,584` bytes 的 PNG；精确 `LF` trailing、前后空错误队列与 healthy session 均已验证，最终 source 双路 OFF、scope STOP、CH1/CH2 high_z。

## 不采用的方案

- 对 `:DISPlay:DATA?` 猜测 `DEFINITE_BLOCK` 或 `MESSAGE` framing；
- 对二进制响应调用文本 `query()`；
- 为绕过预算将图片拆分、截断或使用文件路径；
- 将 `menu_mode="device"` 伪装为 `exclude`；
- 调低插件 profile budget 后声称支持超出该预算的截图。
