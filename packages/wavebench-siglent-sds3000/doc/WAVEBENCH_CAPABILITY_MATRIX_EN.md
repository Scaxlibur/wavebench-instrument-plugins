# SDS3000 WaveBench Capability Matrix

[中文](WAVEBENCH_CAPABILITY_MATRIX.md)

## Conclusion

This matrix covers all 26 `scope` capabilities in WaveBench `0.8.24`. The plugin implements and declares six. Each of the remaining 20 has an explicit disposition. No capability outside WaveBench is invented, and neither raw SCPI nor arbitrary VBS is exposed to bypass the capability boundary.

The machine-readable source of truth is [`wavebench-capability-matrix.json`](wavebench-capability-matrix.json). Tests compare its 26 entries with WaveBench `CAPABILITY_METHODS` and require every manual anchor to exist in [`command-catalog.json`](command-catalog.json).

Disposition meanings:

- `implemented`: code and offline tests exist, and the descriptor declares the capability; hardware evidence is tracked separately.
- `firmware-unverified`: the manual provides a candidate path, but SDS3054 firmware `8.4.1` has not been shown to satisfy the complete capability contract.
- `option-unconfirmed`: required hardware, probe, or licensed option has not been confirmed.
- `core-gap-rfc`: the instrument can provide some information, but the current WaveBench model requires fields that cannot be filled honestly; only a cross-vendor RFC is proposed.
- `contract-incompatible`: WaveBench has an optional contract, but this device cannot satisfy it honestly. The existing capability that accurately represents the device remains in place.
- `unsafe-quarantined`: the candidate path depends on external hardcopy, instrument files, or another path without safe restoration.

## All 26 capabilities

| Capability | Disposition | Evidence | Current boundary |
| --- | --- | --- | --- |
| `scope.idn` | `implemented` | Hardware accepted | Strictly accepts SDS3054 firmware `8.4.1`, including the optional `*IDN ` header returned by the device. |
| `scope.errors` | `implemented` | Offline tested | Reads `CMR?`, `EXR?`, and `DDR?`; all three clear state and are not represented as side-effect-free health queries. |
| `scope.autoscale` | `firmware-unverified` | Manual only | `ASET` changes vertical, timebase, and trigger settings together; it is not declared before firmware and restoration boundaries are accepted. |
| `scope.fetch_waveform` | `implemented` | CH1/CH2 hardware accepted | Uses existing `query_bin_block()` and snapshots then restores `CHDR/CFMT/CORD/WFSU` in reverse order. |
| `scope.capture_waveform` | `implemented` | Hardware accepted | Uses `STOP → ARM → WAIT → *OPC?`, then requires `TRMD STOP` and restores all modified state. |
| `scope.capture_waveforms` | `implemented` | Hardware accepted | Reads every requested channel after one acquisition and never retriggers per channel; three 1 Vpp, 1 kHz rounds passed. |
| `scope.screenshot` | `unsafe-quarantined` | Manual contract review | `SCDP` sends the image to the current hardcopy device, while `SCDP?` returns status rather than PNG bytes. The plugin does not route around this through instrument files or arbitrary VBS. |
| `scope.channel_coupling` | `implemented` | Hardware accepted | Maps `D1M/A1M/D50/GND` to existing WaveBench coupling semantics and fails closed on `OVL`. |
| `scope.snapshot` | `core-gap-rfc` | Manual and core-model review | `ScopeSnapshot` requires complete health, probe, waveform, and edge-trigger fields that SDS3054 cannot fill honestly in one read-only transaction. |
| `scope.acquisition_status` | `core-gap-rfc` | Manual and core-model review | The current model requires average and segmented-option state; `IsTriggerReady`, `TRMD`, and `SEQ` expose only a subset. |
| `scope.capture_average` | `firmware-unverified` | Manual only | `ClearSweeps` is not a complete average-capture protocol; mode, completion, and restoration fields are unverified. |
| `scope.digital_status` | `option-unconfirmed` | Manual only | A digital connector is present, but the probe, license, and firmware Automation path are unconfirmed. |
| `scope.digital_waveform` | `option-unconfirmed` | Manual only | The Result Interface documents digital arrays, but that does not prove the option is installed or safe to read on this device. |
| `scope.history_timestamps` | `firmware-unverified` | Manual only | `SEQ`, History objects, and result time properties exist; the per-segment table and firmware byte layout are unverified. |
| `scope.measurement_statistics` | `firmware-unverified` | Manual only | `PAST?` and result statistics exist; configured-slot confirmation, parsing, and consumption semantics remain unverified. |
| `scope.math_metadata` | `firmware-unverified` | Manual only | Math traces and result-axis properties exist, but a February 2026 rolling manual cannot be projected onto firmware `8.4.1`. |
| `scope.fft_status` | `firmware-unverified` | Manual only | The contract requires RBW, sample rate, and averaging completion; no verified path fills all fields. |
| `scope.reference_metadata` | `firmware-unverified` | Manual only | Memory traces and result-axis properties exist; reference storage is not created or overwritten merely to produce acceptance evidence. |
| `scope.cursor_readout` | `firmware-unverified` | Manual only | `CRVA?` reads configured cursors, but the response format and complete WaveBench mapping are not hardware verified. |
| `scope.screenshot_profile` | `unsafe-quarantined` | Manual contract review | `SCDP?` returns hardcopy status and cannot establish PNG format, menu state, or color mode. The plugin does not fabricate a profile through the filesystem or arbitrary VBS. |
| `scope.screenshot_v2` | `unsafe-quarantined` | Manual contract review | The core contract requires a PNG payload plus display-state snapshot, restoration, and independent verification. The existing `SCDP` path does not satisfy that transaction. |
| `scope.acquisition_run_state` | `firmware-unverified` | Manual and driver review | `TRMD?` values `AUTO/NORM/SINGLE` describe trigger mode more closely; only `STOP` proves stopped state, and ready, arming, waiting, or acquiring cannot be distinguished. |
| `scope.acquisition_control` | `firmware-unverified` | Partial hardware evidence | Existing capture validates `STOP → ARM → WAIT → *OPC?`, but not the typed baselines, failure recovery, and independent readback required for generic continuous start, stop, and single acquisition. |
| `scope.trace_metadata` | `firmware-unverified` | Analog-channel candidate only | `WAVEDESC` already supports analog waveform conversion, but `ScopeTraceRef` and typed metadata are not implemented; digital, math, and reference traces also lack complete firmware evidence. |
| `scope.fetch_trace` | `firmware-unverified` | Partial transfer hardware evidence | `CHDR/CFMT/CORD/WFSU` transfer state is verified, but the new contract also requires trace source/mode, run state, typed baseline, and independent restoration verification. Legacy `fetch_waveform` is not presented as the complete contract. |
| `scope.error_drain_v1` | `contract-incompatible` | Fixed-register contract review | `CMR?`, `EXR?`, and `DDR?` are three fixed read-to-clear registers and cannot honestly satisfy one termination sentinel, an overflow record, and `query_count == records + 1`. Existing `scope.errors` remains in place. |

## Relationship to 100% manual coverage

This matrix answers whether each current WaveBench interface can be represented. [`COMMAND_COVERAGE_EN.md`](COMMAND_COVERAGE_EN.md) and the machine catalog answer how every explicit manual entity is disposed. Their denominators differ: 26 capabilities here and 578 explicit manual entities in the command catalog.

One hundred percent coverage therefore does not mean executing every instruction on hardware. Reset, calibration, filesystem, network, hardcopy, option activation, shutdown, and arbitrary-script paths remain quarantined. Missing options, model exclusions, unverified firmware behavior, and core-model gaps remain auditable coverage outcomes.
