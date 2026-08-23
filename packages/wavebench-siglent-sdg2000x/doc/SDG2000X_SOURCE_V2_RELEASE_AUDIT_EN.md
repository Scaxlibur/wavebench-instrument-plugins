# SDG2000X Source V2 C3 Release-Audit Preparation

[中文](SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)

## Current Status

At plugin version `0.8.1`, C3 is not complete. This document records only release preparation that can be
reviewed offline and separates A0 from the device-dependent A1–A3 gates. It is not a release sign-off, a
wheel conformance manifest, or a hardware claim for any model or firmware.

## C3 Conditions and Current Evidence

| C3 condition | Current offline evidence | Status |
| --- | --- | --- |
| First plugin M5 Basic/Output offline contract | The descriptor declares `source.snapshot_v2`, `source.basic_configure_v2`, and `source.output_v2`; driver and core fake-transport tests cover query, write, readable mismatch, and recovery branches | A0 complete |
| Declared Basic write surface | CH1/CH2 frequency, Vpp, Sine/Square/Ramp/Pulse changes, and square duty each have single-field, single-write, no-MAIN-query fake tests; `offset_v` and multi-field patches reject before I/O; a readable mismatch gets at most one OFF and an ambiguous write gets no extra I/O | A0 complete |
| Declared Output write surface | CH1/CH2 may be ON together and disabling either leaves the other unchanged; core phases, one OFF recovery after a readable postcondition mismatch, and no retry or extra I/O after an ambiguous ON/OFF result have fake tests | A0 complete |
| Declared Harmonic-disable write surface | `source.harmonics_disable_v2` applies only to `SDG2122X` / `2.01.01.39R7T2` while Sine and target output OFF are proven; an already-disabled state has zero MAIN writes, an enabled state has one `HARMSTATE,OFF` write, and the core independently reads Harmonic and output; it provides neither configuration nor enable | A0 complete |
| Version, descriptor, and package metadata | `pyproject.toml`, descriptor, READMEs, coverage matrices, and A0 record agree on `0.8.1`; wheel/sdist, isolated discovery, and dependency/descriptor cross-checks have offline tests | Offline complete |
| No unregistered write capability | Descriptor, driver, `validate_source_descriptor()`, and `validate_declared_capabilities()` are checked together; no raw-SCPI endpoint is exposed | Current source audited |
| A1, A2, and A3 | No real-device profile read, output transition/recovery, or scope-loopback validation has run | Awaiting separate authorization |
| Stable core and release-artifact sign-off | WaveBench `0.8.24` remains a development line; no final plugin wheel digest, A1–A3 manifest, or release sign-off exists | Pending |

## A0 Scope

Offline tests prove protocol contracts and core call boundaries only:

- `source.snapshot_v2` anchor/facet/anchor plans, query budgets, deadlines, and zero writes;
- audited `BSWV` write forms, pre-write rejection, one OFF recovery after a readable mismatch, and zero
  extra I/O after an ambiguous write for `source.basic_configure_v2`;
- `source.output_v2` single-write MAIN, independent postcondition, one OFF recovery after a readable
  mismatch, and no retry or extra I/O after an ambiguous ON/OFF result;
- `source.harmonics_disable_v2` zero-write idempotence, one `HARMSTATE,OFF` write, model/firmware denial,
  and independent Harmonic/output readback on the exact runtime target;
- wheel/sdist metadata, entry point, version gates, and descriptor cross-checks.

They do not prove that a real instrument accepts a command, changes an output relay, has correct wiring, or
produces a measured waveform.

## Remaining Before C3

1. A1: confirm V2 snapshot responses and query budgets on an independently authorized model, firmware,
   resource, and transport/backend.
2. A2: confirm V2 Basic/Output and exact-runtime-target Harmonic-disable completion, independent readback,
   rejection, and OFF recovery. Unknown
   transport results remain poisoned and receive no unapproved additional I/O.
3. A3: use a scope loopback to confirm declared writes for frequency, Vpp, function, and duty cycle; record
   the pre-enable offset reading, termination, limits, tolerance, and final OFF state.
4. Use a stable core and final plugin wheel to create and review a conformance manifest, then perform the
   actual release sign-off.

Hardware work requires new explicit authorization. This audit does not change `wavebench.toml`, connect to
instruments, or replace any recovery procedure.
