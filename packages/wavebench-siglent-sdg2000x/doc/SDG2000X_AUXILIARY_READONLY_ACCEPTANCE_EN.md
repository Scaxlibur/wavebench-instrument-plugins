# SDG2000X Auxiliary and Global-State Read-Only Acceptance

[中文](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed read-only A3 acceptance for Sync, Frequency Counter, reference clock, phase mode, over-voltage protection, number format, language, power-on configuration, buzzer, screen saver, and multi-device synchronization.

The formal pass used `read_only` access and performed 18 queries with zero writes. Both main outputs were OFF at the beginning and end. Reference-clock, Cascade, Counter, Sync, protection, and system settings were not changed.

These results prove query protocol and current state only, not electrical behavior or measurement accuracy for unwired interfaces. Switching the external reference, enabling Counter, or rewriting global protection/UI settings merely to increase a coverage number would be unsafe and misleading.

## Environment and boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- The only known wiring is CH1/CH2 main outputs to the RTM2032. Sync/Aux, Counter input, and external-reference interfaces were not part of physical wiring proof.

All queries ran through the plugin transport with no public raw-SCPI endpoint. The pass sent no `*RST`, `ROSC`, `FCNT`, `SYNC`, `CASCADE`, `VOLTPRT`, or system-setting write.

## Query results

| Domain | Query | Current readback | Grade |
| --- | --- | --- | --- |
| CH1 Sync | `C1:SYNC?` | OFF, Type=CH1 | A3 |
| CH2 Sync | `C2:SYNC?` | OFF, Type=CH2 | A3 |
| Frequency Counter | `FCNT?` | OFF | A3 |
| Reference clock | `ROSC?` | INT, 10 MHz Output=ON | A3 |
| Phase mode | `MODE?` | `PHASE-LOCKED` | A3; separate A4 phase evidence exists |
| Over-voltage protection | `VOLTPRT?` | ON | A3 |
| Number format | `NBFM?` | decimal DOT, separator SPACE | A3 |
| Language | `LAGG?` | Simplified Chinese | A3 |
| Power-on configuration | `SCFG?` | DEFAULT | A3 |
| Buzzer | `BUZZ?` | ON | A3 |
| Screen saver | `SCSV?` | OFF | A3 |
| Multi-device sync | `CASCADE?` | OFF with retained Master mode | A3 |

`ROSC?` showed that 10 MHz Output was already ON before acceptance. It was left unchanged. Without a qualified external reference and lock-state evidence, the clock source must not be switched to EXT, and disabling an existing clock output is not legitimate “cleanup.”

## Firmware response differences

- With Counter OFF, `FCNT?` returns only `FCNT STATE,OFF`, omitting measurement and configuration fields shown in the manual's ON example.
- `VOLTPRT?` returns bare `ON`, not the documented `VOLTPRT ON`.
- `MODE?` returns `PHASE-LOCKED`, unlike E05C's `PHASELOCKED` spelling.
- `SYNC?` retains `TYPE` while OFF.
- `CASCADE?` retains `MODE,MASTER` while OFF.

Strict parsing must allow state-dependent omission and only confirmed response variants. A fixed token count or the manual's ON example cannot parse every state.

## Core interface boundary

- `SourceChannelProfile` requires Sync polarity, while SDG2000X `SYNC?` reports routing Type and no polarity. A default cannot be invented.
- The current Counter profile requires observable configuration and valid measurements. `FCNT?` provides only state while OFF. Writing configuration before reporting it would violate read-only semantics and would become stale after panel or third-party changes.
- Reference clock needs a reusable facet for `selected_source`, `lock_state`, `available_sources`, and output state; it does not belong in Sync or Counter.
- Cascade, protection, and UI settings are global system domains, not channel Source capabilities.

Reusable modeling is covered by the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md). The core repository was not changed.

## Transport audit

The formal pass used 18 queries, zero write requests, zero transmitted or completed writes, zero unknown write outcomes, and zero instrument-mutation writes. Public `source.status` reconfirmed both outputs OFF at completion.

## Requirements for later physical acceptance

- Sync: connect Sync/Aux to a scope and verify frequency/phase relationships under basic wave, modulation, Sweep, and Burst.
- Counter: connect a known calibrated signal to Counter BNC and verify frequency, period, positive/negative width, duty, and deviation.
- External reference: provide a qualified 10 MHz source, correct amplitude/impedance, and lock-loss detection in a separate high-risk transaction.
- Cascade: use at least two compatible instruments, dedicated wiring, and a delay reference. A single-unit state toggle is not multi-device synchronization evidence.
