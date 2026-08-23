# SDG2000X Source V2 A1/A2 Hardware Acceptance

[中文](SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE.md)

## Conclusion

On 2026-08-24, the current SDG2000X Source V2 adapter completed A1 and limited A2 acceptance on one
`SDG2122X` running firmware `2.01.01.39R7T2`. The evidence applies only to that model, firmware, and the
channels/directions listed below; it does not extend to `SDG2042X`, `SDG2082X`, other firmware revisions, or
unlisted features.

- A1: `source.snapshot_v2` completed a consistent read-only snapshot for CH1/CH2. The two Sine channels used
  38 queries and zero instrument writes; the session remained healthy.
- A2: `source.basic_configure_v2` completed one 1 Vpp write and independent readback on each of CH1 and CH2.
  `source.output_v2` completed one ON and one OFF transition on each channel. The final read-only snapshot was
  Sine / 1 kHz / 1 Vpp / 0 V / Harmonic OFF / output OFF on both channels, with a healthy session.
- A2: `source.harmonics_disable_v2` completed one audited disable write on CH1, followed by independent
  Harmonic-OFF and output-OFF readback. That capability remains limited to the exact model and firmware on this page.

This record is not A3 waveform acceptance, fault-injection acceptance, a conformance manifest, or release sign-off.

## Software and Safety Boundary

- Core source version: WaveBench `0.8.24` development line; Source contract revision `R7`.
- Plugin: `wavebench-siglent-sdg2000x` `0.8.2`, canonical driver ID `siglent.sdg2000x`.
- The controlled configuration set `max_source_vpp` to 5 Vpp. All Basic/Output requests in this round used
  1 Vpp, below that limit and the authorized 10 Vpp ceiling.
- Every write used `run check → run verify → run intent → run plan`. No raw SCPI was used and `wavebench.toml`
  was not changed.
- Retained private run records contain redacted intent, operation artifacts, I/O counts, and final state.
  Resource addresses, serial numbers, and raw responses are not included here or in release artifacts.

## A1: Dual-Channel Read-Only Snapshot

When runtime identity matched the descriptor applicability, `source.snapshot_v2` read the CH1/CH2
anchor/facet/anchor state.

| Item | Result |
| --- | --- |
| capability | `source.snapshot_v2` |
| channels | CH1, CH2 |
| queries / writes | 38 / 0 |
| consistency | `consistent` |
| session health | `healthy → healthy` |
| initial basic state | Sine / 1 kHz / 4 Vpp / 0 V / output OFF on both channels |

This evidence proves the query responses, budget, and runtime model/firmware applicability only. It does not
prove output transitions or waveform accuracy.

## A2: Controlled Basic, Output, and Harmonic Disable

### Basic and Output

A controlled plan wrote 1 Vpp to each channel while output was OFF, then enabled and disabled the two outputs
in sequence. All nine steps completed. The source recorded six completed mutations and zero unknown outcomes;
the scope only supplied the coupling safety guard and did not capture a waveform.

Each Basic and Output operation obtained an independent postcondition snapshot. A final read-only V2 snapshot
confirmed Sine / 1 kHz / 1 Vpp / 0 V / Harmonic OFF / output OFF on both channels, with a healthy session.

### Harmonic Disable

An initial Basic attempt encountered an existing Harmonic state. The earlier Basic driver refused that state
before sending a Basic command; because MAIN had started, the core issued one OFF recovery and verified output
OFF. That round is neither a successful Basic write nor hardware fault-injection evidence.

`source.harmonics_disable_v2` then disabled Harmonic on CH1. The operation had one completed mutation, no
unknown outcome or recovery, and independent Harmonic-OFF/output-OFF readback with a healthy session. The
final Harmonic-OFF state on CH2 was observed only; no CH2 Harmonic-disable operation ran. The Basic/Output plan
ran only after the CH1 operation.

## Not Proven

- No scope loopback verified frequency, Vpp, offset, waveform, or duty cycle. A3 remains pending.
- No transport failure, ambiguous write, or post-write readback mismatch was induced. Those recovery branches
  remain A0 fault-injection evidence and are not claimed as A2 hardware evidence.
- No other model, firmware, load, port mapping, or advanced Source V2 capability was verified.
- No wheel conformance manifest existed when this acceptance ran; later candidate manifests and release sign-off
  status are recorded separately.
