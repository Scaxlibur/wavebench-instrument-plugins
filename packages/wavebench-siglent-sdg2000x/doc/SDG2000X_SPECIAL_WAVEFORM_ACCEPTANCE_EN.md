# SDG2000X Special-Waveform Protocol and Hardware Acceptance

[中文](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed focused acceptance for Noise, DC, Noise Add, and TrueArb sample-rate mode. Noise, DC, and TARB produced A4 waveform evidence. The highest measured level was 1.68 Vpp, below both the 9 V stop threshold and the 10 Vpp hard limit.

`NOISE_ADD` accepted and returned `RATIO` and `RATIO_DB`, but every documented enable form silently remained at `STATE,OFF` on this firmware. Twelve enable probes covered both channels with the main output both OFF and ON. Noise Add is therefore recorded as a negative A3 result; no write capability or fabricated A4 result is published.

The current core `SourceChannelProfile` assumes a finite Vpp periodic waveform and cannot losslessly represent Noise `STDEV/MEAN/BANDWIDTH`, a DC level, or ARB DDS/TARB mode. The plugin keeps only the published read-only `source.arbitrary_probe` and does not declare lossy capabilities for these states. See the reusable [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Scope: `RTM2032`, firmware `06.010`.
- Wiring: source CH2 to scope CH2, high-impedance input.
- Stop guard: disable output if any capture reaches 9 Vpp or an absolute sample value above 5 V.

Parameters were configured while output was OFF. Harmonic, Modulation, Sweep, Burst, Combine, and Coupling were disabled, and output was disabled immediately after each capture. DC used a fresh single acquisition followed by restoration of continuous RTM2032 acquisition, preventing reuse of an old AUTO-trigger frame.

## Noise

The source used `STDEV=0.2 V` and `MEAN=0 V`.

| Mode | Measured mean | Centered RMS | Measured Vpp |
| --- | ---: | ---: | ---: |
| Band limit OFF | -5.4 mV | 182.1 mV | 1.52 V |
| Band limit ON, 20 MHz | -3.6 mV | 196.7 mV | 1.68 V |

A 100 kHz request read back as 20 MHz, proving that this firmware clamps the request to the model minimum. The scope timebase and sampling configuration was selected for safe waveform confirmation, not calibrated bandwidth measurement, so the 20 MHz result remains A3 readback evidence.

## DC

| Requested level | Measured mean | Measured Vpp |
| ---: | ---: | ---: |
| -1.0 V | -1.0038 V | 0.16 V |
| 0 V | -5.4 mV | 0.24 V |
| +1.0 V | +1.0027 V | 0.16 V |

All mean errors were at most 5.4 mV. The listed Vpp values describe capture noise and quantization around a static trace, not periodic source amplitude.

## Negative Noise Add result

The probe covered CH1 and CH2 with output both OFF and ON, trying:

- `STATE,ON,RATIO,100`;
- `STATE,ON,RATIO_DB,20`;
- `RATIO,100` followed by a separate `STATE,ON` write.

Every query returned `STATE,OFF,RATIO,100,RATIO_DB,20dB`. The parameter register accepted the ratio while the hardware/firmware did not enter Noise Add state. The probe explicitly restored `STATE,OFF` and disabled both outputs.

This is stable negative evidence for the tested unit only. If another firmware returns `STATE,ON`, carrier-residual and spectral-noise A4 acceptance is still required before publication.

## TrueArb sample-rate mode

Built-in ARB index 2 was selected at 0.5 Vpp and 0 V offset. `SRATE MODE,TARB,VALUE,1000000` strictly read back TARB at 1 MSa/s. The measured waveform was non-flat, with 0.72 Vpp and 107.7 mV centered RMS. The test then restored DDS, the original ARB selection, and the safe Sine / 1 kHz / 4 Vpp / 0 V baseline.

No user arbitrary waveform was uploaded, deleted, or overwritten.

## Transport audit and restoration

The formal CH2 waveform pass used:

- 51 queries;
- 77 write requests;
- 77 transmitted writes;
- 77 completed writes;
- zero unknown write outcomes.

At completion, both outputs were OFF; the original ARB selection, DDS mode, and Harmonic enable state were restored; and the RTM2032 channel, probe, timebase, and trigger snapshots were unchanged with no overload.

## Coverage boundary

- Noise bandwidth coverage confirms state, clamping, and non-flat random output; it is not a spectral-density or analog-bandwidth calibration.
- DC covers three safe points under high-impedance load, not 50-ohm limits.
- TARB covers one built-in waveform and one safe sample rate, not user-waveform upload or storage.
- Noise Add is a firmware-specific negative result, not a cross-firmware claim of unavailability.
- Hardware evidence applies only to the tested SDG2122X. SDG2042X/SDG2082X are released only under the same query protocol contract.
