# RFC-0001：非重放文本查询

状态：Core R1 已实现（未发布）

目标仓库：WaveBench core

## 问题

`:SYSTem:ERRor?`、`*ESR?` 等查询会消费设备状态。普通只读状态查询可以按其幂等性选择重放策略；消费型文本查询必须在调用点显式禁用重放。

以错误队列为例，第一次 query 可能已经让仪器删除队首错误，只是响应在返回途中失败。自动重放会读取下一条错误，调用方无法恢复第一条响应，也无法判断队列移动了几次。

MSO8104 只对错误队列采用这个语义，不用 `*CLS`、`*ESR?` 或 `*STB?` 代替实际记录。

## 已实现接口

Core R1 没有新增独立的 `query_text_once()`，而是把策略公开为 `query()` 的显式参数：

```python
class InstrumentTransport(Protocol):
    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str: ...
```

对消费型文本读取，插件必须传入 `ReplayPolicy.NO_REPLAY`。该策略保证一次调用不会因读回或解码失败而重发命令，并保留 Core 的审计、lease 和 access guard 语义。响应失败仍表示队列可能已消费，插件不得自行重试或退回到默认文本 query。

这实现了原提案所需的安全性质，同时避免新增一个与现有 `query()` 平行的 transport 入口。

## capability 影响

MSO8104 descriptor 已受控声明 `scope.error_drain_v1`，但 legacy `scope.errors` 继续不声明。`drain_errors(max_records=...)` 的规则为：

- 每条 `:SYSTem:ERRor?` 都使用显式 `ReplayPolicy.NO_REPLAY`；
- 严格解析 `<integer>,"<message>"`，只在第一个逗号处分隔；message 可以包含逗号；
- 仅把实机观察到的精确记录 `0,"No error"` 视为空队列终止；
- 达到 `max_records` 而尚未终止时，再读取一条 overflow 记录，并返回未确认排空；
- 格式异常、transport 失败或未确认排空均 fail closed，不清队列、不重试。

Core 的有界 fetch/capture 在 `scope.check_errors=true` 时可在主操作前后调用该 drain，并核对实际 query 数。legacy autoscale 等不走该 Core 策略的路径仍要求 `scope.check_errors=false`。

公开硬件验收已在 `scope.check_errors=true` 的单通道 capture 中观察到前后两次空 drain、`1,000` 样本和 13 字段恢复／新鲜验证。非零记录、FIFO 顺序和 overflow 目前仅有离线故障注入证据。

## 替代方案

- 将 `read_retry_attempts` 全局设为 0：会改变所有普通状态查询，粒度过粗。
- 直接调用未显式指定 `ReplayPolicy.NO_REPLAY` 的 `query()`：无法审计消费型读取是否使用单发语义。
- 读取 `*STB?` 代替错误队列：只能得到摘要位，不能返回实际错误。
- 用 `*CLS` 掩盖队列：会破坏调用方应见的错误记录。
