# WaveBench 插件目录

[English](plugin-catalog-en.md)

本 Reference 由各包的 `pyproject.toml` 和 production descriptor 生成。运行
`python scripts/generate_plugin_catalog.py` 更新，运行
`python scripts/generate_plugin_catalog.py --check` 检查漂移。

> 元数据版本表示本仓库内的包源码合同，不代表 PyPI、Git tag 或 GitHub Release 状态。
> capability 列表只表示 descriptor 顶层声明；型号、固件、选件和 profile 限制仍以包级
> Reference 与运行时 capability 查询为准。

## 包与入口点

| 包 | 元数据版本 | Driver ID | 类型 | 型号 | Python | WaveBench |
| --- | --- | --- | --- | --- | --- | --- |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README.md) | `0.7.0` | `rigol.dg4202` | 信号源 | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README.md) | `0.7.0` | `rigol.dg4202-v2` | 信号源 | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README.md) | `0.7.0` | `rigol.dg4202-v2-workspace` | 信号源 | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dm3000`](../../packages/wavebench-rigol-dm3000/README.md) | `0.5.0` | `rigol.dm3000` | 数字万用表 | DM3000, DM3058 | `>=3.11` | `wavebench>=0.8.11,<0.9` |
| [`wavebench-rigol-dp800`](../../packages/wavebench-rigol-dp800/README.md) | `0.3.0` | `rigol.dp800` | 直流电源 | DP800, DP832, DP832A | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-rigol-ds1000z`](../../packages/wavebench-rigol-ds1000z/README.md) | `0.1.0` | `rigol.ds1000z` | 示波器 | DS1104Z, DS1104Z Plus, DS1104Z-S Plus, DS1000Z | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-rigol-dsg830`](../../packages/wavebench-rigol-dsg830/README.md) | `0.2.0` | `rigol.dsg830` | 射频信号源 | DSG830 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-mso8000`](../../packages/wavebench-rigol-mso8000/README.md) | `0.9.0` | `rigol.mso8104` | 示波器 | MSO8104 | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-rohde-schwarz-rtm2000`](../../packages/wavebench-rohde-schwarz-rtm2000/README.md) | `0.15.0` | `rohde-schwarz.rtm2032` | 示波器 | RTM2032, RTM2000 | `>=3.11` | `wavebench>=0.8.26,<0.9` |
| [`wavebench-shengpu-sp3000a`](../../packages/wavebench-shengpu-sp3000a/README.md) | `0.2.0` | `shengpu.sp30120` | 扫频仪 | SP30120 | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-siglent-sdg2000x`](../../packages/wavebench-siglent-sdg2000x/README.md) | `0.8.2` | `siglent.sdg2000x` | 信号源 | SDG2042X, SDG2082X, SDG2122X | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-siglent-sds3000`](../../packages/wavebench-siglent-sds3000/README.md) | `0.1.0` | `siglent.sds3000` | 示波器 | SDS3054 | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-siglent-sds800x-hd`](../../packages/wavebench-siglent-sds800x-hd/README.md) | `0.6.0` | `siglent.sds800x-hd` | 示波器 | SDS802X HD, SDS804X HD, SDS812X HD, SDS814X HD, SDS822X HD, SDS824X HD | `>=3.11` | `wavebench>=0.8.23,<0.9` |

## 已声明 capability

### `rigol.dg4202`

- 显示名称：RIGOL DG4000 Function/Arbitrary Waveform Generator
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `source.snapshot_v2`
  - `source.basic_configure_v2`
  - `source.basic_live_configure_v2`
  - `source.output_v2`
  - `source.counter_configure_v2`
  - `source.counter_enable_v2`
  - `source.counter_measure_v2`
  - `source.idn`
  - `source.errors`
  - `source.status`
  - `source.channel_profile`
  - `source.sweep_profile`
  - `source.counter_profile`
  - `source.set_frequency`
  - `source.set_function`
  - `source.set_amplitude_vpp`
  - `source.set_square_duty_cycle`
  - `source.output`
  - `source.arbitrary_probe`
  - `source.arbitrary_upload`

### `rigol.dg4202-v2`

- 显示名称：RIGOL DG4000 Source V2 Advanced (opt-in)
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `source.snapshot_v2`
  - `source.basic_configure_v2`
  - `source.basic_live_configure_v2`
  - `source.output_v2`
  - `source.counter_configure_v2`
  - `source.counter_enable_v2`
  - `source.counter_measure_v2`
  - `source.idn`
  - `source.errors`
  - `source.status`
  - `source.channel_profile`
  - `source.sweep_profile`
  - `source.counter_profile`
  - `source.set_frequency`
  - `source.set_function`
  - `source.set_amplitude_vpp`
  - `source.set_square_duty_cycle`
  - `source.output`
  - `source.arbitrary_probe`
  - `source.sweep_configure_v2`
  - `source.sweep_fire_v2`

### `rigol.dg4202-v2-workspace`

- 显示名称：RIGOL DG4000 Source V2 Volatile Workspace (opt-in)
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `source.idn`
  - `source.snapshot_v2`
  - `source.output_v2`
  - `source.arbitrary_workspace_volatile_replace_v2`

### `rigol.dm3000`

- 显示名称：RIGOL DM3000/DM3058 Digital Multimeter
- Backend：`pyvisa`
- Resource scheme：`tcpip`
- Capabilities:

  - `dmm.idn`
  - `dmm.read`
  - `dmm.function_status`
  - `dmm.set_function`
  - `dmm.measurement_profile`
  - `dmm.trigger_status`
  - `dmm.calculation_status`
  - `dmm.calculation_statistics`
  - `dmm.system_interface_status`
  - `dmm.set_voltage_range`
  - `dmm.set_dcv_impedance`

### `rigol.dp800`

- 显示名称：RIGOL DP800 Power Supply
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `power.idn`
  - `power.status`
  - `power.measurement`
  - `power.set_voltage_current_limit`
  - `power.output`
  - `power.protection`

### `rigol.ds1000z`

- 显示名称：RIGOL DS1000Z Oscilloscope
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `scope.idn`
  - `scope.errors`
  - `scope.autoscale`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`
  - `scope.screenshot`
  - `scope.channel_coupling`

### `rigol.dsg830`

- 显示名称：RIGOL DSG830 RF Signal Generator
- Backend：`pyvisa`
- Resource scheme：`tcpip`, `usb`
- Capabilities:

  - `rf_source.idn`
  - `rf_source.snapshot`
  - `rf_source.cw_configure`
  - `rf_source.output`
  - `rf_source.modulation_configure`
  - `rf_source.modulation_disable`
  - `rf_source.modulated_output_enable`
  - `rf_source.pulse_configure`
  - `rf_source.pulse_output`
  - `rf_source.sweep_configure`

### `rigol.mso8104`

- 显示名称：RIGOL MSO8104 Oscilloscope
- Backend：`pyvisa`
- Resource scheme：`tcpip`, `usb`, `gpib`
- Capabilities:

  - `scope.idn`
  - `scope.error_drain_v1`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`
  - `scope.channel_coupling`
  - `scope.channel_input_state_v2`
  - `scope.autoscale`
  - `scope.screenshot_profile`
  - `scope.screenshot_v2`
  - `scope.math_metadata`
  - `scope.measurement_statistics_v2`
  - `scope.fft_status_v2`
  - `scope.acquisition_status_v2`
  - `scope.acquisition_run_state`
  - `scope.acquisition_control`
  - `scope.digital_status_v2`
  - `scope.snapshot_v2`
  - `scope.cursor_readout`
  - `scope.cursor_readout_v2`

### `rohde-schwarz.rtm2032`

- 显示名称：Rohde & Schwarz RTM2032 Oscilloscope
- Backend：`rsinstrument-socket`, `rsinstrument`, `rsinstrument-rsvisa`, `rsinstrument-pyvisa-py`
- Resource scheme：`tcpip`
- Capabilities:

  - `scope.idn`
  - `scope.errors`
  - `scope.autoscale`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`
  - `scope.screenshot`
  - `scope.channel_coupling`
  - `scope.snapshot`
  - `scope.acquisition_status`
  - `scope.capture_average`
  - `scope.digital_status`
  - `scope.digital_waveform`
  - `scope.history_timestamps`
  - `scope.measurement_statistics`
  - `scope.math_metadata`
  - `scope.fft_status`
  - `scope.reference_metadata`
  - `scope.cursor_readout`
  - `scope.channel_input_state_v2`
  - `scope.digital_status_v2`
  - `scope.snapshot_v2`
  - `scope.measurement_statistics_v2`
  - `scope.fft_status_v2`
  - `scope.channel_display_configure_v2`
  - `scope.focus_configure_v2`

### `shengpu.sp30120`

- 显示名称：Shengpu SP30120 Digital Sweep Analyzer
- Backend：`serial`
- Resource scheme：—
- Capabilities:

  - `sweep_analyzer.idn`

### `siglent.sdg2000x`

- 显示名称：SIGLENT SDG2000X Function/Arbitrary Waveform Generator
- Backend：`pyvisa`
- Resource scheme：—
- Capabilities:

  - `source.idn`
  - `source.status`
  - `source.set_frequency`
  - `source.set_function`
  - `source.set_amplitude_vpp`
  - `source.set_square_duty_cycle`
  - `source.output`
  - `source.arbitrary_probe`
  - `source.snapshot_v2`
  - `source.basic_configure_v2`
  - `source.output_v2`
  - `source.harmonics_disable_v2`

### `siglent.sds3000`

- 显示名称：SIGLENT SDS3054 Oscilloscope
- Backend：`pyvisa`
- Resource scheme：`vicp`, `tcpip`
- Capabilities:

  - `scope.idn`
  - `scope.errors`
  - `scope.channel_coupling`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`

### `siglent.sds800x-hd`

- 显示名称：SIGLENT SDS800X HD Oscilloscope
- Backend：`pyvisa`
- Resource scheme：`tcpip`, `usb`
- Capabilities:

  - `scope.idn`
  - `scope.channel_coupling`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`
  - `scope.measurement_statistics`
  - `scope.screenshot_profile`
  - `scope.screenshot_v2`
  - `scope.acquisition_run_state`
  - `scope.acquisition_control`
