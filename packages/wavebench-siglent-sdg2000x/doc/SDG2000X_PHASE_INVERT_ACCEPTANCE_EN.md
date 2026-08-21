# SDG2000X Phase Mode, Equal-Phase, and Invert Acceptance

[中文](SDG2000X_PHASE_INVERT_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed acceptance for `MODE`, `EQPHASE`, and per-channel `INVT`. Two 1 kHz, 0.5 Vpp sine outputs differed by -0.27 degrees after `EQPHASE` in `PHASE-LOCKED` mode. The difference became 179.54 degrees when CH2 was inverted and 179.90 degrees when CH1 was inverted. The highest measured level was 0.72 Vpp, below the 9 V stop threshold and 10 Vpp hard limit.

All 44 formal writes completed with zero unknown outcomes. Both outputs were OFF at completion, and original invert states and phase mode were restored.

The hardware also established that this firmware uses `MODE PHASE-LOCKED`, including the hyphen in query responses and accepted writes. E05C documents `PHASELOCKED`; the unhyphenated setting was silently ignored by the tested unit.

Although core `SourceChannelProfile` contains output polarity, it also requires Noise ratio, Sync polarity, Marker, Modulation type, and Pulse hold fields that this instrument cannot authoritatively query. The plugin cannot publish Invert by fabricating those unrelated values, so it does not declare the monolithic profile. See the reusable [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Scope: `RTM2032`, firmware `06.010`.
- Wiring: source CH1 to scope CH1 and source CH2 to scope CH2, both high impedance.
- Baseline: Sine, 1 kHz, 0.5 Vpp, 0 V offset, and 0 degrees on both channels.

Harmonic, Modulation, Sweep, Burst, Combine, Noise Add, and Coupling were disabled. The scope performed one common `SINGle`, read CH1 and CH2 from that frozen acquisition, and then resumed `RUN`, avoiding false phase offsets from sequential acquisitions.

## Protocol difference

| Operation | Hardware result |
| --- | --- |
| `MODE?` | `MODE PHASE-LOCKED` or `MODE INDEPENDENT` |
| `MODE INDEPENDENT` | Accepted and read back |
| `MODE PHASELOCKED` | Silently ignored |
| `MODE PHASE-LOCKED` | Accepted and read back |
| `C1:INVT ON/OFF` | Accepted and strictly read back |
| `C2:INVT ON/OFF` | Accepted and strictly read back |
| `EQPHASE` | Action with no query; proved by dual-channel waveform |

An early diagnostic pass temporarily left the phase mode at `INDEPENDENT` because the documented token was silently ignored. Both outputs remained OFF throughout. The initial `PHASE-LOCKED` state was then explicitly restored with the hyphenated token and independently read back before the complete formal pass was rerun. The formal pass began and ended in `PHASE-LOCKED`.

## Waveform results

Each channel was fitted against orthogonal 1 kHz sine/cosine bases. The phase difference is normalized as CH2 minus CH1.

| State | CH2−CH1 phase | CH1 fitted Vpp | CH2 fitted Vpp | Maximum trace Vpp |
| --- | ---: | ---: | ---: | ---: |
| After `EQPHASE`, both normal | -0.27° | 0.4986 V | 0.5027 V | 0.72 V |
| CH2 `INVT ON` | 179.54° | 0.5007 V | 0.5025 V | 0.72 V |
| CH1 `INVT ON` | 179.90° | 0.5019 V | 0.5046 V | 0.72 V |

The acceptance thresholds were at most 20 degrees for equal phase and at least 150 degrees for inversion. Measurements were well away from both boundaries.

## Transport audit and restoration

The formal pass used:

- 24 queries;
- 44 write requests;
- 44 transmitted writes;
- 44 completed writes;
- zero unknown write outcomes.

At completion, both outputs were OFF; both channels were restored to Sine / 1 kHz / 4 Vpp / 0 V; original Invert and Harmonic enable states and `PHASE-LOCKED` mode were restored; and the RTM2032 channel, probe, timebase, and trigger snapshots were unchanged with no overload.

## Coverage boundary

- `EQPHASE` is a non-queryable action and can only be proved by a same-acquisition dual-channel capture.
- `INVT` has dual-channel protocol and A4 phase-flip evidence, but was not combined with modulation, sweep, burst, or Combine.
- `INDEPENDENT` has A3 set/readback evidence only; short-term phase drift is not used as semantic proof.
- Hardware evidence applies only to the tested SDG2122X firmware.
