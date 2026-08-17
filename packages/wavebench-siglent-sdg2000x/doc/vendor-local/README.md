# 本地厂商资料 / Local vendor material

将 SIGLENT SDG 系列编程手册原文件放在本目录。推荐文件名：

```text
SDG_Series_Programming_Guide_E05C.pdf
```

如需同时保留 SDG2000X 用户手册，推荐使用：

```text
SDG2000X_User_Manual_EN03A.pdf
```

版本号应保留在文件名中，避免新手册覆盖旧版。当前公开下载入口见 [SIGLENT SDG2000X 产品页](https://www.siglent.com/in/products-overview/sdg2000x/)。

Place the original SIGLENT SDG Series Programming Guide in this directory. The recommended filename is shown above. Keep the revision in each filename so that a newer manual does not overwrite an older revision. The SDG2000X user manual may be stored here as supporting material.

除本说明外，本目录内容由仓库级 `.gitignore` 排除，并由本包的 sdist 构建规则排除。不要强制加入 Git，也不要在厂商资料中混入真实仪器地址、序列号、凭据、波形、截图或实验日志。

All files in this directory except this README are excluded by the repository-level `.gitignore`; the complete directory is excluded from the package sdist. Do not force-add vendor files, and do not mix real instrument addresses, serial numbers, credentials, waveforms, screenshots, or laboratory logs into this directory.
