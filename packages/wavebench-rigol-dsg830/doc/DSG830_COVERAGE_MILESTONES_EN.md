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
| M1 | Offline complete | OFF-only CW frequency/dBm configuration with independent readback; the production capability remains closed. |
| M2 | Offline complete | One-write RF ON/OFF mapping, Core safety preflight, independent readback, and one-shot OFF recovery; the production capability remains closed. |
| M3 | Not started | Declared internal-sine AM/FM/PM subset. |
| M4 | Not started | Declared Pulse and frequency-only Step Sweep subset. |
| A1–A5 | A1 complete; A2 harness and regression tests complete, hardware evidence pending; A3–A5 not started | A1 is read-only snapshot evidence; the remaining items need separately authorized controlled hardware evidence. |

## Seed: historical package boundary

The completed seed includes distribution metadata, license, one `wavebench.instruments` entry point, the WaveBench `0.8.24` seed dependency, `rigol.dsg830`/`DSG830`/PyVISA/USB/TCPIP metadata, `*IDN?` and `close()` fake tests, zero-I/O descriptor loading, vendor-local exclusion, and packaging checks.

It does not include an error queue, snapshot, frequency, power, RF output, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough. The current `[source]` configuration sample is for the historical identity seed only; it is not part of the normal source Vpp, channel, or run-plan workflow.

## M0: read-only RF migration

The prerequisite is met on the Core `0.8.25` development line: `rf_source` kind, descriptor extension, capability registry, `[rf_source]`, read-only Service/CLI/doctor, and the `rf_source.status` run path are available. That development line does not yet have an independent release tag.

The plugin has migrated its kind, capabilities, and config fields to `rf_source`; declares one `rf_out` port with `9 kHz–3 GHz`, `-110 dBm–20 dBm`, and a 50-ohm dBm reference; and adds a strict parser for `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. Fake-transport tests cover every query, normal values, unknown values, malformed responses, and protection-bit mapping. The connector label is not treated as actual termination. The wheel dependency and descriptor gate are both `>=0.8.25,<0.9`.

A1 has completed and been reviewed, so the production descriptor now declares `rf_source.idn` and `rf_source.snapshot`. Later M1–M4 capabilities remain in fake descriptors or offline driver tests until their respective hardware evidence is obtained.

## M1–M4 and A1–A5

- M1 has an offline one-write `:FREQ`/`:LEV` mapping, independent readback contract, Core CLI, run step, and redacted artifact while RF is OFF. The production descriptor still lacks `rf_source.cw_configure`, so the CLI and run step cannot operate a live DSG830. Fake/guarded-transport acceptance does not promote a production capability; A3 is still required before `rf_source.cw_configure` is production-declared.
- M2 has an offline `:OUTP ON|OFF` mapping, independent readback, per-port preflight, and at most one guarded same-port OFF recovery when session health permits. The driver sends exactly one output write and leaves preflight, readback, and recovery to Core. A2 is required before `rf_source.output` is production-declared.
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

### A2: controlled RF-output evidence (harness implemented; hardware evidence pending)

The source checkout contains `tools/a2_output_evidence.py`, a one-shot local harness excluded from wheel and sdist. It never changes the production descriptor. It requires three local inputs: a read-only RF TOML, a read-only scope TOML, and a resource-free A2 setup TOML. The public template is `tools/a2_output_evidence.setup.template.toml`. The setup fixes `rf_out` and records the reviewed physical termination, installed options, frequency range, low-power limit, and CH1/CH2 observation conditions; its power limit must be no higher than `-40 dBm`.

Without `--execute`, the harness performs static preflight only: it opens no transport and writes no instrument. With an explicit `--execute` and a new local `--output` file, it creates a bounded in-memory `read_write` configuration and an in-memory descriptor containing only `rf_source.output`. The RF config must start as `read_only` with query retries disabled. The scope config must also start as `read_only`, with error draining and retries disabled, and must identify a resource different from the RF source. The harness creates a redacted JSON evidence file with mode `0600`; it creates no directories and prints no resource, full IDN, raw response, SCPI command, or waveform.

The primary sequence is an initial snapshot, one RF ON, independent readback, optional scope observation, one RF OFF, and independent readback. An initially ON or unknown RF-output state fails A2; if the session is healthy and no RF-OFF transaction has started, the harness requests one bounded RF OFF to reduce residual-output risk. For an unverified RF-ON result, Core owns at most one authorized OFF recovery. The harness accepts the final OFF condition only when that recovery independently verifies OFF. Once an RF-OFF transaction begins, an unverified result is not retried by the harness.

Scope observation requires `--observe-scope`. It reads the current `DEF` buffer on CH1 and CH2 at most once per channel and does not issue `SINGle`, trigger, or autoscale. CH2 50-ohm input requires the separate `allow_ch2_50ohm = true` setup declaration. Scope fetch may change channel-display and waveform-transfer fields, which the harness records as unrestored. A missing high-frequency CH2 waveform and the low-frequency CH1 auxiliary observation are warnings only. They do not replace typed RF readback or final-OFF verification, and do not prove a control relationship between RF and LF outputs.

The A2 production gate remains closed. Only a `passed` record with confirmed final RF OFF and a review of redacted evidence may add `rf_source.output` to the production descriptor.
