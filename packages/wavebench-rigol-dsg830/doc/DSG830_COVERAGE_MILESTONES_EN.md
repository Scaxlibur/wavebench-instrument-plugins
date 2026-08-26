# DSG830 Coverage Milestones

[中文](DSG830_COVERAGE_MILESTONES.md) · [Documentation](README_EN.md)

This document tracks model-specific delivery boundaries for `wavebench-rigol-dsg830`. It is used with the Core RF source-domain design and development milestones. It does not turn manual material, fake-transport tests, or seed code into real-device control claims. A standalone plugin checkout follows its package state and the matching released Core version.

## Target model and evidence rules

- `DSG830` is the only registered model. The DSG800 manual also covers DSG815, but that does not declare DSG815 compatibility.
- `0.1.0` is the historical transitional `kind="source"`, `source.idn` seed. Current `0.2.0` has migrated to `kind="rf_source"`, but its production descriptor still declares only `rf_source.idn`.
- Offline success proves parser, SCPI mapping, fake transport, and packaging boundaries only; it cannot promote a production descriptor capability.
- Production capabilities are promoted one A1–A5 item at a time, with recorded model, firmware, option, port, termination, and final RF-OFF state.
- Vendor-local material, real resources, serial numbers, raw responses, waveforms, screenshots, and experiment logs do not enter public documentation or artifacts.

## Status summary

| Stage | Status | Scope |
| --- | --- | --- |
| Seed | Offline complete | `*IDN?`, zero-I/O descriptor, packaging tests, one entry point, and vendor-local exclusion. |
| M0 | Offline complete; awaiting A1 | `rf_source`, `rf_out` topology, and a strict snapshot parser; production remains identity only. |
| M1 | Not started | OFF-only CW frequency/dBm configuration with independent readback. |
| M2 | Not started | RF ON/OFF, safety preflight, and one-shot OFF recovery. |
| M3 | Not started | Declared internal-sine AM/FM/PM subset. |
| M4 | Not started | Declared Pulse and frequency-only Step Sweep subset. |
| A1–A5 | Not started | Separately authorized controlled hardware evidence. |

## Seed: historical package boundary

The completed seed includes distribution metadata, license, one `wavebench.instruments` entry point, the WaveBench `0.8.24` seed dependency, `rigol.dsg830`/`DSG830`/PyVISA/USB/TCPIP metadata, `*IDN?` and `close()` fake tests, zero-I/O descriptor loading, vendor-local exclusion, and packaging checks.

It does not include an error queue, snapshot, frequency, power, RF output, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough. The current `[source]` configuration sample is for the historical identity seed only; it is not part of the normal source Vpp, channel, or run-plan workflow.

## M0: read-only RF migration

The prerequisite is met on the Core `0.8.25` development line: `rf_source` kind, descriptor extension, capability registry, `[rf_source]`, read-only Service/CLI/doctor, and the `rf_source.status` run path are available. That development line does not yet have an independent release tag.

The plugin has migrated its kind, capabilities, and config fields to `rf_source`; declares one `rf_out` port with `9 kHz–3 GHz`, `-110 dBm–20 dBm`, and a 50-ohm dBm reference; and adds a strict parser for `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`, `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`. Fake-transport tests cover every query, normal values, unknown values, malformed responses, and protection-bit mapping. The connector label is not treated as actual termination. The wheel dependency and descriptor gate are both `>=0.8.25,<0.9`.

After offline M0, the production descriptor declares only `rf_source.idn` until A1. `rf_source.snapshot` waits for A1; later M1–M4 capabilities remain in fake descriptors or offline driver tests.

## M1–M4 and A1–A5

- M1 implements one-write, independently read-back `:FREQ` and `:LEV` mapping while RF is OFF. A3 is required before `rf_source.cw_configure` is production-declared.
- M2 implements `:OUTP ON|OFF`, independent readback, per-port preflight, and at most one OFF recovery when session health permits. A2 is required before `rf_source.output` is production-declared.
- M3 reviews only a bounded internal-sine AM/FM/PM subset. A4 is required before production modulation capability.
- M4 reviews only declared Pulse and frequency-only Step Sweep subsets. External trigger, auxiliary output, reference clock, and synchronization require their own A4/A5 evidence.

Every hardware acceptance needs separate authorization. An unknown final RF-OFF state fails acceptance and cannot promote any capability.
