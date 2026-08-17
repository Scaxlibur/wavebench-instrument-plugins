# 本地厂商资料 / Local vendor material

本目录已登记《SDS 系列数字示波器编程手册》`CN11G`。手册转换因工具限制可拆为多个
目录；当前审计输入为三个转换目录中的 `full.md`。原始 PDF 或后续转换结果仍可使用以下
基础文件名：

```text
SDS800XHD_Series_ProgrammingGuide.pdf
```

The registered source is revision `CN11G` of the SDS Series Digital Oscilloscope Programming
Guide. Converter limits may split it across multiple directories; the current audit uses three
converted `full.md` files. Original PDFs and future conversions may retain the base filename above.

官方资料入口 / Official source:

- [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/)
- [SDS800X HD 产品页 / Product page](https://www.siglent.com/int/products-overview/sds800x-hd/)

除本说明外，本目录内容由仓库级 `.gitignore` 排除，并由 package 的 sdist 规则排除。不要强制加入 Git，也不要在厂商资料中混入真实设备地址、序列号、凭据或实验日志。

All files in this directory except this README are excluded by the repository-level `.gitignore`
and by the package sdist configuration. Do not force-add them, and do not mix real resources,
serial numbers, credentials, or laboratory logs into vendor material.

项目原创的审计结论见
[`SDS800X_HD_COVERAGE_MATRIX.md`](../SDS800X_HD_COVERAGE_MATRIX.md)。厂商手册的支持表将
SDS800X HD 最低固件列为 `1.1.3.1`；该版本下限不代表每条通用 SDS 命令均已在本系列
实机验证。

Project-authored audit conclusions are recorded in
[`SDS800X_HD_COVERAGE_MATRIX_EN.md`](../SDS800X_HD_COVERAGE_MATRIX_EN.md). The manual support
table lists `1.1.3.1` as the minimum SDS800X HD firmware; that minimum does not establish that
every shared SDS command has been verified on this family.
