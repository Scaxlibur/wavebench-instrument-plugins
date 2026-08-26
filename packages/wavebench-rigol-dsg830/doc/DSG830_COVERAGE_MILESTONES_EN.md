# DSG830 Coverage Milestones

[中文](DSG830_COVERAGE_MILESTONES.md) · [Documentation](README_EN.md)

This document tracks model-specific delivery boundaries for `wavebench-rigol-dsg830`. It is used with the Core RF source-domain design and development milestones. It does not turn manual material, fake-transport tests, or seed code into real-device control claims. A standalone plugin checkout follows its package state and a matching Core checkout/version range; formal wheel acceptance also requires a released Core version.

## Target model and evidence rules

- `DSG830` is the only registered model. The DSG800 manual also covers DSG815, but that does not declare DSG815 compatibility.
- `0.1.0` is the historical transitional `kind="source"`, `source.idn` seed. Current `0.2.0` has migrated to `kind="rf_source"`. After A1 completion, its production descriptor declares `rf_source.idn` and `rf_source.snapshot`.
- Offline success proves parser, SCPI mapping, fake transport, and packaging boundaries only; it cannot promote a production descriptor capability.
- Production capabilities are promoted one A1–A5 item at a time, with recorded model, firmware, option, port, termination, and final RF-OFF state.
- Vendor-local material, real resources, serial numbers, raw responses, waveforms, screenshots, and experiment logs do not enter public documentation or artifacts.

## Status summary

| Stage | Status | Scope |
| --- | --- | --- |
| Seed | Offline complete | `*IDN?`, zero-I/O descriptor, packaging tests, one entry point, and vendor-local exclusion. |
| M0 | Offline complete; A1 complete | `rf_source`, `rf_out` topology, a strict snapshot parser, and production read-only status. |
| M1 | Offline in progress | OFF-only CW frequency/dBm configuration with independent readback; the production capability remains closed. |
| M2 | Not started | RF ON/OFF, safety preflight, and one-shot OFF recovery. |
| M3 | Not started | Declared internal-sine AM/FM/PM subset. |
| M4 | Not started | Declared Pulse and frequency-only Step Sweep subset. |
| A1–A5 | A1 complete; A2–A5 not started | A1 is read-only snapshot evidence; the remaining items need separately authorized controlled hardware evidence. |

## Seed: historical package boundary

The completed seed includes distribution metadata, license, one `wavebench.instruments` entry point, the WaveBench `0.8.24` seed dependency, `rigol.dsg830`/`DSG830`/PyVISA/USB/TCPIP metadata, `*IDN?` and `close()` fake tests, zero-I/O descriptor loading, vendor-local exclusion, and packaging checks.

It does not include an error queue, snapshot, frequency, power, RF output, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough. The current `[source]` configuration sample is for the historical identity seed only; it is not part of the normal source Vpp, channel, or run-plan workflow.

## M0: read-only RF migration

The prerequisite is met on the Core `0.8.25` development line: `rf_source` kind, descriptor extension, capability registry, `[rf_source]`, read-only Service/CLI/doctor, and the `rf_source.status` run path are available. That development line does not yet have an independent release tag.

The plugin has migrated its kind, capabilities, and config fields to `rf_source`; declares one `rf_out` port with `9 kHz–3 GHz`, `-110 dBm–20 dBm`, and a 50-ohm dBm reference; and adds a strict parser for `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. Fake-transport tests cover every query, normal values, unknown values, malformed responses, and protection-bit mapping. The connector label is not treated as actual termination. The wheel dependency and descriptor gate are both `>=0.8.25,<0.9`.

A1 has completed and been reviewed, so the production descriptor now declares `rf_source.idn` and `rf_source.snapshot`. Later M1–M4 capabilities remain in fake descriptors or offline driver tests until their respective hardware evidence is obtained.

## M1–M4 and A1–A5

- M1 now has an offline one-write `:FREQ`/`:LEV` mapping and independent readback contract while RF is OFF. Complete CLI, run-step, and offline acceptance work remains; A3 is still required before `rf_source.cw_configure` is production-declared.
- M2 is intended to add `:OUTP ON|OFF`, independent readback, per-port preflight, and at most one OFF recovery when session health permits. A2 is required before `rf_source.output` is production-declared.
- M3 is limited to a bounded internal-sine AM/FM/PM subset. A4 is required before production modulation capability.
- M4 is limited to declared Pulse and frequency-only Step Sweep subsets. External trigger, auxiliary output, reference clock, and synchronization require their own A4/A5 evidence.

Every hardware acceptance needs separate authorization. An unknown final RF-OFF state fails acceptance and cannot promote any capability.

### A1: completed package-specific read-only acceptance

A1 used a one-shot, non-production local evidence harness and has been reviewed. It must not temporarily alter the descriptor or use
`rf-source status` to bypass the then-current `rf_source.snapshot` gate. With an isolated TOML copy whose `[rf_source]` sets
`access = "read_only"`, a guarded single session may query only `*IDN?`, `:FREQ?`, `:LEV?`,
`:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. No retry, error queue,
RF-output switch, setter, or trigger is permitted. The harness itself does not perform network discovery; if discovery is needed, it must happen before acceptance through a bounded, separately authorized process, then be manually reviewed into the isolated TOML without entering the evidence.

Acceptance requires a successful parser, an explicitly OFF `rf_out`, a healthy closed session, and a guard audit
showing `read_only` with zero write counters. Keep only a redacted typed snapshot and audit summary; never keep a
resource, serial number, full IDN, raw response, or command log. An unknown/ON output, parser failure, or session
failure does not promote a capability and must not trigger automatic RF OFF in this read-only flow.

The isolated TOML must also contain an `[a1_evidence]` table used only by the harness: `port_id` is fixed to
`rf_out`; `actual_termination_ohm` must be a human-confirmed finite positive number; and `installed_options` must be
an already-confirmed, sorted, duplicate-free list of safe option identifiers. An explicitly confirmed absence of
options is recorded as an empty list. The harness extracts a restricted firmware token from the same `*IDN?`
response without adding a query. Missing options, termination, or either runtime distribution version metadata fails
before the transport is opened; unavailable firmware fails the evidence after the query. This table must not infer
actual termination from a connector label, scope coupling, or model name.

The source checkout retains `tools/a1_snapshot_evidence.py`, excluded from wheel and sdist, as the historical protocol and regression test. After the A1 promotion, it rejects a rerun with `production_snapshot_gate_changed` because the production descriptor now declares snapshot; it is not the current status-query entry point. The script does not create directories or edit configuration, and it never prints a resource, full IDN, raw response, or command log.
