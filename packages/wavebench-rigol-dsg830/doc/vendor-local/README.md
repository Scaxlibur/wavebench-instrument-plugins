# 本地厂商资料 / Local vendor material

请将普源 DSG800 系列编程手册原文件放在本目录。推荐文件名：

```text
DSG800_ProgrammingGuide_EN.pdf
DSG800_ProgrammingGuide_EN.md
```

原文为普源官方 [DSG800 ProgrammingGuide V1.0](https://www.rigol.com/intl/dam/global/downloads/brochures/en/program-guide/rf-signal-generators/DSG800_ProgrammingGuide_EN.pdf)。
官网条目记录版本 `V1.0`、日期 `2019-09-30`；手册说明该系列包含 DSG830 和 DSG815，并默认以
DSG830 介绍命令。PDF 是原始对照文件，Markdown 是后续检索和审计使用的转换稿。若保存不同语言、版本或
日期的资料，请在文件名中保留该信息，避免相互覆盖。

除本说明外，本目录内容由仓库级 `.gitignore` 排除，并由本包的 sdist 构建规则排除。不要强制加入 Git，也
不要在厂商资料中混入真实仪器地址、序列号、凭据、波形、截图或实验日志。

Place the original RIGOL DSG800 programming guide and an optional converted Markdown copy in this directory.
The official source and recommended filenames are shown above. Keep language, revision, or date information in
filenames when storing multiple editions. All files except this README are ignored by Git and the complete
directory is excluded from the package sdist. Do not force-add vendor material or place real-device data here.
