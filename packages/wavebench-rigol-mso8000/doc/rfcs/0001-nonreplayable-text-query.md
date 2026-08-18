# RFC-0001：非重放文本查询

状态：提议

目标仓库：WaveBench core

## 问题

`InstrumentTransport.query()` 可按连接配置重放失败的文本 query。这适合幂等状态读取，但不能安全读取 `:SYSTem:ERRor?`、`*ESR?` 等消费型响应。

以错误队列为例，第一次 query 可能已经让仪器删除队首错误，只是响应在返回途中失败。自动重放会读取下一条错误，调用方无法恢复第一条响应，也无法判断队列移动了几次。

现有 `query_bin_block()` 与 `query_float_list()` 已按不可重放操作处理，但公开 transport 没有对应的文本入口。MSO8104 插件因此不能严格实现 `scope.errors`。

## 建议接口

在 `InstrumentTransport` 增加语义明确的方法：

```python
class InstrumentTransport(Protocol):
    def query_text_once(self, command: str) -> str: ...
```

要求：

- 只发送一次命令；
- 读取或解码失败后不重放；
- 错误信息明确说明响应状态可能已经部分消费；
- 保留现有审计、lease 与 access guard；
- PyVISA、RsInstrument、serial 与测试 transport 使用一致语义。

不建议给 `query()` 增加默认行为会变化的布尔参数。单独方法更容易审计，也能让插件代码显式暴露消费边界。

## capability 影响

核心发布该接口前：

- descriptor 不声明 `scope.errors`；
- 波形与 capture 示例必须配置 `scope.check_errors=false`；
- driver 不使用 `*CLS` 掩盖错误队列缺口；
- `*ESR?` 等消费型状态不进入普通快照。

核心发布后，插件可用 `query_text_once()` 实现有限次 drain，并严格解析 `<integer>,"<message>"`。消息可能包含逗号，解析时只按第一个逗号分隔状态码与 quoted message。

## 替代方案

- 将 `read_retry_attempts` 全局设为 0：会改变所有普通状态查询，粒度过粗。
- 直接使用 `query()`：无法证明队列读取没有被重放。
- 读取 `*STB?` 代替错误队列：只能得到摘要位，不能返回实际错误。
