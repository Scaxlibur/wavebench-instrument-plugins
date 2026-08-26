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
| M1 | Offline complete; A3 complete | OFF-only CW frequency/dBm configuration, independent readback, and production `rf_source.cw_configure`. |
| M2 | Offline complete; A2 complete | One-write RF ON/OFF mapping, Core safety preflight, independent readback, and one-shot OFF recovery; production exposes `rf_source.output`. |
| M3 | Offline complete; A4 controlled validation in progress, not yet accepted | Fixed internal-sine AM/FM/PM write sequences, strict readback, and Core configuration transaction/CLI/run/artifact; mode-specific disable is only for local evidence/private recovery, and production capability remains closed. |
| M4 | Not started | Declared Pulse and frequency-only Step Sweep subset. |
| A1–A5 | A1, A2, and A3 complete; A4 has no qualifying evidence; A5 is not started | A1 promotes read-only snapshot, A2 per-port RF output, and A3 OFF-only CW. |

## Seed: historical package boundary

The completed seed includes distribution metadata, license, one `wavebench.instruments` entry point, the WaveBench `0.8.24` seed dependency, `rigol.dsg830`/`DSG830`/PyVISA/USB/TCPIP metadata, `*IDN?` and `close()` fake tests, zero-I/O descriptor loading, vendor-local exclusion, and packaging checks.

It does not include an error queue, snapshot, frequency, power, RF output, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough. The current `[source]` configuration sample is for the historical identity seed only; it is not part of the normal source Vpp, channel, or run-plan workflow.

## M0: read-only RF migration

The prerequisite is met on the Core `0.8.25` development line: `rf_source` kind, descriptor extension, capability registry, `[rf_source]`, read-only Service/CLI/doctor, and the `rf_source.status` run path are available. That development line does not yet have an independent release tag.

The plugin has migrated its kind, capabilities, and config fields to `rf_source`; declares one `rf_out` port with `9 kHz–3 GHz`, `-110 dBm–20 dBm`, and a 50-ohm dBm reference; and adds a strict parser for `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. Fake-transport tests cover every query, normal values, unknown values, malformed responses, and protection-bit mapping. The connector label is not treated as actual termination. The wheel dependency and descriptor gate are both `>=0.8.25,<0.9`.

A1 has completed and been reviewed, so the production descriptor declares `rf_source.idn` and `rf_source.snapshot`. M2 A2 controlled-output evidence separately completed and promoted `rf_source.output`; M1 A3 CW-loopback evidence also completed and promoted `rf_source.cw_configure`. M3/M4 capabilities remain in fake descriptors or offline driver tests until their respective hardware evidence is obtained.

## M1–M4 and A1–A5

- M1 has a one-write `:FREQ`/`:LEV` mapping, independent readback contract, Core CLI, run step, and redacted artifact while RF is OFF. A3 completed with independent source readback, a bounded low-power RF ON/OFF observation, visible CH2 signal, and confirmed final RF OFF. The production descriptor now declares `rf_source.cw_configure`; a `read_write` session still requires the complete OFF-only preflight before each single-field CW write.
- M2 has an offline `:OUTP ON|OFF` mapping, independent readback, per-port preflight, and at most one guarded same-port OFF recovery when session health permits. The driver sends exactly one output write and leaves preflight, readback, and recovery to Core. A2 completed and `rf_source.output` is production-declared; the separate A3 result promotes M1 CW, but not M3/M4 capabilities.
- M3 is offline-complete for a bounded internal-sine AM/FM/PM subset. AM is `0–100 %`, FM is `0.1 Hz–1 MHz`, PM is `0–5 rad`, and every mode uses a `10 Hz–100 kHz` internal frequency. `get_rf_modulation_state()` reads only global/per-mode state for safe preflight, while the full target profile is read after configuration or when explicitly required. The driver uses fixed `INT`/`SINE` sequences and records the shared FM/PM selection separately from the queried profile. When all modes are disabled, preflight may observe a different inactive selection; the fixed write selects the requested type, and postcondition requires it. External source, non-Sine waveform, unknown modulation-condition bits, or mismatched postcondition readback fail closed. Core requires RF OFF, all AM/FM/PM modes disabled, Pulse/Sweep disabled, and no active protection condition; postcondition requires RF still OFF, exactly the target mode enabled, and global modulation enabled. No retry, RF enable, or output recovery occurs. `disable_rf_modulation()` only disables a requested mode and global modulation when RF is OFF and that mode is the only active mode; it independently reads back the disabled state, returns without a write for an already-consistent disabled state, and is used only by local A4 evidence/recovery. A4 is still required before a production modulation capability.
- M4 is limited to declared Pulse and frequency-only Step Sweep subsets. External trigger, auxiliary output, reference clock, and synchronization require their own A4/A5 evidence.

Every hardware acceptance needs separate authorization. An unknown final RF-OFF state fails acceptance and cannot promote any capability.

### A4: controlled validation in progress, no qualifying evidence yet

The source checkout now contains `tools/a4_modulation_evidence.py`, its regression tests, and
`tools/a4_modulation_evidence.setup.template.toml`. This one-shot local harness is excluded from wheel and sdist;
the production descriptor still does not declare modulation capability before A4.

Static preflight requires a `read_only` RF configuration with retries disabled, exact driver/model/current-production
capability matching, and a setup containing only `rf_out`, human-confirmed termination, confirmed options,
`modulation_kind`, one matching mode value, and internal frequency. The setup contains no resource, serial number,
raw response, or scope data. The harness adds the complete internal-Sine modulation profile plus
`rf_source.modulation_configure` and `rf_source.modulation_disable` only in memory; it never registers, writes back,
or promotes that descriptor.

With `--execute`, one invocation validates AM, FM, or PM only: the initial RF snapshot must establish RF OFF with
modulation/Pulse/Sweep disabled and no active protection; Core reads modulation state, performs one fixed mode-specific
configuration sequence, independently reads it back, then performs the bounded disable transaction for that same mode.
The final independent snapshot must establish both RF OFF and modulation disabled. The successful AM budget is 72
queries and 8 completed writes; FM/PM are 73 queries and 9 completed writes. Every write is a modulation-configuration
or disable command: A4 does not call `set_rf_output()`, read scope, enable RF, or attempt output recovery.

With `--recover`, the harness only restores the one known active mode named in setup, or records a consistent
already-disabled no-write result. It requires the same RF-OFF safety preconditions and creates a private `0600` recovery
record; that record is not A4 capability-promotion evidence.

Unknown or mismatched initial/postcondition/final RF-OFF state, mode/value/frequency mismatch, unknown write outcome,
audit-budget mismatch, unhealthy session, or changed counters after close fails acceptance. Controlled validation has
not produced a qualifying record for `rf_source.modulation_configure`, so the production descriptor remains closed.
Even after a future successful A4 run, the evidence would prove only that one internal-Sine profile was configured, read
back, and disabled while RF stayed OFF; it would not prove modulated RF output, CH2 signal, Pulse, Sweep, or trigger behavior.

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

### A2: completed controlled RF-output acceptance

The controlled hardware sequence completed and was reviewed: initial RF OFF, one RF ON, independent readback, supplementary CH1/CH2 scope observation, one RF OFF, and independent readback all succeeded. The evidence records model, a restricted firmware token, options, port, physical termination, final RF OFF, session closure, and guard audit; the public status contains no resource, serial number, raw response, command, or waveform. CH1/CH2 observation is supplementary and does not replace typed RF readback.

The source checkout contains `tools/a2_output_evidence.py`, a one-shot local harness excluded from wheel and sdist. It never changes the production descriptor. It requires three local inputs: a read-only RF TOML, a read-only scope TOML, and a resource-free A2 setup TOML. The public template is `tools/a2_output_evidence.setup.template.toml`. The setup fixes `rf_out` and records the reviewed physical termination, installed options, frequency range, low-power limit, and CH1/CH2 observation conditions; its power limit must be no higher than `-40 dBm`.

Without `--execute`, the harness performs static preflight only: it opens no transport and writes no instrument. With an explicit `--execute` and a new local `--output` file, it creates a bounded in-memory `read_write` configuration and an in-memory descriptor containing only `rf_source.output`. The RF config must start as `read_only` with query retries disabled. The scope config must also start as `read_only`, with error draining and retries disabled, and must identify a resource different from the RF source. The harness creates a redacted JSON evidence file with mode `0600`; it creates no directories and prints no resource, full IDN, raw response, SCPI command, or waveform.

The primary sequence is an initial snapshot, one RF ON, independent readback, optional scope observation, one RF OFF, and independent readback. An initially ON or unknown RF-output state fails A2; if the session is healthy and no RF-OFF transaction has started, the harness requests one bounded RF OFF to reduce residual-output risk. For an unverified RF-ON result, Core owns at most one authorized OFF recovery. The harness accepts the final OFF condition only when that recovery independently verifies OFF. Once an RF-OFF transaction begins, an unverified result is not retried by the harness.

Scope observation requires `--observe-scope`. It reads the current `DEF` buffer on CH1 and CH2 at most once per channel and does not issue `SINGle`, trigger, or autoscale. CH2 50-ohm input requires the separate `allow_ch2_50ohm = true` setup declaration. Scope fetch may change channel-display and waveform-transfer fields, which the harness records as unrestored. A missing high-frequency CH2 waveform and the low-frequency CH1 auxiliary observation are warnings only. They do not replace typed RF readback or final-OFF verification, and do not prove a control relationship between RF and LF outputs.

The `passed` record, confirmed final RF OFF, and review of redacted evidence have added `rf_source.output` to the production descriptor. The historical harness now rejects reruns with `production_output_gate_changed`; ordinary output control must use the production descriptor, `read_write` access, and complete per-port safety configuration.

### A3: completed CW-loopback acceptance

The checkout retains `tools/a3_cw_evidence.py`, its regression tests, and the resource-free
`tools/a3_cw_evidence.setup.template.toml`. The controlled sequence has completed and been reviewed: initial RF OFF,
one OFF-only frequency write with independent source readback, one OFF-only power write with independent source
readback, a bounded low-power RF ON/OFF observation, visible signal in the current CH2 buffer, and confirmed final
RF OFF. The redacted audit records four completed writes, 72 queries, and healthy session closure. The selected
frequency and power remain at the declared test point after the run; RF output is independently confirmed OFF.

CH2's 50-ohm input is an explicit electrical-safety precondition. Its observation only establishes visible signal;
source readback remains the frequency and dBm-power evidence, with no dBm-to-Vpp conversion or scope-frequency
substitution. The CH1 LF connection is a separate port and is neither read nor controlled by A3. After promotion, the
historical harness rejects reruns with `production_cw_gate_changed`; ordinary CW control uses the production
descriptor, `read_write` access, and the Core OFF-only preflight.
