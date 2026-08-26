# SDG2000X Burst Protocol and Waveform Acceptance

[中文](SDG2000X_BURST_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed output-OFF Burst protocol characterization and finite-cycle A4 waveform acceptance. Internal 5-, 10-, and 20-cycle bursts measured exactly 5, 10, and 20 carrier cycles. A requested 2 ms repetition measured 1.998 ms, and two manual triggers each produced a 10-cycle burst.

The carrier was Sine, 10 kHz, 2 Vpp, and 0 V offset. Maximum valid burst output was 2.16 Vpp, below the 9 V stop threshold and 10 Vpp hard limit. All 109 writes in the formal pass completed, with zero unknown outcomes.

`TIME,INF` read back but did not produce a repeatable continuous 10 kHz carrier for either INT or MAN entry sequence. Five refreshed records contained only an approximately 0.24 Vpp noise floor. Infinity therefore fails physical acceptance; protocol readback is not substituted for A4 evidence.

The current core `SourceBurstProfile` requires finite cycles, internal period, gate polarity, and trigger slope even for GATED, INFINITY, MANUAL, EXTERNAL, and `enabled=False` states where those values are not simultaneously applicable on SDG. The plugin inserts no fake defaults and declares no lossy Burst capability. See the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.7.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to high-impedance scope CH2.
- Carrier: Sine, 10 kHz, 2 Vpp, 0 V offset.

Output was disabled before each configuration. Harmonic, Modulation, Sweep, Combine, Noise Add, and Coupling were confirmed inactive. Public `source.output` continues to reject Burst ON by design; only the managed acceptance script directly controlled output.

## Protocol results

| Field or mode | Firmware result | Acceptance |
| --- | --- | --- |
| `TIME` | 1, 5, 10, 20, and INF read back | A3 |
| `STPS` | 0°, 90°, and 359° read back | A3 |
| `DLAY` | 0 and 100 µs read back | A3; no independent trigger reference |
| `TRMD` | RISE, FALL, and OFF read back | A3; Trigger Out unwired |
| `EDGE` | EXT RISE/FALL read back | A3; external trigger unwired |
| `EDGE` | Not returned for MAN | Not claimed |
| `GATE_NCYC,GATE` | POS/NEG polarity read back | A3; Gate input unwired |
| `MTRIG` | Two actions each produced a finite burst | A4 / T1 |
| `TIME,INF` | Read back; trigger-source field depends on write order | Protocol presence only |

When recovering from hidden `TIME,INF/TRSR,MAN` state, finite `TIME` must be written before `TRSR,INT`; the reverse order is ignored by this firmware. Composite configuration cannot be treated as an unordered retryable field set.

## Finite-cycle waveform results

Burst duration used the analytic envelope. Carrier-cycle count combined the active-segment FFT frequency with duration, avoiding false raw zero crossings around burst edges.

| Configuration | Median duration | Median carrier cycles | Active frequency | Measured Vpp |
| --- | ---: | ---: | ---: | ---: |
| 5 cycles / INT | 0.543 ms | 5.0 | 9.20 kHz | 2.08–2.16 V |
| 10 cycles / INT | 1.043 ms | 10.0 | 9.59 kHz | 2.16 V |
| 20 cycles / INT | 2.043 ms | 20.0 | 9.79 kHz | 2.16 V |
| 10 cycles / MAN | 1.039 ms | 10.0 | — | 2.16 V maximum |

A 5-cycle, 2 ms internal-period record contained three bursts with a 1.998 ms median onset interval. Two consecutive manual triggers each produced a separate 10-cycle burst.

## Infinity negative result

`TRSR,INT` and `TRSR,MAN` were each confirmed while finite before entering INF; the requested source did not remain reliably present in INF readback. Five refreshed records were collected for each sequence:

- valid continuous-carrier records: 0;
- maximum measured output: 0.24 Vpp;
- maximum 10 kHz fixed component: approximately 0.0011 V for INT and 0.0014 V for MAN.

This proves only that the tested firmware and command sequence did not produce the expected continuous carrier. It is not extrapolated to other models, and the noise floor is not counted as passing Infinity output.

## Transport audit and restoration

The formal pass used 96 queries and 109 writes. Every write was transmitted and completed, with zero unknown outcomes. It ended with both outputs OFF, Burst and Sweep OFF, CH2 restored to Sine / 1 kHz / 4 Vpp / 0 V, unchanged RTM2032 channel/probe/timebase/trigger snapshots, and no overload.

A separate fresh session reconfirmed both outputs OFF using 13 queries and zero writes.

## Coverage boundary

- EXT, Gate, and Trigger Out lack physical wiring and remain A3 only.
- `DLAY` and `STPS` lack an independent trigger reference and remain A3 only.
- Infinity failed physical acceptance and is not exposed as a product capability.
- Disabled Burst hides its configuration. Acceptance restores a known safe baseline but does not claim restoration of unknown hidden fields.
- Evidence applies only to the tested SDG2122X firmware.
