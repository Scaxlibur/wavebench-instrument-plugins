# SDG2000X Dual-Channel Waveform Combine Acceptance

[中文](SDG2000X_COMBINE_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed bidirectional A4 acceptance for `C1:CMBN` and `C2:CMBN`. Each target output contained both its own tone and the other channel's tone. The foreign tone returned to the noise floor after Combine was disabled. Combine remained effective while the source channel's front-panel output was OFF, proving that this firmware uses the other channel's internal signal path rather than its output relay.

The highest measured level was 0.56 Vpp, below the 9 V stop threshold and 10 Vpp hard limit. All 50 formal writes completed with zero unknown outcomes. Both outputs and both Combine states were OFF at completion.

The current core has no generic Source facet that can losslessly express cross-channel composition, participants, envelope budget, and state dependencies. The plugin therefore does not publish a Combine write capability. See the reusable [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Scope: `RTM2032`, firmware `06.010`.
- Wiring: source CH1 to scope CH1 and source CH2 to scope CH2, both high impedance.
- CH1: 2 kHz Sine, 0.2 Vpp, 0 V offset.
- CH2: 5 kHz Sine, 0.2 Vpp, 0 V offset.

Harmonic, Modulation, Sweep, Burst, Noise Add, Coupling, and Invert were disabled on both channels. Only the target output was enabled initially. The source output would be enabled only if the internal contribution were absent. Any capture reaching 9 Vpp or an absolute sample beyond 5 V would stop the test.

## Bidirectional waveform results

The analysis used an orthogonal least-squares fit at 2 kHz and 5 kHz, avoiding FFT-bin leakage as a presence criterion.

| Target | State | 2 kHz fitted Vpp | 5 kHz fitted Vpp | Trace Vpp |
| --- | --- | ---: | ---: | ---: |
| CH1 | Combine OFF | 0.1995 V | 0.0016 V | 0.40 V |
| CH1 | Combine ON, CH2 output OFF | 0.1985 V | 0.1991 V | 0.56 V |
| CH1 | OFF again | 0.1977 V | 0.0016 V | 0.40 V |
| CH2 | Combine OFF | 0.0014 V | 0.2132 V | 0.40 V |
| CH2 | Combine ON, CH1 output OFF | 0.2048 V | 0.2041 V | 0.56 V |
| CH2 | OFF again | 0.0023 V | 0.2139 V | 0.40 V |

Neither direction required the source-channel output relay. Trace Vpp includes sampling noise and quantization at the existing RTM2032 range, so the functional criterion uses fitted amplitudes at known frequencies rather than trace extrema alone.

## Transport audit and restoration

The formal pass used:

- 28 queries;
- 50 write requests;
- 50 transmitted writes;
- 50 completed writes;
- zero unknown write outcomes.

At completion, both outputs and both Combine states were OFF; both channels were restored to Sine / 1 kHz / 4 Vpp / 0 V; original Invert and Harmonic enable states were restored; and the RTM2032 channel, probe, timebase, and trigger snapshots were unchanged with no overload.

## Coverage boundary

- This pass covers bidirectional unlike-frequency combination, disable restoration, and source-output-relay dependence.
- A generic safety implementation must calculate the worst-case envelope from offsets, peaks, random-signal crest factors, and load; it cannot merely add nominal Vpp values.
- Combine interaction with modulation, sweep, burst, harmonic, Noise Add, or Coupling is not covered because those combinations require explicit mutual-exclusion and availability models.
- Hardware evidence applies only to the tested SDG2122X firmware.
