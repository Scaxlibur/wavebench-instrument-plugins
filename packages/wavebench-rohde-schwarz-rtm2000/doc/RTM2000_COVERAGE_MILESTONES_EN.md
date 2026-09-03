# RTM2000 Feature-Coverage Development Roadmap

[中文](RTM2000_COVERAGE_MILESTONES.md)

> Type: Development

This page records development order, current blockers, and exit gates for future RTM2000 plugin
capabilities. It does not maintain the current capability list or replace acceptance evidence for a
specific device and version. The [production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py)
is authoritative for current capabilities. See the [coverage matrix](RTM2000_COVERAGE_MATRIX_EN.md)
for manual-domain mapping and the [development and acceptance archive](archive/RTM2000_README_0.15_EN.md)
for recorded hardware and negative evidence.

## Shared rules

- A new capability needs an accurate Core typed model before it enters the plugin descriptor.
- Option-dependent work checks identity and installed options before specialized queries. A missing
  option is not a plugin defect.
- A read-only method, Python method, or manual command does not constitute a production capability.
- Writes, acquisitions, and triggers are not blindly retried. Unknown state must fail and latch as
  required by the transaction contract.
- Setup blobs, persistent storage, network configuration, and global maintenance commands are not
  ordinary capabilities.
- Hardware acceptance applies only to the recorded model, firmware, transport, and procedure; it is
  not projected onto the full RTM2000 family.

## P1: basic oscilloscope and diagnostics

| Work item | Current development state | Next exit gate |
|---|---|---|
| Identity, options, non-consuming health | Implemented | New fields must still prove that they avoid consuming EVENT and error-queue reads. |
| CH1/CH2 analog channel, timebase, probe metadata | Implemented | New fields require strict parsing, a model boundary, and query-only hardware evidence. |
| Edge trigger | Query-only state and a minimal controlled CH2 configuration exist | Establish a complete transaction, restoration ownership, and model gate before adding sources or types. |
| Automatic measurement statistics | Query-only access to caller-confirmed slots exists | Buffer reads require a separate stopped precondition and hardware acceptance. |
| Waveform scaling and shape metadata | Implemented | Segment/history identity needs a separate model and must not reuse the fourth header field. |
| Channel display and multi-channel focus | Controlled V2 configuration is implemented | Add a joint baseline and restoration before position, offset, coupling, termination, or bandwidth writes. |

## P2: specialized acquisition and query-only analysis

| Work item | Current development state | Next exit gate |
|---|---|---|
| Average acquisition | Capability declared; transaction covered offline | Add independent hardware normal-path, failure-restoration, and fresh-session final-state evidence. |
| Segmented acquisition | Not implemented | Define segment identity, selection, data limits, artifacts, and restoration first. |
| History timestamps | Capability declared; a K15 query remains blocked in recorded evidence | Query only after option gating; never retry/clear after timeout or substitute frame number for time. |
| Math/FFT | Existing metadata/status capabilities declared | Review payload, expression, and accuracy separately; host DSP does not establish instrument capability. |
| Reference metadata | Capability declared; the valid-reference hardware gate remains open | Do not call update/save/load or overwrite user references merely to create evidence. |
| Cursor | Query-only readout declared | Keep configuration and positioning as a separate controlled write. |
| DVM/counter | Not implemented | Confirm options, source, type, state, and result models before a narrow query-only capability. |
| Probe safety integration | Basic metadata implemented | Define how identity and attenuation/impedance constrain safe input. |
| Digital waveform | Capability declared with offline coverage and controlled negative evidence | Use a stopped stable digital record to accept payload, bit order, and X-axis consistency with zero writes. |

## P3: option-dependent advanced applications

The following require independent capabilities, option gates, result models, and restoration rules
rather than expansion of the base scope API:

- spectrum and spectrogram;
- serial/parallel bus decode;
- protocol trigger and search;
- mask testing;
- power analysis.

Instrument filesystems, report export, state save/load, calibration, reset, network, and global
system configuration remain out of default scope. If required, they need a separate maintenance
workflow with path permissions, persistent-side-effect documentation, and human confirmation.

## Exit gate for each new capability

1. A Core typed model accurately represents device semantics or explicitly permits unavailable fields.
2. Driver behavior, descriptor declaration, configuration fields, and permissions agree.
3. Exact offline tests cover normal behavior, malformed responses, timeout, unknown outcome, and restoration failure.
4. Writes or triggers have snapshot, readback, restoration, independent verification, and required latching.
5. Option, model, transport, and resource limits are explicit; RTM2032 evidence is not family-wide evidence.
6. Controlled hardware acceptance writes conditions and results to Historical/evidence pages.
7. Chinese/English Current Reference, navigation, and the generated plugin catalog pass checks together.
