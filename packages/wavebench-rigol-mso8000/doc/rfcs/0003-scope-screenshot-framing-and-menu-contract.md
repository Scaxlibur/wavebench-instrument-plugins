# RFC-0003：示波器截图 framing 与菜单合同

状态：提议

目标仓库：WaveBench core

## 问题

MSO8000 编程手册提供两条截图路径，但当前 WaveBench 公开接口无法同时安全表达响应 framing 与菜单可见性。

`:DISPlay:DATA?` 返回当前屏幕的 PNG 二进制数据。手册没有说明该响应带 IEEE/TMC definite-length block 头，因此插件不能把它交给只接受 block framing 的 `InstrumentTransport.query_bin_block()`；普通文本 `query()` 也不能无损读取任意二进制响应。猜测 framing 会把超时、截断或 PNG 首字节误判成有效响应。

`:SAVE:IMAGe:DATA?` 明确返回 TMC block，但内容受 `:SAVE:IMAGe:TYPE`、`:SAVE:IMAGe:INVert` 与 `:SAVE:IMAGe:COLor` 状态影响。这三项可以设计为快照、逐项回读与恢复的事务，手册却没有提供菜单 inclusion 的查询或设置。WaveBench 的 `ScopeScreenshotProtocol.screenshot_png()` 要求调用方传入 `include_menu`，Service 当前明确请求 `include_menu=False`。插件无法证明设备响应满足该合同，也不能静默忽略参数。

`:SAVE:IMAGe <path>` 会在仪器或外部存储中创建或覆盖文件，不属于可接受的截图替代路径。

## 建议接口

先为无 framing 声明的二进制查询增加单次读取接口，例如：

```python
class InstrumentTransport(Protocol):
    def query_raw_bytes_once(self, command: str) -> bytes: ...
```

要求：

- 命令和响应只发送、读取一次，失败后不重放；
- 返回未经文本解码或 block 解包的完整响应；
- 保留核心的 lease、access guard、审计与大小上限；
- 读取失败或截断时明确报告响应状态不确定；
- 各 transport backend 对终止符和读取完成条件具有一致、可测试的定义。

截图合同还需要表达设备不能控制或不能证明菜单可见性的情况。可将请求与结果分离，并允许结果报告未知状态，例如：

```python
@dataclass(frozen=True)
class ScopeScreenshotRequest:
    format: Literal["png"]
    color_scheme: Literal["color", "gray"]
    include_menu: bool | None = None


@dataclass(frozen=True)
class ScopeScreenshotResult:
    data: bytes
    color_scheme: Literal["color", "gray"]
    include_menu: bool | None
```

具体模型名和 capability 迁移方式由 core 决定；关键要求是调用方不能把「未知」误当成 `False`。

## capability 影响

核心合同补齐前：

- descriptor 不声明 `scope.screenshot`；
- driver 不调用 `:DISPlay:DATA?`，也不猜测其 framing；
- driver 不通过 `:SAVE:IMAGe:DATA?` 假装满足 `include_menu=False`；
- driver 不创建仪器文件，也不使用远程文件传输绕过截图协议。

核心提供原始二进制单次查询后，插件仍需验证 PNG 签名、响应大小、颜色设置回读与恢复，并为菜单可见性保留明确的未知或不支持结果。以上结论仍需实机验证。

## 替代方案

- 对 `:DISPlay:DATA?` 调用 `query_bin_block()`：手册没有 TMC block 证据。
- 对二进制响应调用文本 `query()`：存在解码、终止符、截断和重放风险。
- 仅支持默认 `include_menu=False` 并忽略参数：无法证明返回图片不含菜单。
- 使用 `:SAVE:IMAGe <path>` 后再读取文件：引入路径、覆盖、清理和权限副作用，违反基础插件的默认拒绝边界。
