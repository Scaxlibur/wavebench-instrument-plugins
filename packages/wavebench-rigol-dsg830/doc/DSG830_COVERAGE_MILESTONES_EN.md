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
| M3 | A4 complete and promoted | Fixed internal-sine AM/FM/PM write sequences, strict readback, and Core configuration/mode-specific-disable transaction/CLI/run/artifact; production exposes `rf_source.modulation_configure` and `rf_source.modulation_disable`. PM is fixed to the `1.25 rad` production profile. |
| M3-MO | A4-MO complete and promoted | Profile-bound modulated-output special capability, one RF ON, strict dual snapshots, guarded OFF recovery, and fixed AM plus FM/PM DSG830 harnesses; production exposes AM `50 %` at `1 kHz`, FM `20 kHz` at `1 kHz`, and PM `1.25 rad` at `1 kHz`, all with maximum `-50 dBm`. |
| M4 (Pulse) | Offline complete; A4 Pulse passed | Internal/single Pulse period/width/polarity mapping, independent readback, Core transaction/CLI/run/artifact, and a local evidence harness; production exposes `rf_source.pulse_configure`. |
| M4 (Step Sweep) | A4 complete and promoted | Fixed `STEP`/`FWD`/`RAMP`/`LIN` frequency-only profile, strict readback, Core configuration transaction/CLI/run/artifact, and a local evidence harness; production exposes `rf_source.sweep_configure` while Sweep remains disabled. |
| A5-0 | Offline complete; not physical A5 evidence | Six fixed trigger-configuration queries, strict enum parsing, and the Core read-only Service/CLI/run/artifact; the production descriptor remains unchanged. |
| A5 (Pulse Output) | Passed and promoted | `:PULM:OUT:STAT?`/`:PULM:OUT:STAT ON|OFF` for `pulse_in_out` output, with Core Service/CLI/run/artifact and a local evidence harness; production exposes `rf_source.pulse_output`. |
| A1–A5 | A1, A2, A3, A4 modulation/Pulse/Step Sweep, A4-MO, and one A5 Pulse Output route complete | A1 promotes read-only snapshot, A2 per-port RF output, A3 OFF-only CW, and A4 separately promotes RF-OFF modulation, modulation disable, OFF-only Pulse, and disabled Step Sweep configuration. A4-MO promotes the three exact AM `50 %`/`1 kHz`, FM `20 kHz`/`1 kHz`, and PM `1.25 rad`/`1 kHz` modulated-output profiles. A5 promotes only the verified Pulse Output route; A5-0 does not promote a capability. |

## Seed: historical package boundary

The completed seed includes distribution metadata, license, one `wavebench.instruments` entry point, the WaveBench `0.8.24` seed dependency, `rigol.dsg830`/`DSG830`/PyVISA/USB/TCPIP metadata, `*IDN?` and `close()` fake tests, zero-I/O descriptor loading, vendor-local exclusion, and packaging checks.

It does not include an error queue, snapshot, frequency, power, RF output, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough. The current `[source]` configuration sample is for the historical identity seed only; it is not part of the normal source Vpp, channel, or run-plan workflow.

## M0: read-only RF migration

The prerequisite is met on the Core `0.8.25` development line: `rf_source` kind, descriptor extension, capability registry, `[rf_source]`, read-only Service/CLI/doctor, and the `rf_source.status` run path are available. That development line does not yet have an independent release tag.

The plugin has migrated its kind, capabilities, and config fields to `rf_source`; declares one `rf_out` port with `9 kHz–3 GHz`, `-110 dBm–20 dBm`, and a 50-ohm dBm reference; and adds a strict parser for `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. Fake-transport tests cover every query, normal values, unknown values, malformed responses, and protection-bit mapping. The connector label is not treated as actual termination. The wheel dependency and descriptor gate are both `>=0.8.25,<0.9`.

A1 has completed and been reviewed, so the production descriptor declares `rf_source.idn` and `rf_source.snapshot`. M2 A2 controlled-output evidence separately completed and promoted `rf_source.output`; M1 A3 CW-loopback evidence also completed and promoted `rf_source.cw_configure`; M3 modulation and M4 Pulse/Step Sweep A4 evidence separately promoted `rf_source.modulation_configure`, `rf_source.modulation_disable`, `rf_source.pulse_configure`, and `rf_source.sweep_configure`. M3-MO A4-MO evidence promoted AM `50 %` at `1 kHz`, FM `20 kHz` at `1 kHz`, and PM `1.25 rad` at `1 kHz`, all with maximum `-50 dBm` `rf_source.modulated_output_enable`. The bounded A5 Pulse Output evidence promoted `rf_source.pulse_output`.

## M1–M4 and A1–A5

- M1 has a one-write `:FREQ`/`:LEV` mapping, independent readback contract, Core CLI, run step, and redacted artifact while RF is OFF. A3 completed with independent source readback, a bounded low-power RF ON/OFF observation, visible CH2 signal, and confirmed final RF OFF. The production descriptor now declares `rf_source.cw_configure`; a `read_write` session still requires the complete OFF-only preflight before each single-field CW write.
- M2 has an offline `:OUTP ON|OFF` mapping, independent readback, per-port preflight, and at most one guarded same-port OFF recovery when session health permits. The driver sends exactly one output write and leaves preflight, readback, and recovery to Core. A2 completed and `rf_source.output` is production-declared; the separate A3 result promotes M1 CW, but not M3/M4 capabilities.
- M3 is complete for a bounded internal-sine AM/FM/PM subset. The offline driver accepts AM `0–100 %`, FM `0.1 Hz–1 MHz`, PM `0–5 rad`, and `10 Hz–100 kHz` internal frequency for every mode. The production descriptor keeps the verified profile: AM `0–100 %`, FM `0.1 Hz–1 MHz`, PM exactly `1.25 rad`, and `10 Hz–100 kHz` internal frequency. `get_rf_modulation_state()` reads only global/per-mode state for safe preflight, while the full target profile is read after configuration or when explicitly required. The driver uses fixed `INT`/`SINE` sequences and records the shared FM/PM selection separately from the queried profile. When all modes are disabled, preflight may observe a different inactive selection; the fixed write selects the requested type, and postcondition requires it. External source, non-Sine waveform, unknown modulation-condition bits, or mismatched postcondition readback fail closed. Core requires RF OFF, all AM/FM/PM modes disabled, Pulse/Sweep disabled, and no active protection condition; postcondition requires RF still OFF, exactly the target mode enabled, and global modulation enabled. No retry, RF enable, or output recovery occurs. `disable_rf_modulation()` only disables a requested mode and global modulation when RF is OFF and that mode is the only active mode; it independently reads back the disabled state, returns without a write for an already-consistent disabled state, and is production-declared after A4/A4-MO evidence. Ordinary RF ON still requires modulation disabled.
- M3-MO is an independent `rf_source.modulated_output_enable` special capability, not a relaxation of `rf_source.output`. It verifies one already-active internal-sine AM/FM/PM profile against an explicit `RfModulatedOutputProfile`; it does not configure or disable modulation. Its preflight requires RF OFF, enabled global modulation and only the target mode, exact source/waveform/value/internal-frequency readback, Pulse/Sweep OFF, clear protection, and complete per-port safety/termination conditions. It performs one `set_rf_output(..., enabled=True)` and then independently rereads RF and modulation snapshots. It never retries RF ON; only the existing one-shot guarded RF-OFF recovery is allowed when the result is uncertain. The DSG830 production descriptor exposes three exact profiles: AM `50 %` at `1 kHz`, FM `20 kHz` at `1 kHz`, and PM `1.25 rad` at `1 kHz`, all with maximum `-50 dBm`.
- The historical AM tool `tools/a4_modulated_output_evidence.py` remains in the checkout, together with a separate `tools/a4_fm_pm_modulated_output_evidence.py` and resource-free templates for FM/PM. The FM/PM tool adds exactly one in-memory profile per invocation: FM `20 kHz` deviation at `1 kHz` or PM `1.25 rad` deviation at `1 kHz`; both controlled cycles use RF `1 MHz` at `-50 dBm`. It requires an explicit 50-ohm CH2 declaration and records signal presence plus WaveBench waveform summary and FFT quality observations. Those observations do not measure FM deviation, PM deviation, modulation accuracy, or spectral compliance; sampling-quality warnings remain private evidence and do not replace DSG830's strict profile readback. Neither tool reads CH1 or controls/interprets LF OUTPUT, trigger/sync, or rear Pulse I/O. The AM, FM, and PM controlled cycles each completed with final RF/modulation OFF and healthy closure; their historical harnesses refuse reruns after promotion.
- M4 starts with Pulse, then addresses frequency-only Step Sweep. The completed Pulse subset is `rf_out` internal/single only: the driver fixes `:PULM:SOUR INT`, `:PULM:MODE SING`, period, width, and polarity, then ends with `:PULM:STAT OFF`. It never writes `:PULM:OUT`, invokes `:OUTP`, or sends a trigger. Core requires RF output, modulation, Pulse, and Sweep OFF with no active protection before and after the write, then independently reads source, mode, timing, polarity, and disabled Pulse state. No retry or recovery setter is sent after a failure.
- `tools/a4_pulse_evidence.py` and its resource-free template completed the controlled A4 Pulse acceptance. Static preflight requires a `read_only` RF configuration, disabled read retries, an exact production descriptor, and a reviewed 50-ohm termination. Normal and inverted polarity each completed one `--execute` configuration through an in-memory write descriptor, with independent readback and final RF/Pulse OFF; each successful path has 38 queries and 6 configuration writes. `--diagnose` keeps `read_only` with 22 queries and zero writes. Neither path reads scope, CH1/CH2, rear Pulse I/O, or trigger. After evidence review, `rf_source.pulse_configure` is production-declared and the historical harness rejects reruns.
- The production frequency-only Step Sweep subset accepts only start/stop frequency, points, and dwell, with a fixed `STEP`/`FWD`/`RAMP`/`LIN` profile. `get_rf_sweep_snapshot()` strictly reads type, direction, shape, spacing, start/stop frequency, points, dwell, and state; `configure_rf_sweep()` writes only those profile fields and ends with `:SWE:STAT OFF`. It never writes `:SWE:EXEC`, `*TRG`, any `:TRIG:*`, `:SWE:STAT FREQ`, Level Sweep, list setup, `:OUTP`, or rear-panel I/O. Core requires RF output, modulation, Pulse, and Sweep OFF with no active protection before and after the write, then independently reads the complete profile and requires Sweep to remain disabled. After A4 Step Sweep evidence, the production descriptor declares `rf_source.sweep_configure`; ordinary CLI and run requests still require `read_write`, a matching profile, and fresh OFF-only preflight.
- The source checkout includes `tools/a4_step_sweep_evidence.py` and `tools/a4_step_sweep_evidence.setup.template.toml`, both covered by offline regression and controlled hardware acceptance. Static preflight requires a separate `read_only` RF config, disabled read retries, the exact production descriptor, and a reviewed 50-ohm termination. `--diagnose` reads only initial/final RF snapshots and the complete Step Sweep profile, with 25 queries and zero writes on the successful path. Explicit `--execute` creates a bounded in-memory `read_write` descriptor and has 41 queries with 9 configuration writes on the successful path. Neither path reads scope, invokes RF output, arms/fires Sweep, or sends a trigger; evidence files use mode `0600`. Both paths passed with independent final confirmation that RF output, modulation, Pulse, and Sweep were disabled and no protection condition was active; the historical harness now rejects reruns.
- Except for the verified `PULSE IN/OUT` output route, Pulse trigger, Sweep execution/fire, physical external interfaces, auxiliary output, reference clock, synchronization, Level Sweep, and list control remain unimplemented. A5-0 only reads logical trigger configuration; it does not fire a trigger or define a physical connector. Fake descriptors may cover later trigger/fire transactions; production capabilities require their own A5 evidence.

Every hardware acceptance needs separate authorization. An unknown final RF-OFF state fails acceptance and cannot promote any capability.

### A5-0: logical trigger-configuration readback (offline complete)

`get_rf_trigger_snapshot()` queries, in fixed order, `:PULM:TRIG:MODE?`, `:PULM:TRIG:EXT:SLOP?`, `:PULM:TRIG:EXT:GATE:POL?`, `:SWE:MODE?`, `:SWE:SWE:TRIG:TYPE?`, and `:SWE:POIN:TRIG:TYPE?`. It parses Pulse trigger mode, external edge, external-gate polarity, Sweep mode, Sweep-period trigger, and Sweep-point trigger into closed enums; unknown responses fail closed. Every command is a query: the driver sends no setter, `*TRG`, `:TRIG:PULS`, `:TRIG:SWE`, `:SWE:EXEC`, `:PULM:OUT`, or RF-output write.

Core models this path as `rf_source.trigger_snapshot`, `wavebench rf-source trigger status --port PORT_ID`, and `rf_source.trigger_status`. It requires a `TRIGGER / READ` profile and is declared only by a non-production descriptor. `port_id` means the RF output whose behavior the logical settings govern; it is not a `TRIGGER IN`, `PULSE IN/OUT`, or sync connector. The DSG830 production descriptor declares neither this capability nor feature, so ordinary configuration rejects the operation before hardware I/O.

The source checkout provides `tools/a5_trigger_snapshot_evidence.py` and a resource-free setup template for the private zero-write diagnostic. Its default mode performs static preflight only; explicit `--diagnose` opens one exclusive session from the unchanged `read_only` configuration with read retries disabled. If the initial snapshot does not establish RF output, modulation, Pulse, and Sweep OFF with no active protection, it does not read trigger configuration. The successful path is an initial snapshot, six trigger queries, and a final snapshot: 22 queries and zero writes. Evidence files use mode `0600` and contain no resource, serial number, raw response, or command log. Static preflight is pinned to the reviewed current production capability list; a later capability change requires an explicit baseline update, fake regression, and a new zero-write diagnostic, otherwise the tool rejects before opening a session. The isolated diagnostic completed with final RF OFF and healthy closure verified; it is still not physical A5 hardware evidence or a capability promotion.

### A5: completed PULSE IN/OUT output acceptance; other physical interfaces remain unverified

The verified route is strictly DSG830 `PULSE IN/OUT` in the output direction to RTM2032 `EXT TRIGGER INPUT`. `TRIGGER IN`, Pulse input, sync/reference, and `rf_out` are distinct interfaces. Do not infer their electrical boundary from the CH2 50-ohm RF path.

The acceptance profile is fixed: DSG830 output `0 V`/`3.3 V`, about `600 ohms`, internal/single/normal, period `1 ms`, width `100 us`; the RTM receiver is `1 Mohm`/`12 pF`/`<= 150 Vp`. RF output, modulation, Pulse, and Sweep remain off with clear protection. The isolated harness reads scope trigger source and mode, temporarily performs an external/normal/single/auto sequence, and uses raw scope transport only for this physical acceptance. It changes neither the RTM driver nor its descriptor or production capability.

The successful sequence is Pulse Output ON, one scope single acquisition, then Pulse Output OFF. Audits recorded 97 RF-primary queries and 8 completed writes, 15 independent-final-RF queries and zero writes, plus 5 scope queries and 3 completed writes; final RF output and Pulse Output are independently confirmed OFF. The original source Pulse profile and scope acquisition state are not restored, so the scope can remain in `Single`. Evidence is private and redacted: no resource, serial number, raw response, command, or waveform enters public documentation or artifacts.

Core and the driver expose this narrow route as `rf_source.pulse_output`, `wavebench rf-source pulse-output --port PORT_ID --interface INTERFACE_ID on|off`, and corresponding run steps. Enable accepts only the named interface, direction, and fixed profile; disable permits known profile drift so that an already-enabled output can still be safely turned off. The operation does not enable RF output, configure the receiver, send trigger/fire, or retry an uncertain write. After evidence review, the production descriptor promotes only `rf_source.pulse_output`; the historical harness rejects reruns to prevent a temporary descriptor from bypassing the production boundary.

A5-0 remains a separate logical trigger-configuration zero-write read and the production descriptor still does not declare `rf_source.trigger_snapshot`. Any remaining A5 route must define its own wiring, direction, electrical profile, initial/restoration state, and success condition before new hardware evidence. Until then, do not write rear-panel configuration or send `*TRG`, `:TRIG:PULS`, `:TRIG:SWE`, or `:SWE:EXEC`.

### A4: AM/FM/PM passed and promoted

The source checkout retains `tools/a4_modulation_evidence.py`, its regression tests, and
`tools/a4_modulation_evidence.setup.template.toml` as the A4 acceptance protocol. This one-shot local harness is excluded from wheel and sdist. After promotion, it rejects a rerun so a temporary descriptor cannot bypass the current production-capability boundary.

The setup contains only `rf_out`, human-confirmed termination, confirmed options, `modulation_kind`, one matching mode value, and internal frequency. It contains no resource, serial number, raw response, or scope data. Controlled validation uses a separate `read_only` preflight and bounded `read_write` session; an uncertain write result or strict postcondition is never retried.

Controlled acceptance validates AM, FM, or PM one mode at a time: the initial RF snapshot must establish RF OFF with modulation/Pulse/Sweep disabled and no active protection; Core reads modulation state, performs one fixed mode-specific configuration sequence, independently reads it back, then performs the bounded disable transaction in a new recovery session. The final independent snapshot must establish both RF OFF and modulation disabled. The successful AM budget is 72 queries and 8 completed writes; FM/PM are 73 queries and 9 completed writes. Every write is a modulation-configuration or disable command: A4 does not call `set_rf_output()`, read scope, enable RF, or attempt output recovery.

With `--recover`, the harness only restores the one known active mode named in setup, or records a consistent already-disabled no-write result. With `--diagnose`, it retains the original `read_only` configuration and reads only the initial/final RF snapshots plus the selected complete profile. Both records are private `0600` records and are not new capability-promotion evidence.

Unknown or mismatched initial/postcondition/final RF-OFF state, mode/value/frequency mismatch, unknown write outcome, audit-budget mismatch, unhealthy session, or changed counters after close fails acceptance. Controlled validation passed AM, FM, and PM RF-OFF configuration/readback/disable sequences. PM is fixed to the `1.25 rad` production profile rather than extrapolating the wider offline mapping. The evidence proves only that one internal-Sine profile was configured, read back, and disabled while RF stayed OFF; it does not prove modulated RF output, CH2 signal, Pulse, Sweep, or trigger behavior.

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
