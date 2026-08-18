# SDS3000 编程手册基线

[English](MANUAL_BASELINE_EN.md)

## 结论

当前资料是 Teledyne LeCroy 于 2026 年 2 月发布的《Oscilloscopes Remote Control and Automation Manual》。它覆盖 MAUI/XStreamDSO 的远程控制体系，但不是 SDS3054 专属手册。目标实机固件为 `8.4.1`，手册部分内容以 `8.5.0.0+` 或更高版本为前提，因此「手册有记录」不能直接等同于「实机已支持」。

本项目将手册明确列出的实体作为完整性分母，再通过离线协议证据和分级实机测试判断固件 `8.4.1` 的实际支持状态。

机器可读记录见 [`manual-baseline.json`](manual-baseline.json)。

## 来源与分段

上传转换系统将一份 411 页源手册拆成三个 PDF。下表的页码是源 PDF 的顺序页，不是正文印刷页码。

| 段 | 源 PDF 顺序页 | 页数 | 字节数 | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `segment-001` | 1–200 | 200 | 2,588,943 | `1a035e879600ee75d1d381c1fe8e5c2bcffc09d3fbc0fa02d4db46d82d04af53` |
| `segment-002` | 201–400 | 200 | 914,888 | `bb316a51ccd76ff58f4aa6ecab68da6ef993086cfd605b6fdd7395501379edeb` |
| `segment-003` | 401–411 | 11 | 125,917 | `39dac5d034da11fe3df2d7d13a0ffd2edb48e8c05efda2ee023f1cd93dcda55f` |

分段边界已通过正文连续性复核：

- 第一段从封面开始，结束于印刷页 `6-32`；
- 第二段从印刷页 `6-33` 开始，结束于印刷页 `7-198`；
- 第三段从印刷页 `7-199` 开始，结束于印刷页 `7-208`，随后为空白尾页。

三个 PDF 均由上传系统使用 PDFium 重新生成。其文件创建时间属于转换元数据，不能当作文档发布日期或修订号。

## 设备适用边界

| 项目 | 冻结值 |
| --- | --- |
| 物理品牌 | SIGLENT |
| 机身型号 | SDS3054 |
| 脱敏远程身份 | `LECROY,SDS3054,<serial>,8.4.1` |
| 协议平台 | Teledyne LeCroy MAUI/XStreamDSO |
| 首版支持范围 | 仅 SDS3054 |

手册正文明确提示，部分单位、脚本和接口只适用于较新的 XStreamDSO 版本。所有未在 SDS3054 固件 `8.4.1` 上取得证据的实体先标记为 `firmware-unverified`；型号、选件或平台明显不适用的实体分别标记为 `model-not-applicable` 或 `option-absent`。

## 完整性分母

M1 审计采用以下边界：

1. Part 7「Commands and Queries by Short Form」表中的 164 行 legacy/IEEE 488.2 命令；
2. Part 4 明确记录的 Automation 对象、Action、Method 和 CVAR；
3. Part 5 明确记录的 Result Interface 属性；
4. 手册明确说明但没有逐项列出的其他 CVAR 不计入分母。

每个实体必须具有唯一稳定 ID、手册位置、读写方向、参数或响应、版本与选件条件、副作用、安全等级、WaveBench 映射和处置状态。M1 验收要求总数可重现、无重复稳定 ID、无未分类实体。

## 状态与安全等级

覆盖矩阵使用以下处置状态：

- `implemented`：已通过离线测试，并在需要时通过安全实机测试；
- `planned`：WaveBench 现有接口可表达，尚未完成实现；
- `core-gap-rfc`：需要可被至少两个独立仪器系列复用的 WaveBench 核心接口；
- `firmware-unverified`：手册版本晚于实机，尚未确认固件 `8.4.1` 支持；
- `option-absent`：需要当前设备未确认或未安装的选件；
- `model-not-applicable`：面向其他型号或产品族；
- `unsafe-quarantined`：可能重置、校准、写文件、改网络、关机或执行任意脚本，禁止自动实机测试。

任何状态都不得通过暴露任意 SCPI 或 VBS 执行接口来「完成覆盖」。覆盖的含义是逐项审计和明确处置，不是把手册变成字符串转发器。

## 复核命令

在厂商资料仍位于 `doc/vendor-local/` 时，可使用以下只读命令复核基线：

```bash
find doc/vendor-local -type f -name '*_origin.pdf' -print0 \
  | sort -z \
  | xargs -0 sha256sum

find doc/vendor-local -type f -name '*_origin.pdf' -print0 \
  | sort -z \
  | xargs -0 -n1 pdfinfo
```

厂商资料、转换图片和全文 Markdown 均由仓库级 `.gitignore` 排除，不进入 Git、wheel 或 sdist。
