# SDG2000X Public Source API Dual-Channel Acceptance

[中文](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, `wavebench-siglent-sdg2000x` 0.8.0 completed CH1/CH2 A4 acceptance through WaveBench 0.8.23 `SourceService` on one `SDG2122X`. The pass covered `source.set_amplitude_vpp`, `source.set_frequency`, Sine/Square/Ramp `source.set_function`, `source.set_square_duty_cycle`, and `source.output`.

Both channels covered output-OFF configuration, output ON, live frequency/amplitude writes while ON, and final restoration. All 23 formal writes were transmitted and completed with zero unknown outcomes. The highest measured level was 0.80 Vpp, below the 9 V stop threshold and 10 Vpp hard limit.

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Scope: `RTM2032`, firmware `06.010`.
- Wiring: source CH1 to scope CH1 and source CH2 to scope CH2, both high impedance.

Earlier harmonic acceptance had correctly restored Harmonic ON on CH1. The first preflight was therefore rejected by the plugin's advanced-mode gate before any basic-configuration write; both outputs stayed OFF. The formal pass separately saved and disabled Harmonic on both channels outside the public-operation audit interval, then restored each original enable state after all public API operations.

Every functional call passed through the declared descriptor, `SourceService`, `SourceStateGuard`, plugin driver, and core transport audit. No public raw-SCPI bypass was used.

## CH1 results

| Stage | Requested | RTM2032 result |
| --- | --- | --- |
| Square | 1.3 kHz, 0.5 Vpp, 30% | 1.4 kHz FFT bin, 0.64 Vpp, 28.70% high fraction |
| Ramp | 1.3 kHz, 0.5 Vpp | 1.4 kHz FFT bin, 0.64 Vpp |
| Live Sine write | 1.5 kHz, 0.6 Vpp | 1.6 kHz FFT bin, 0.80 Vpp |

## CH2 results

| Stage | Requested | RTM2032 result |
| --- | --- | --- |
| Square | 1.7 kHz, 0.5 Vpp, 70% | 1.8 kHz FFT bin, 0.72 Vpp, 69.49% high fraction |
| Ramp | 1.7 kHz, 0.5 Vpp | 1.8 kHz FFT bin, 0.64 Vpp |
| Live Sine write | 1.9 kHz, 0.6 Vpp | 2.0 kHz FFT bin, 0.72 Vpp |

The current RTM2032 record has 200 Hz FFT spacing, so off-grid requests fall on an adjacent bin center. The pass used FFT frequency with a one-bin tolerance. Raw zero-crossing estimates were contaminated by the current 80 mV quantization steps and noise and were not used as acceptance criteria.

## Core transaction evidence

The formal pass used 510 queries, 23 write requests, 23 transmitted writes, 23 completed writes, zero unknown outcomes, and 23 instrument-mutation writes. The query count comes from identity, complete state, safety context, readback closure, and core postcondition checks around every public write, not error-queue polling.

At completion, CH1 and CH2 were both restored to Sine / 1 kHz / 4 Vpp / 0 V / OFF; original Harmonic enable states were restored; and RTM2032 channel, probe, timebase, and trigger snapshots were unchanged with no overload.

## Release boundary

- All registered models (`SDG2042X`, `SDG2082X`, and `SDG2122X`) pass the same protocol contract and offline model matrix. Under the user's authorization, the two unavailable models are released by protocol.
- A4 electrical evidence applies only to the tested SDG2122X firmware and is not calibration evidence for other models.
- Noise/DC remain outside the safe periodic-wave Vpp state; public output enable continues to reject them.
- Basic write capabilities intentionally reject while advanced modes are active. Callers must end the advanced transaction explicitly; the plugin does not silently clear state.
