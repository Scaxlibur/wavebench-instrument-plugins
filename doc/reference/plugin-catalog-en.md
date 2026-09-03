# WaveBench plugin catalog

[中文](plugin-catalog.md)

This Reference is generated from each package's `pyproject.toml` and production descriptor.
Regenerate it with `python scripts/generate_plugin_catalog.py`; verify drift with
`python scripts/generate_plugin_catalog.py --check`.

> A metadata version identifies the package source contract in this repository; it is not a
> PyPI, Git tag, or GitHub Release claim. Declared capabilities are top-level descriptor
> entries. Model, firmware, option, and profile restrictions remain in the package Reference
> and the runtime capability query.

## Packages and entry points

| Package | Metadata version | Driver ID | Type | Models | Python | WaveBench |
| --- | --- | --- | --- | --- | --- | --- |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README_EN.md) | `0.7.0` | `rigol.dg4202` | source | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README_EN.md) | `0.7.0` | `rigol.dg4202-v2` | source | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dg4000`](../../packages/wavebench-rigol-dg4000/README_EN.md) | `0.7.0` | `rigol.dg4202-v2-workspace` | source | DG4202, DG4000 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-dm3000`](../../packages/wavebench-rigol-dm3000/README_EN.md) | `0.5.0` | `rigol.dm3000` | dmm | DM3000, DM3058 | `>=3.11` | `wavebench>=0.8.11,<0.9` |
| [`wavebench-rigol-dp800`](../../packages/wavebench-rigol-dp800/README_EN.md) | `0.3.0` | `rigol.dp800` | power | DP800, DP832, DP832A | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-rigol-ds1000z`](../../packages/wavebench-rigol-ds1000z/README_EN.md) | `0.1.0` | `rigol.ds1000z` | scope | DS1104Z, DS1104Z Plus, DS1104Z-S Plus, DS1000Z | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-rigol-dsg830`](../../packages/wavebench-rigol-dsg830/README_EN.md) | `0.2.0` | `rigol.dsg830` | rf_source | DSG830 | `>=3.11` | `wavebench>=0.8.25,<0.9` |
| [`wavebench-rigol-mso8000`](../../packages/wavebench-rigol-mso8000/README_EN.md) | `0.9.0` | `rigol.mso8104` | scope | MSO8104 | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-rohde-schwarz-rtm2000`](../../packages/wavebench-rohde-schwarz-rtm2000/README_EN.md) | `0.15.0` | `rohde-schwarz.rtm2032` | scope | RTM2032, RTM2000 | `>=3.11` | `wavebench>=0.8.26,<0.9` |
| [`wavebench-shengpu-sp3000a`](../../packages/wavebench-shengpu-sp3000a/README_EN.md) | `0.2.0` | `shengpu.sp30120` | sweep_analyzer | SP30120 | `>=3.11` | `wavebench>=0.8,<0.9` |
| [`wavebench-siglent-sdg2000x`](../../packages/wavebench-siglent-sdg2000x/README_EN.md) | `0.8.2` | `siglent.sdg2000x` | source | SDG2042X, SDG2082X, SDG2122X | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-siglent-sds3000`](../../packages/wavebench-siglent-sds3000/README_EN.md) | `0.1.0` | `siglent.sds3000` | scope | SDS3054 | `>=3.11` | `wavebench>=0.8.24,<0.9` |
| [`wavebench-siglent-sds800x-hd`](../../packages/wavebench-siglent-sds800x-hd/README_EN.md) | `0.6.0` | `siglent.sds800x-hd` | scope | SDS802X HD, SDS804X HD, SDS812X HD, SDS814X HD, SDS822X HD, SDS824X HD | `>=3.11` | `wavebench>=0.8.23,<0.9` |

## Declared capabilities

### `rigol.dg4202`

- Display name: RIGOL DG4000 Function/Arbitrary Waveform Generator
- Backends: `pyvisa`
- Resource schemes: —
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

- Display name: RIGOL DG4000 Source V2 Advanced (opt-in)
- Backends: `pyvisa`
- Resource schemes: —
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

- Display name: RIGOL DG4000 Source V2 Volatile Workspace (opt-in)
- Backends: `pyvisa`
- Resource schemes: —
- Capabilities:

  - `source.idn`
  - `source.snapshot_v2`
  - `source.output_v2`
  - `source.arbitrary_workspace_volatile_replace_v2`

### `rigol.dm3000`

- Display name: RIGOL DM3000/DM3058 Digital Multimeter
- Backends: `pyvisa`
- Resource schemes: `tcpip`
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

- Display name: RIGOL DP800 Power Supply
- Backends: `pyvisa`
- Resource schemes: —
- Capabilities:

  - `power.idn`
  - `power.status`
  - `power.measurement`
  - `power.set_voltage_current_limit`
  - `power.output`
  - `power.protection`

### `rigol.ds1000z`

- Display name: RIGOL DS1000Z Oscilloscope
- Backends: `pyvisa`
- Resource schemes: —
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

- Display name: RIGOL DSG830 RF Signal Generator
- Backends: `pyvisa`
- Resource schemes: `tcpip`, `usb`
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

- Display name: RIGOL MSO8104 Oscilloscope
- Backends: `pyvisa`
- Resource schemes: `tcpip`, `usb`, `gpib`
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

- Display name: Rohde & Schwarz RTM2032 Oscilloscope
- Backends: `rsinstrument-socket`, `rsinstrument`, `rsinstrument-rsvisa`, `rsinstrument-pyvisa-py`
- Resource schemes: `tcpip`
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

- Display name: Shengpu SP30120 Digital Sweep Analyzer
- Backends: `serial`
- Resource schemes: —
- Capabilities:

  - `sweep_analyzer.idn`

### `siglent.sdg2000x`

- Display name: SIGLENT SDG2000X Function/Arbitrary Waveform Generator
- Backends: `pyvisa`
- Resource schemes: —
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

- Display name: SIGLENT SDS3054 Oscilloscope
- Backends: `pyvisa`
- Resource schemes: `vicp`, `tcpip`
- Capabilities:

  - `scope.idn`
  - `scope.errors`
  - `scope.channel_coupling`
  - `scope.fetch_waveform`
  - `scope.capture_waveform`
  - `scope.capture_waveforms`

### `siglent.sds800x-hd`

- Display name: SIGLENT SDS800X HD Oscilloscope
- Backends: `pyvisa`
- Resource schemes: `tcpip`, `usb`
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
