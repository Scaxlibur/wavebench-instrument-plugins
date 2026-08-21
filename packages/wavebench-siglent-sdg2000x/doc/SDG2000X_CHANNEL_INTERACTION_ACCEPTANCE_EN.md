# SDG2000X Tracking, Coupling, Copy, and Dual-Channel Trigger Acceptance

[中文](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed acceptance for channel tracking, frequency/amplitude/phase coupling, bidirectional parameter copy, and dual-channel manual Burst triggering.

- `TRACE` immediately copied the complete CH1 basic-wave state to CH2 and continued tracking CH1 frequency and amplitude changes.
- `FRAT/FDEV`, `ARAT/ADEV`, and `PRAT/PDEV` strictly read back and produced corresponding A4 waveforms on both outputs.
- `PACP C2,C1` and `PACP C1,C2` both produced complete basic-wave readback; CH1-to-CH2 also produced dual-channel A4 evidence.
- `TRDUCH` means joint Manual Burst triggering, not generic tracking direction. With `TRDUCH ON`, a CH2 manual trigger produced ten-cycle bursts on both channels in two valid captures.

The highest regular-interaction measurement was 0.72 Vpp, and the highest dual-Burst measurement was 2.16 Vpp. Both were below the 9 V stop threshold and 10 Vpp hard limit. All formal source writes completed with zero unknown outcomes. Both outputs, both Burst states, and all Coupling states were OFF at completion.

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Scope: `RTM2032`, firmware `06.010`.
- Wiring: source CH1 to scope CH1 and source CH2 to scope CH2, both high impedance.

Both outputs and Modulation, Sweep, Burst, Harmonic, Combine, and Noise Add were confirmed OFF before testing. Only one interaction mode was enabled at a time, and every mode transition occurred with output OFF. Any capture reaching 9 Vpp or an absolute sample beyond 5 V would stop the test.

## Protocol results

### Tracking and dual-channel trigger

In the normal disabled state, `COUP?` returns five states: `TRACE/FCOUP/PCOUP/ACOUP/TRDUCH`. With `TRACE ON`, this firmware returns only `COUP TRACE,ON`; other fields are omitted. A parser cannot require disabled-state fields in every state.

`TRACE ON` immediately replaced CH2 Square / 3 kHz / 0.2 Vpp / 30 degrees with CH1 Sine / 1 kHz / 0.4 Vpp / 10 degrees. Changing CH1 to 1.5 kHz and 0.6 Vpp then produced identical CH2 readback.

`TRDUCH ON` did not copy basic-wave state. Changing CH1 frequency left CH2 unchanged. The user manual defines this field as dual-channel Manual Burst triggering, and hardware acceptance followed that meaning.

### Frequency, amplitude, and phase coupling

| Mode | CH1 readback | CH2 readback | Relationship |
| --- | ---: | ---: | --- |
| `FRAT,2` | 1200 Hz | 2400 Hz | CH2 / CH1 = 2 |
| `FDEV,500` | 1200 Hz | 1700 Hz | CH2 − CH1 = 500 Hz |
| `ARAT,0.5` | 0.4 Vpp | 0.2 Vpp | CH2 / CH1 = 0.5 |
| `ADEV,0.1` | 0.4 Vpp | 0.5 Vpp | CH2 − CH1 = 0.1 Vpp |
| `PRAT,2` | 30° | 60° | CH2 / CH1 = 2 |
| `PDEV,90` | 30° | 120° | CH2 − CH1 = 90° |

`COUP?` returns only the active relationship field: `FRAT` versus `FDEV`, `ARAT` versus `ADEV`, and so on. Generic parsing must treat them as conditional named fields.

### Parameter copy

With both outputs and all Coupling states OFF:

- `PACP C2,C1` copied CH1 Sine / 2 kHz / 0.4 Vpp / 0.05 V / 10 degrees to CH2;
- `PACP C1,C2` copied CH2 Ramp / 4 kHz / 0.3 Vpp / -0.02 V / 40 degrees to CH1.

PACP has no query, so independent post-copy `BSWV?` responses are the protocol evidence.

## Regular interaction waveform results

| Case | CH1 result | CH2 result |
| --- | --- | --- |
| Tracking | 1800 Hz, 0.3988 Vpp | 1800 Hz, 0.4051 Vpp |
| Frequency ratio 2 | 1200 Hz, 0.3977 Vpp | 2400 Hz, 0.2135 Vpp |
| Frequency deviation 500 Hz | 1200 Hz, 0.3969 Vpp | 1700 Hz readback and 0.2127 Vpp fit at 1700 Hz |
| Amplitude ratio 0.5 | 1000 Hz, 0.3997 Vpp | 1000 Hz, 0.2145 Vpp |
| Amplitude deviation 0.1 Vpp | 1000 Hz, 0.3982 Vpp | 1000 Hz, 0.5036 Vpp |
| Phase ratio 2 | phase reference | CH2−CH1 = 29.66° |
| Phase deviation 90° | phase reference | CH2−CH1 = 89.85° |
| CH1-to-CH2 copy | 2200 Hz, 0.3979 Vpp | 2200 Hz, 0.4040 Vpp |

The current RTM2032 FFT grid is 200 Hz. The 1700 Hz deviation case therefore peaked in the 1600 Hz bin, but it also had exact 1700 Hz source readback and a 0.2127 Vpp orthogonal fit at 1700 Hz. The grid center is not misreported as source frequency.

## Dual-channel Manual Burst results

Both channels used Sine, 10 kHz, 2 Vpp, ten cycles, and `TRSR,MAN`, with `TRDUCH` enabled. CH2 issued `MTRIG`, and the RTM2032 used CH2 as trigger source while freezing both channel records.

Two of three attempts produced usable captures:

| Valid capture | CH1 duration | CH2 duration | CH2−CH1 onset | Maximum Vpp |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.043 ms | 1.055 ms | 41.5 µs | 2.16 V |
| 2 | 1.054 ms | 1.044 ms | 40.5 µs | 2.16 V |

The third record was overwritten by AUTO acquisition and spanned the full record, so it was excluded. CH1-initiated triggering did not produce repeatable frozen records with the current scope trigger setup. This pass therefore claims CH2-to-both A4 only, not bidirectional hardware proof of the manual's “either channel” wording.

## Transport audit and restoration

The protocol pass used 46 queries and 108 writes. The regular A4 pass used 45 queries and 148 writes. The formal dual-Burst pass used 16 queries and 51 writes. In all three passes, transmitted and completed writes equaled requests, with zero unknown outcomes.

During dual-Burst diagnostics, an RTM2032 single acquisition timed out after temporarily selecting `NORM`. That scope session latched as designed. A fresh session found the scope still in `NORM`, restored only `AUTO` and `RUN`, and strictly read back the result before the formal pass. Source recovery kept both outputs OFF on every failed path.

At formal completion, both outputs and all `TRACE/TRDUCH/FCOUP/PCOUP/ACOUP` states were OFF; both Burst, Modulation, Sweep, Combine, and Noise Add states were OFF; both channels were restored to Sine / 1 kHz / 4 Vpp / 0 V; original Harmonic enable states and `PHASE-LOCKED` mode were restored; and RTM2032 channel, probe, timebase, and trigger snapshots were unchanged with no overload.

## Core interface boundary

The current core coupling/channel profiles cannot fully express state-dependent responses, mutually exclusive relationship modes, bidirectional reference behavior, action-style PACP, or joint Manual Burst transactions. The plugin does not force these commands through raw SCPI or fabricate a complete profile. Reusable facet splitting, availability, patch/transaction, and safety-budget design is in the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Coverage boundary

- Tracking, all three coupling groups, and CH1-to-CH2 copy have A4 evidence; CH2-to-CH1 copy has A3 evidence.
- `TRDUCH` has repeated CH2-initiated A4 evidence only; CH1 initiation needs a more stable dual-record capture method.
- Coupling was not combined with Modulation, Sweep, Harmonic, Combine, or Noise Add.
- Hardware evidence applies only to the tested SDG2122X firmware.
