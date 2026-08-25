# RFC-0003：示波器截图 framing 与菜单合同

状态：Core 当前分支已实现；插件离线实现完成，待独立实机验收

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

插件不使用 Core 的最大预算，而是将自己的唯一 variant 限为 `524,288` bytes。该值覆盖已知示例，但不构成对所有屏幕、固件、颜色或菜单状态的吞吐承诺；超出此预算的响应继续 fail closed。

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
- 离线测试已覆盖实际类型预检、预算、trailing、PNG 结构和异常停止读取；实际 payload、精确 trailing、PNG 尺寸／校验、session health 和空错误队列仍须独立实机验收。

## 不采用的方案

- 对 `:DISPlay:DATA?` 猜测 `DEFINITE_BLOCK` 或 `MESSAGE` framing；
- 对二进制响应调用文本 `query()`；
- 为绕过预算将图片拆分、截断或使用文件路径；
- 将 `menu_mode="device"` 伪装为 `exclude`；
- 调低插件 profile budget 后声称支持超出该预算的截图。
