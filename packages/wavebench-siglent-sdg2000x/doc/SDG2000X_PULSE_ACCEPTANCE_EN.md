# SDG2000X Pulse Protocol and Waveform Acceptance

[中文](SDG2000X_PULSE_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed Pulse parameter protocol and A4 waveform acceptance. At 1 kHz and 2 Vpp, requested 25% and 65% duty measured 25.20% and 64.96%. Requested 20/40 µs rise/fall times measured 20.0–20.9 µs and 39.5–42.4 µs. Maximum measured output was 2.16 Vpp, below the 9 V stop threshold and 10 Vpp hard limit.

`WIDTH`, `DUTY`, `RISE`, `FALL`, and `DLY` all supported independent write and readback. This firmware may return second-valued fields without an `S` suffix. All 38 writes in the formal pass completed, with zero unknown outcomes.

The current core `SourcePulseProfile` requires authoritative `hold` as either `WIDTH` or `DUTY`. SDG returns both values but no hold state. Frequency changes preserved width in this hardware pass, but observed behavior is not an authoritative protocol field and cannot support a lossless round trip. The plugin therefore declares no lossy Pulse profile/control capability. See the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.7.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to high-impedance scope CH2.
- Baseline: Pulse, 1 kHz, 2 Vpp, 0 V offset.

Every parameter was configured with output OFF. Harmonic, Modulation, Sweep, Burst, Combine, Noise Add, and Coupling were confirmed inactive. Output was disabled immediately after each acquisition.

## Protocol results

| Operation | Readback |
| --- | --- |
| `DUTY,25` at 1 kHz | 25%, `WIDTH=250 µs` |
| Then change to 2 kHz | `WIDTH=250 µs` preserved, `DUTY=50%` |
| `WIDTH,300 µs` at 1 kHz | 300 µs, `DUTY=30%` |
| Then change to 2 kHz | `WIDTH=300 µs` preserved, `DUTY=60%` |
| `DLY` | 0 and 100 µs read back |
| `RISE/FALL` | 20/40 µs read back |

Current firmware preserved absolute width after either setting order, but the query returned no “hold width” mode bit. Round-tripping the state as `hold=DUTY` would change future frequency behavior, while hard-coding one observation as a permanent all-model semantic would also be unsafe.

Real `WIDTH`, `RISE`, `FALL`, and `DLY` responses used bare second values without an `S`. Strict parsing may accept finite bare seconds and explicit `S` seconds, while still rejecting unknown units, duplicate fields, and non-finite values.

## Waveform results

Scope platform P05/P95 levels established 10%/50%/90% thresholds. Period and width used only edges that completed 10%→90% or 90%→10% transitions, excluding false crossings from falling-edge ringing.

| Configuration | Frequency | Width | Duty | Rise 10–90% | Fall 90–10% | Vpp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 25% | 1000.0 Hz | 252.0 µs | 25.20% | 20.9 µs | 42.4 µs | 2.16 V |
| 65% | 1000.0 Hz | 649.5 µs | 64.96% | 20.0 µs | 39.5 µs | 2.16 V |

`DLY` completed 0/100 µs protocol readback only. A single free-running channel has no independent timing reference and the scope follows the measured edge, so DLY is not claimed as physical A4 evidence.

## Transport audit and restoration

The formal pass used 34 queries and 38 writes. Every write was transmitted and completed, with zero unknown outcomes. It ended with both outputs OFF, CH2 restored to Sine / 1 kHz / 4 Vpp / 0 V, unchanged RTM2032 channel/probe/timebase/trigger snapshots, and no overload.

A separate fresh session reconfirmed both outputs OFF using 13 queries and zero writes.

## Coverage boundary

- DLY lacks an independent timing reference and remains A3 only.
- Hold has no authoritative query field, so no core Pulse capability is declared.
- Parameter limits are period-dependent. This pass uses a safe 1 kHz point away from limits and is not a full-spec calibration.
- Evidence applies only to the tested SDG2122X firmware.
