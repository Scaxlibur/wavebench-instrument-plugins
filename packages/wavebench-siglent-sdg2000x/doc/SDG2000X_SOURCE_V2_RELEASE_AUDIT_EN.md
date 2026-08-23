# SDG2000X Source V2 C3 Release-Audit Preparation

[中文](SDG2000X_SOURCE_V2_RELEASE_AUDIT.md)

## Current Status

At plugin version `0.8.2`, C3 is not complete. This document records offline-reviewable release preparation and
the exact-target A1/limited-A2/Basic-A3 evidence, separately from final release gates. It is not release sign-off,
a wheel conformance manifest, or an extrapolated claim for any model or firmware.

## C3 Conditions and Current Evidence

| C3 condition | Current offline evidence | Status |
| --- | --- | --- |
| First plugin M5 Basic/Output offline contract | The descriptor declares `source.snapshot_v2`, `source.basic_configure_v2`, and `source.output_v2`; driver and core fake-transport tests cover query, write, readable mismatch, and recovery branches | A0 complete |
| Declared Basic write surface | CH1/CH2 frequency, Vpp, Sine/Square/Ramp/Pulse changes, and square duty each have single-field, single-write, no-MAIN-query fake tests; `offset_v` and multi-field patches reject before I/O; a readable mismatch gets at most one OFF and an ambiguous write gets no extra I/O | A0 complete |
| Declared Output write surface | CH1/CH2 may be ON together and disabling either leaves the other unchanged; core phases, one OFF recovery after a readable postcondition mismatch, and no retry or extra I/O after an ambiguous ON/OFF result have fake tests | A0 complete |
| Declared Harmonic-disable write surface | `source.harmonics_disable_v2` applies only to `SDG2122X` / `2.01.01.39R7T2` while Sine and target output OFF are proven; an already-disabled state has zero MAIN writes, an enabled state has one `HARMSTATE,OFF` write, and the core independently reads Harmonic and output; it provides neither configuration nor enable | A0 complete |
| Version, descriptor, and package metadata | `pyproject.toml`, descriptor, READMEs, coverage matrices, and A0 record agree on `0.8.2`; wheel/sdist, isolated discovery, and dependency/descriptor cross-checks have offline tests | Offline complete |
| No unregistered write capability | Descriptor, driver, `validate_source_descriptor()`, and `validate_declared_capabilities()` are checked together; no raw-SCPI endpoint is exposed | Current source audited |
| A1: V2 snapshot | On `SDG2122X` / `2.01.01.39R7T2`, a CH1/CH2 hardware snapshot completed 38 queries and zero writes with consistent state and a healthy session | Complete; not extrapolated |
| A2: normal Basic/Output/Harmonic disable | On that target, one 1 Vpp Basic write/readback on each of CH1/CH2, one Output ON/OFF on each channel, and one CH1 Harmonic disable all succeeded; both channels finish Harmonic OFF/output OFF with a healthy session | Limited normal path complete; not full A2 |
| A2: fault, rejection, and recovery | No transport failure, ambiguous write, or post-write mismatch was induced. An initial Basic request was rejected by existing Harmonic state before the Basic command; because MAIN had started, the core completed one OFF recovery | Neither hardware fault injection nor a successful Basic write; A0 covers the corresponding injected branches |
| A3: Basic scope loopback | With confirmed high-impedance CH1-to-CH1 and CH2-to-CH2 wiring, Sine/Square/Ramp/Pulse on CH1/CH2 all completed 2 kHz / 2 Vpp scope capture; both Square captures measured 25% duty, all eight quality gates passed, and both outputs finished OFF | Exact operating points complete; not extrapolated |
| Stable core and release-artifact sign-off | WaveBench `0.8.24` remains a development line; no final plugin wheel digest, implemented and verified conformance manifest, or release sign-off exists | Pending |

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

1. Implement and validate the conformance-manifest schema, digest checks, and current-distribution wheel
   ownership, then use a stable core and final plugin wheel to create and review that manifest.
2. Perform the actual release sign-off from the final artifacts and manifest.

Hardware fault injection beyond A3 needs separate authorization if it is ever required; the current C3 does not
substitute it for the minimal safety closure. This audit does not change `wavebench.toml`, connect to instruments,
or replace any recovery procedure.
