# Plugin packages

[English](README_EN.md)

该目录用于放置独立的 WaveBench 仪器插件源码包。当前正式包包括五个预装驱动的可选外置发行版、M3 query-only 的 `wavebench-shengpu-sp3000a`、已完成 Source V2 C3 候选审计的 `wavebench-siglent-sdg2000x`、已采用 WaveBench `0.8.24` transport/session P0 的 `wavebench-siglent-sds3000`、已完成 SDS804X HD 波形、PNG 截图和独立采集控制验收的 `wavebench-siglent-sds800x-hd` `0.6.0`，以及面向 MSO8104 的 `wavebench-rigol-mso8000` `0.9.0`。后者已完成有界 waveform/capture、截图 V2、采集控制和光标读数的受控验收。后续仍按仪器或紧密相关系列逐包维护，不以移除预装驱动为目标，也不在这里冻结第二套 manifest、安装器或 catalog 协议。

`wavebench-rigol-dsg830` `0.2.0` 已进入仓库开发环境，完成 `rf_source` M0 与 A1 只读快照证据，并要求 Core `>=0.8.25,<0.9`；production descriptor 声明 `rf_source.idn` 和 `rf_source.snapshot`，RF 控制仍由 A2–A5 分别门控。

这些包分别声明各自的 WaveBench `0.8.x` 最低版本；SDS800X HD `0.6.0` 要求 `wavebench>=0.8.23,<0.9`，SDG2000X `0.8.2`、SDS3000 与 MSO8000 要求 `wavebench>=0.8.24,<0.9`。MSO8000 依赖的当前 Core API 尚未独立发布，不能据此宣称兼容性 wheel 已发布。它们不能与 `v0.7.0` 配套运行，也不会把未来 `0.9` 自动视为兼容版本。

每个正式包至少应具备：

- 独立的 `pyproject.toml` 与版本；
- `wavebench.instruments` entry point；
- canonical driver ID 和明确的 WaveBench 兼容范围；
- 不访问真实仪器的单元测试；
- 中英双语的用户可见说明；
- 独立可打包的 MIT 许可证文件和 SPDX 包元数据；
- 不含真实设备资源、凭据、原始波形或私有实验记录。

## 新增仪器系列

- [`wavebench-rigol-mso8000`](wavebench-rigol-mso8000/README.md)：RIGOL MSO8104 混合信号示波器，canonical ID `rigol.mso8104`；有界 waveform/capture、截图 V2、采集控制、状态和光标读数已在记录的型号、固件与 LAN/PyVISA 条件下完成受控验收。
- [`wavebench-rigol-dsg830`](wavebench-rigol-dsg830/README.md)：RIGOL DSG830 射频信号发生器，canonical ID `rigol.dsg830`；`0.2.0` 完成 `rf_source` M0 与 A1 只读快照证据，production descriptor 声明 `rf_source.idn` 和 `rf_source.snapshot`。A2–A5 门槛见包内[里程碑](wavebench-rigol-dsg830/doc/DSG830_COVERAGE_MILESTONES.md)。
- [`wavebench-shengpu-sp3000a`](wavebench-shengpu-sp3000a/README.md)：Shengpu SP30120 扫频仪插件，保留最小 query-only descriptor 和经认证的 RF-OFF 控制。
- [`wavebench-siglent-sds3000`](wavebench-siglent-sds3000/README.md)：早期 SIGLENT SDS3000 系列插件，当前严格支持 SDS3054 固件 `8.4.1`；身份、错误寄存器、通道耦合、波形读取和单/双通道采集已实现。
- [`wavebench-siglent-sdg2000x`](wavebench-siglent-sdg2000x/README.md)：SIGLENT SDG2000X 函数／任意波形发生器，已完成 Source V2 候选包审计。
- [`wavebench-siglent-sds800x-hd`](wavebench-siglent-sds800x-hd/README.md)：SIGLENT SDS800X HD 系列示波器，已完成波形、PNG 截图和独立采集控制验收。

这些包均提供独立 `pyproject.toml` 和唯一 entry point，进入仓库级开发环境。尚未完成的 capability 不会提前声明。
