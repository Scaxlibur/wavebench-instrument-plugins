# 本地厂商资料 / Local vendor material

将 Rohde & Schwarz RTM2000 系列示波器编程手册的原始文件放在本目录。推荐文件名：

```text
RTM2000_programming_manual.pdf
```

也可以保留厂商发布的原始文件名。若同时保存多个版本，请在文件名中保留手册版本号或发布日期，避免覆盖旧版。

Place the original Rohde & Schwarz RTM2000-series oscilloscope programming manual in this directory. The recommended filename is shown above, but the vendor's original filename may also be retained. If multiple revisions are stored, keep the revision or publication date in each filename.

除本说明外，本目录内容由仓库级 `.gitignore` 排除，并由 RTM2000 包的 sdist 构建规则排除。请勿强制加入 Git，也不要在厂商资料中混入真实仪器地址、序列号、凭据、波形、截图或实验日志。

All files in this directory except this README are excluded by the repository-level `.gitignore` and by the RTM2000 package's sdist build rules. Do not force-add them, and do not mix real instrument addresses, serial numbers, credentials, waveforms, screenshots, or laboratory logs into vendor material.
