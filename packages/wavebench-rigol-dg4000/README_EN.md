# WaveBench RIGOL DG4000 Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the dual-channel RIGOL DG4202 and compatible DG4000 function/arbitrary waveform generators.

## Identity and compatibility

- Distribution: `wavebench-rigol-dg4000`
- Canonical driver ID: `rigol.dg4202`
- WaveBench: `>=0.8.25,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

This package uses the public `SourceChannelProfile` contract first available in WaveBench
`v0.8.15`, the `SourceSweepProfile` contract added in `v0.8.16`, the `SourceCounterProfile`
contract added in `v0.8.17`, and the Source V2 snapshot contract available in `v0.8.25`. It does
not run with a core older than `v0.8.25` and does not automatically claim compatibility with a
future `0.9` core.

The plugin defines no aliases. After installation, the explicit canonical ID `rigol.dg4202` selects the external implementation, while the short `dg4202` alias always selects WaveBench's built-in fallback. Removing the plugin also restores the built-in canonical implementation.

## Capabilities and boundaries

The driver supports identity/error queries, CH1/CH2 state, strict read-only channel profiles for
load, polarity, noise, sync, burst, modulation, marker, and pulse hold, strict read-only sweep
profiles for the frequency window, spacing, timing, trigger, and marker, a strict read-only global
counter profile for input configuration, statistics display, and conditional five-field
measurements, fixed frequency, function, VPP amplitude, square duty cycle, explicit output control,
query-only arbitrary-wave capability probes, and upload of validated DAC14 blocks through
WaveBench's public `DG4000DacBlock` contract. `source.snapshot_v2` adds typed read-only Basic,
output-enabled, Sweep, Pulse, Burst, and partial Harmonic facets for CH1/CH2; the Harmonic facet
does not claim per-order component readback.

WaveBench core retains waveform-file loading, normalization, DAC14 encoding, amplitude safety limits, services, run plans, state restoration, and artifacts. Descriptor import performs no instrument I/O, and default tests use only a fake transport. Writes and uploads are not retried blindly.

Version `0.7.0` adds a pure-query Source V2 adapter to the existing M1-M6 surface without declaring
any Source V2 write capability. It preserves the M1/M2/M4 transaction boundaries from `0.3.0`:
all I/O shares one reentrant lock;
fixed-wave writes use a pre-write snapshot, per-step readback, off-first recovery, and ambiguous-
write latching; DAC14 upload is accepted only while the target channel is already OFF, in FIX
mode, with sweep OFF. Overwriting the volatile USER waveform is reported as an irreversible side
effect. DG4202 firmware `00.01.14` has passed the M1-M5 CH1/CH2 hardware exit gates and the M6
counter-OFF gate. The M3, M5, and M6 profiles are read-only contexts: they do not widen core basic
restoration or promise restoration of load, polarity, noise, sync, burst, modulation, marker,
pulse hold, a complete sweep/counter profile, or volatile USER contents. No result is extrapolated
to another model, firmware, channel wiring, or the counter-ON measurement path.

The [DG4000 coverage matrix](doc/DG4000_COVERAGE_MATRIX_EN.md) maps vendor command domains to
current public APIs, offline/hardware evidence, and high-risk commands denied by default. The
[DG4000 coverage milestones](doc/DG4000_COVERAGE_MILESTONES_EN.md) define staged exit gates and
hardware-acceptance boundaries. The local vendor manual remains under ignored `doc/vendor-local/`
and is excluded from releases.

The Chinese README contains an RFC 5737 documentation resource. Never commit real resources, serial numbers, captures, screenshots, or command logs.

## License

This plugin is licensed under the [MIT License](LICENSE).

## Hardware acceptance boundary

An earlier controlled loop used external `wavebench-rigol-dg4000` to drive DG4202 CH1 with a 1 kHz, 1 Vpp sine wave and external `wavebench-rigol-ds1000z` to capture DS1104Z Plus CH1. Scope CH1 used AC coupling with fixed high-impedance input. A 1200-point DEF waveform measured 1000.000 Hz and 1.008 Vpp in WaveBench. Both instruments had clear error queues before and after the run, and the original generator CH1 state was restored in a `finally` path and verified by readback.

On 2026-07-27, current worktree behavior was reaccepted on DG4202 firmware `00.01.14`.
M1 completed one strict CH1/CH2 profile with 24 queries and zero writes. M2 separately exercised
OFF, temporary SQU/different fixed frequencies/0.8 Vpp/37% duty, explicit ON-to-OFF, off-first
restore, and fresh-session field verification on both channels. Both channels ended at their
original SIN, 1 kHz, 5 Vpp, 0 V offset, FIX, sweep OFF, output ON state.

M3 used external plugin `0.4.0` to read complete CH1 and CH2 channel profiles in one controlled
session. Transport guards turned any text or binary write into an immediate failure; acceptance
completed 45 queries, zero text writes, and zero binary writes. Both channels reported
high-impedance load, NORMAL polarity, noise OFF/10%, sync ON/POSITIVE, burst OFF, modulation
OFF/AM, marker OFF, and pulse hold DUTY, with all basic and context fields returned. The gate did
not read the error queue because consuming it would not be a side-effect-free observation.

M4 separately uploaded a 64-point little-endian DAC14 triangle to CH1 and CH2 while output was
OFF, read back USER/1 kHz/1 Vpp/0 V, verified clear error queues, and confirmed restoration in new
sessions. CH1 then explicitly drove a 2 Vpp triangle into a high-impedance RTM2032. A 10,000-point
capture measured 997.26 Hz and 2.16 Vpp; triangle-template RMSE was 0.0390 V, 49.2% of the
sine-template RMSE. After restoration, the original sine measured 998.25 Hz and 5.12 Vpp. CH2 was
then connected to the high-impedance RTM2032 CH2 input and completed an independent 1 kHz, 1 Vpp
triangle loop: measured frequency was 999.75 Hz, Vpp was 1.12 V, normalized triangle-template RMSE
was 0.09285, sine-template RMSE was 0.2196, and their ratio was 0.4229. The original DG4202 CH2
state was restored and the error queue was clear; scope timebase, range, and trigger settings were
unchanged across the gate. RTM2032 waveform fetch uses controlled transfer-format/point writes and
is not a zero-write scope session. Both uploads overwrite volatile USER data, an acknowledged
irreversible side effect. No real resource, serial number, raw waveform, or command log is stored.

M5 used external plugin `0.5.0` for query-only sweep-profile acceptance on CH1 and CH2. Both
channels initially had output ON, FIX mode, and sweep/burst/modulation/marker OFF. A controlled
staging session first disabled output and separately established sweep OFF and sweep ON. For each
state, a guarded read-only session read both channels three consecutive times. Each session issued
104 queries, zero text writes, and zero binary writes, and all six profiles matched field by field
within their preset state. The profile covers start/stop/center/span, linear/log/step spacing,
steps, sweep/hold/return timing, trigger source/slope/out, and marker. Any failed query or invalid
relationship rejects the whole profile. Staging and restoration writes were outside the two
zero-write read sessions. After restoration, both complete channel profiles and sweep profiles
matched their initial snapshots and the error queue was clear. No immediate trigger or `*TRG` was
sent, and no sweep-write capability was created.

M6 used external plugin `0.6.0` for non-destructive OFF-state acceptance of the DG4202's global
counter. The counter was OFF before and after the gate, statistics stayed OFF, the display stayed
DIGITAL, and three complete profiles matched field by field. The complete gate issued 39 queries,
zero text writes, and zero binary writes, returning AC coupling, 1 megaohm, 1X attenuation, USER1
gate time, HF rejection OFF, 0 V trigger level, and 50% sensitivity. The OFF state explicitly
returned `measurement=None`; the driver sent no `MEASure?`, did not enable the counter, and sent
neither `AUTO` nor `STATIstics:CLEAr`. Parsing and relationship validation for the counter-ON
frequency/period/duty/positive-width/negative-width tuple has offline evidence only and is not part
of this hardware conclusion.

On 2026-08-30, external plugin `0.7.0` completed read-only Source V2 acceptance for the current
instrument state. DG4202 firmware `00.01.14` reported CH1/CH2 OFF, SIN, 1 kHz, 5 Vpp, 0 V offset,
FIX, and sweep OFF. `source.snapshot_v2` completed 40 pure queries with matching before/after
anchors and healthy session state. Burst OFF was returned as a typed facet; Sweep, Pulse, and
Harmonic were `inactive_by_anchor`. Existing V1 transactions then staged both channels at PULSE,
1 Vpp, and output OFF. A second V2 snapshot completed 52 queries and returned DUTY hold, 500 us
width, 50% duty, 0 s delay, and 1.9531 us leading/trailing transitions on both channels. A fresh
final session confirmed both channels restored to OFF, SIN, 1 kHz, 5 Vpp, 0 V offset, and FIX.
No waveform was emitted and RTM2032 was not captured. Active Sweep, Burst ON, and Harmonic remain
outside this hardware evidence.

## Development checks

Run the package tests, Ruff, WaveBench package inspection, and a managed-install dry run from an
environment containing WaveBench `v0.8.25` or newer within the declared `<0.9` range.

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for daily source work. Formal acceptance still uses a real wheel and a disposable virtual environment.

## Provenance

- `0.1.0` migrated the vendor-protocol portion of WaveBench's built-in DG4202 driver while leaving services and safety policy in core.
- `0.2.0` adds the bilingual M0-M12 coverage plan and release-artifact leak prevention without expanding capabilities.
- `0.3.0` delivers strict current-API validation, transactional fixed-wave writes, and fail-closed DAC14 handling. DG4202 `00.01.14` passes M1/M2 and the M4 CH1 hardware gate; M4 CH2 passes protocol/restoration only. No capability is added.
- `0.4.0` requires WaveBench `>=0.8.15` and adds `source.channel_profile`. DG4202 `00.01.14`
  passes the strict zero-write M3 gate and complete M4 hardware gate on CH1/CH2 without widening
  automatic restoration or the capability surface.
- `0.5.0` requires WaveBench `>=0.8.16` and adds `source.sweep_profile`. DG4202 `00.01.14`
  passes three strict zero-write M5 rounds on CH1/CH2 in both sweep-OFF and sweep-ON preset states
  without adding a sweep setter, trigger, or automatic-restoration field.
- `0.6.0` requires WaveBench `>=0.8.17` and adds `source.counter_profile`. DG4202 `00.01.14`
  passes three strict zero-write M6 rounds with the counter OFF, without automatically enabling
  the counter, sending `AUTO`/statistics clear, or presenting offline-only counter-ON parsing as a
  hardware result.
- `0.7.0` requires WaveBench `>=0.8.25` and adds pure-query `source.snapshot_v2` with typed Basic,
  output-enabled, Sweep, Pulse, Burst, and partial Harmonic facets. The current OFF/SIN/FIX state
  passed a 40-query hardware read, and the output-OFF PULSE/1 Vpp state passed a 52-query read.
  Active Sweep, Burst ON, and Harmonic retain only prior V1 or offline evidence, and no matching
  write capability is declared.
