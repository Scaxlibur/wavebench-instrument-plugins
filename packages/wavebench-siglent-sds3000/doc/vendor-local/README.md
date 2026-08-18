# 本地厂商资料 / Local vendor material

本目录用于放置早期 SIGLENT SDS3000 系列采用的 Teledyne LeCroy MAUI/X-Stream 编程资料。目标仪器为 SIGLENT SDS3054，远程身份格式为 `LECROY,SDS3054,<serial>,8.4.1`；不要放入 SDS3000X 或 SDS3000X HD 的 SCPI 手册。

当前已放入 2026 年 2 月版《Oscilloscopes Remote Control and Automation Manual》的本地转换结果。上传转换系统将原始 411 页手册拆为 200、200、11 页三段；不要改动三段内容或顺序。推荐保留原始文件名；需要统一命名时，可使用：

```text
Oscilloscopes_Remote_Control_and_Automation_Manual_2026-02.pdf
```

The local conversion of the February 2026 *Oscilloscopes Remote Control and Automation Manual* is present. The upload converter split the 411-page source into segments of 200, 200, and 11 pages; do not modify their content or order. The target is the early SIGLENT SDS3054 reporting `LECROY,SDS3054,<serial>,8.4.1`; do not place SDS3000X or SDS3000X HD SCPI manuals in this directory.

型号操作手册、数据表、固件发行说明和当前官方滚动版 MAUI 手册可以作为补充资料。手册放入后，应在项目原创文档中登记标题、文档号、修订号、发布日期、适用平台和文件 SHA-256。不要直接改写厂商原件。

Model operator manuals, datasheets, firmware release notes, and the current rolling MAUI manual may be added as supplementary material. After adding a document, record its title, document number, revision, publication date, applicable platform, and SHA-256 in project-authored documentation. Do not modify vendor originals in place.

除本说明外，本目录内容由仓库级 `.gitignore` 排除。不要强制加入 Git，也不要在厂商资料中混入真实设备地址、序列号、凭据、波形、截图或实验日志。

All files in this directory except this README are excluded by the repository-level `.gitignore`. Do not force-add them, and do not mix real resources, serial numbers, credentials, waveforms, screenshots, or laboratory logs into vendor material.
