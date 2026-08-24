# SDG2000X 只读实机验收

[English](SDG2000X_READONLY_ACCEPTANCE_EN.md)

## 结论

2026 年 8 月 21 日，一台 `SDG2122X` 完成 `source.idn` 与 `source.status` 的受控实机验收。目标固件为 `2.01.01.39R7T2`。同一会话连续读取 CH1 与 CH2 三轮，返回结果完全一致；WaveBench transport 审计记录 19 次查询、0 次写请求和 0 次仪器状态修改写入。

本次验收只证明该型号与固件的身份、输出状态、基本波和 Sweep 状态查询可由插件严格解析。`SDG2042X`、`SDG2082X` 与其它固件仍待逐台确认。

## 测试环境

- 插件：`wavebench-siglent-sdg2000x` 0.2.0。
- 核心：WaveBench 0.8.23。
- 信号发生器：`SDG2122X`，固件 `2.01.01.39R7T2`。
- 示波器：`RTM2032`，固件 `06.010`。
- 接线：SDG CH1 → RTM CH1，SDG CH2 → RTM CH2。
- 资源与序列号：仅保存在本地会话中，未写入公开文档。
- 访问策略：信号发生器和示波器均为 `read_only`。

## 首次差异与修正

首次 `C1:OUTP?` 返回：

```text
C1:OUTP OFF,LOAD,HZ,POWERON_STATE,OFF,PLRT,NOR
```

E05C 编程手册的 Output Command 响应只列出输出状态、`LOAD` 与 `PLRT`，未登记 `POWERON_STATE`。初版解析器因此按设计失败关闭，没有继续读取或猜测该字段。

实机修正只接受可验证的 `POWERON_STATE,ON|OFF`，同时仍强制要求 `LOAD` 与 `PLRT`。未知值、重复字段和其它未知字段继续抛出 `DataError`。该字段只参与响应校验，不作为不存在于核心 `SourceStatus` 的伪造字段对外返回。

## 信号发生器结果

修正后的持久会话执行一次 `*IDN?`，随后对 CH1 与 CH2 各执行三轮 `OUTP?`、`BSWV?` 和 `SWWV?`。三轮结果一致：

| 字段 | CH1 | CH2 |
| --- | --- | --- |
| 输出 | `OFF` | `OFF` |
| 波形 | `SIN` | `SIN` |
| 频率 | 1 kHz | 1 kHz |
| 幅度 | 4 Vpp | 4 Vpp |
| 偏置 | 0 V | 0 V |
| 相位 | 0° | 0° |
| 频率模式 | `FIX` | `FIX` |
| Sweep | `OFF` | `OFF` |

WaveBench transport 审计结果：

| 计数器 | 结果 |
| --- | ---: |
| Query | 19 |
| Write request | 0 |
| Write transmitted | 0 |
| Binary write transmitted | 0 |
| Instrument mutation write | 0 |

## 示波器只读交叉检查

RTM2032 通过 WaveBench `scope.snapshot` 分别读取 CH1 与 CH2，并读取一次 acquisition status。两路均为已启用、`DCL` 高阻耦合、2 V/div、无过载；波形 metadata 均为 10,000 点与 500 ns X 步长。状态字、questionable condition 和错误队列非空标志均为 0 或 false。

该示波器会话共执行 108 次查询，写请求与仪器状态修改写入均为 0。

## 未通过或未执行的部分

- 两路信号源输出当时均为 OFF，因此未执行波形幅度、频率或相位的物理交叉验收。
- 未发送输出开启、波形配置、Sweep、Burst、trigger、`*RST` 或错误队列查询。
- 未调用会改变 RTM2032 传输格式、采集状态或通道设置的 `scope fetch`、`scope capture`、autoscale 或 screenshot。
- 未声明 `source.errors`、`source.channel_profile` 或任何写 capability。

## 后续门禁

物理信号路径验收需要先取得显式的输出开启授权，或由操作人员在前面板确认两路输出已开启。随后才能使用 WaveBench 的受控示波器采集路径比较设定频率、Vpp、偏置与实际波形。该阶段不得自动扩张为 M3 写 capability 验收。
