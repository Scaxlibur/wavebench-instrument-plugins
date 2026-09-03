# Development and validation

在修改 driver、parser、profile、测试或仓库级开发代码，以及进行插件代码评审时读取本页。默认目标是用最小离线改动证明生产行为，不连接真实仪器。

## Establish the local contract

开始修改前只读取与任务直接相关的材料：

1. 受影响包的 `pyproject.toml`、production descriptor 和入口重导出。
2. 即将修改的 driver、parser、profile 或工具，以及所有直接调用方。
3. 聚焦测试、共享 fixture 和该包已有的 wheel／lifecycle 测试。
4. 包 README 与 `doc/README*` 只用于找到型号边界和证据入口，不把其摘要当作源码合同。
5. 涉及公共类型、capability 或恢复语义时，读取当前依赖范围对应的 WaveBench Core 模型与测试。

不同仪器类型、厂商和包的实现并不统一。通道编号、单位、错误队列、二进制块、timeout、重试、状态恢复和多 entry point 行为都必须从当前包事实确认，不能从相邻包类推。

## Minimal implementation loop

1. 用现有失败测试、复现或明确合同固定问题边界。
2. 在所有调用路径共享的最小正确位置修改；不为单一实现新增抽象层。
3. 用 FakeTransport 或当前包已有替身验证准确命令、顺序、解析、边界和失败行为。
4. 先运行聚焦测试，再运行包级测试；只有共享代码或仓库级工具受影响时才扩大到全仓。
5. 检查 descriptor、metadata、生成内容和公开摘要是否因行为变化而需要同步。

不要为获得绿色测试而放宽生产限制、吞掉异常、增加盲目重试或让测试依赖实际实验室资源。

## Driver and parser checks

按适用范围检查：

- 输入在发出 SCPI 前完成类型、范围、通道和枚举验证。
- query 与 write 的确切格式、终止符、单位和顺序由 FakeTransport 断言。
- parser 拒绝截断、缺字段、非有限数值、超大长度和设备错误，不静默猜测。
- 二进制块同时限制单次读取、总点数、query 次数和操作总量；普通文本重试策略不得套用到 capture。
- 有状态查询、错误队列读取、autoscale、fetch 或 screenshot 的副作用在合同和测试中明确。
- 写入完成状态不明时不重放命令；返回 fail-closed 结果并保留上层恢复所需信息。
- 会改变输出、保护、触发或采集状态的操作具备前置条件、读回验证和停止策略。
- 厂商 quirk 留在型号实现或 profile，不泄漏成 Core 的通用假设。

## FakeTransport coverage

优先复用当前包 fixture。测试至少覆盖改动路径的：

- 正常请求、精确响应解析和返回类型。
- 边界值与非法参数在 I/O 前拒绝。
- 设备错误、timeout、畸形响应和不完整二进制数据。
- query／write 次数上限和不允许的额外命令。
- 失败后状态、latch、恢复请求或 session 健康度。
- descriptor/factory 分界：descriptor 加载为零 I/O，factory 才打开 transport。

测试名称应描述可观察合同，不依赖实现内部行号或临时变量。

## Validation ladder

根据变更逐级运行，前一级失败时先停止并处理根因：

```bash
python3 scripts/dev_env.py check
.venv/bin/python -m pytest -q packages/<package>/tests/<focused-test>.py
.venv/bin/python -m pytest -q packages/<package>/tests
.venv/bin/python -m ruff check <changed-paths>
git diff --check
```

以下情况再扩大验证：

- 修改共享仓库脚本、跨包约定或 Core 兼容处理：运行相关根测试，必要时运行全仓测试。
- 修改 metadata、entry point、descriptor 或正式包集合：检查生成式目录和开发环境漂移，并执行 package check。
- 修改构建包含范围、入口发现或卸载行为：执行实际 wheel／sdist 和隔离生命周期测试。
- 修改 conformance 或实机 harness：先运行其全部离线测试，再考虑单独授权的实时验收。

不要声称「全仓通过」，除非实际运行了全仓命令。报告精确命令、通过数量、跳过项和未运行门禁。

## Diff review mode

用户要求评审时只报告可操作问题，不直接修改。按优先级检查：

1. 可能导致错误命令、危险输出、状态损坏、数据丢失或恢复失败的问题。
2. descriptor 与 production 实现、metadata 或 Core 合同不一致。
3. wheel、sdist、发现、升级和卸载回退缺口。
4. 缺少会让错误逃逸的测试，尤其是失败、边界与零 I/O 导入测试。
5. 私有资源、厂商资料或原始证据进入 Git 或发行物。

每条 finding 给出文件和最小行范围、触发条件、实际影响与修复方向。没有 finding 时明确说明剩余测试或实机验证风险。

## Documentation boundary

代码变更附带的短小 README 或 reference 同步属于本流程，但仍以源码事实为准。若主要任务变成文档盘点、拆分、迁移或中文页面重写，切换到 `$wavebench-docs`；不要让生产开发 Skill 承担文档信息架构。

## Completion report

说明：

- 哪个包、entry point 与生产行为发生变化。
- 哪些测试证明正常与失败路径。
- 是否同步 metadata、descriptor、目录或构建产物。
- 哪些门禁因范围、依赖或授权未运行。
- 是否访问网络、改动 `.venv`、本地配置或真实仪器。
