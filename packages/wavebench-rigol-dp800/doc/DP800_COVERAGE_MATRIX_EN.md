# DP800 Programming-Manual Coverage Matrix

[中文](DP800_COVERAGE_MATRIX.md)

## Purpose, scope, and accounting rules

This matrix compares the locally retained RIGOL DP800 programming manual with the public
capabilities, actual SCPI, offline tests, and recorded DP832A LAN evidence of the external
`wavebench-rigol-dp800` plugin. It distinguishes commands documented by the manual from commands
actually exposed and accepted through the current plugin. A documented command, a Python method,
or acceptance of a neighboring command in the same subsystem does not imply complete coverage.

The audit source is the RIGOL DP800 Series Programming Guide, document `PGH03008-1110`, dated
`2015-12`. Its 17,525-line Markdown transcription is stored under the Git-ignored
`doc/vendor-local/` directory and is excluded from commits, wheels, and sdists. The manual covers
multiple DP800 models, A and non-A variants, channel counts, ranges, and options. Model-specific
limits and option availability are therefore not extrapolated to the DP832A, and DP832A evidence is
not extrapolated to the entire family.

Following the manual's command-system table of contents, this matrix audits 22 domains: 21 named
vendor/status subsystems (`ANALyzer`, `APPLy`, `DELAY`, `DISPlay`, `INITiate`, `INSTrument`, `LIC`,
`MEASure`, `MEMory`, `MMEMory`, `MONItor`, `OUTPut`, `PRESet`, `RECAll`, `RECorder`, `SOURce`,
`STATus`, `STORe`, `SYSTem`, `TIMEr`, and `TRIGger`) plus IEEE 488.2 common commands. Set/query
forms, optional keywords, abbreviations, and aliases are not separate completion units, so this
document does not publish a pseudo-precise percentage.

The current external plugin is version `0.3.0` and declares six capabilities: `power.idn`,
`power.status`, `power.measurement`, `power.set_voltage_current_limit`, `power.output`, and
`power.protection`. It is a narrow power-supply driver governed by safety policy, not a general
DP800 SCPI shell.

Coverage labels:

- **External hardware accepted**: current external implementation, targeted offline tests, and
  controlled DP832A evidence all exist.
- **Implemented / offline verified**: code and exact FakeTransport tests exist, without external
  hardware evidence for that detail.
- **Partially covered**: only a narrow subset of the command domain is exposed publicly.
- **Not covered**: the manual documents the command, but the plugin exposes no corresponding method
  or capability.
- **Denied by default**: the command directly changes output, triggers an action, clears protection,
  resets or recalls state, changes connectivity, or writes persistent data.

See the [DP800 command coverage development milestones](DP800_COVERAGE_MILESTONES_EN.md) for each
stage's public capabilities, exact commands, safety contract, and hardware acceptance gate.

## Functional coverage matrix

| Domain | Manual command surface | Current public coverage | Evidence | Main gap and safety boundary | Recommendation |
|---|---|---|---|---|---|
| Identity and error queue | `*IDN?`, `:SYSTem:ERRor?`, `:SYSTem:VERSion?` | `power.idn`; mutating calls may consume the error queue afterwards | **External hardware accepted**; exact offline queries | `errors()` consumes queue entries; no structured model/firmware or non-consuming health API | Keep queue semantics explicit and evidence redacted |
| IEEE 488.2 status, synchronization, reset, and trigger | `*CLS`, `*ESE/*ESR?`, `*OPC?`, `*RST`, `*SRE/*STB?`, `*TRG`, `*TST?`, `*WAI` | Nothing except `*IDN?` | **Denied by default / not covered** | Reset changes the entire instrument; trigger can change output; clear/event reads mutate status; synchronization is not modeled | Consider only a narrow non-consuming health snapshot; keep reset and trigger in manual maintenance workflows |
| Basic setpoints | `:APPLy` / `:APPLy?` | `power.status` reads rating, voltage, and current setpoints; `power.set_voltage_current_limit` snapshots, writes one `:APPL`, verifies readback, and restores on failure | **External hardware accepted**: three-channel DP832A reads, a distinct-target CH1 write/restore, and fault injection for `APPLy` readback mismatch and ambiguous restoration | Reads reject non-finite values, unknown models, and invalid channels; the manual-defined two-field response to targetless single-channel `:APPL?` is covered offline but remains hardware-unverified, and no rating is guessed; ambiguous writes or unverifiable restoration latch configuration writes for that driver instance | Accept other models individually |
| Live measurement | `:MEASure:ALL?`, voltage, current, and power scalar queries | `power.measurement` uses one `:MEAS:ALL? CH<n>`; `power.status` reuses it | **External hardware accepted** on all three DP832A channels; finite/count offline gates pass | Scalar queries are not exposed; measurement accuracy is not claimed | Preserve one ALL snapshot; accept accuracy separately |
| Output state and CV/CC mode | `:OUTPut[:STATe]?`, `:OUTPut:CVCC?` / `:OUTPut:MODE?` | `power.status` queries output and regulation mode | **External hardware accepted** on three DP832A channels; strict `ON/OFF` and `CV/CC/UR` offline gates pass | Actual mode responses on other models remain unverified | Continue to fail closed on unknown enums; add per-model evidence |
| Explicit output control | `:OUTPut[:STATe] [CH<n>,]ON|OFF` | `power.output` snapshots state, writes once, verifies readback, and forces OFF on failure | **External hardware accepted**: unloaded CH1 ON/OFF, final all channels OFF, and fault injection for an ambiguous first output write | Directly affects the DUT; an ambiguous write or unverifiable OFF recovery latches configuration writes, and the driver never retries ON blindly | Keep a separate explicit capability; accept other models individually |
| OVP/OCP state and thresholds | `:OUTPut:OVP/OCP[:STATe]`, `:VALue`, and `:QUES?`/`:ALAR?` | `power.protection` snapshots enable, threshold, and trip fields; ordered writes are verified and configuration is restored on failure | **External hardware accepted**: three-channel DP832A reads, CH1 write/restore, and fault injection for failures on the second and third transaction writes | A new trip is never cleared during recovery; ambiguous writes, changed trip state, or unverifiable restoration latch configuration writes; ALAR alias remains unverified and the core owns relationship checks | Accept other models and the ALAR alias individually |
| Clear OVP/OCP | `:OUTPut:OVP:CLEAR`, `:OUTPut:OCP:CLEAR`; `SOURce:*:PROTection:CLEar` can also re-enable output | Not exposed | **Denied by default** | Clearing a trip is destructive; the SOURce clear side effect is especially hazardous | Consider only an explicit recovery flow after fault removal and target output state are confirmed |
| `SOURce` voltage/current and protection aliases | Immediate level, step, triggered level, protection, and range | No independent API; immediate setpoints and protection use APPLy/OUTPut paths | **Partially covered** | No step, triggered level, DP811 range, or protection clear; aliases do not count twice | Keep explicit-channel paths; expand only if independent voltage/current transactions are needed |
| Range, Sense, and tracking | `:OUTPut:RANGe`, `:OUTPut:SENSe`, `:OUTPut:TRACk` | Not exposed | **Not covered** | Model/channel-specific; range changes limits, Sense requires remote wiring, and tracking couples channels | **P2:** option/model-gated query-only profile first; writes require wiring confirmation and multi-channel restore |
| Timed output | `:TIMEr:*`, `:OUTPut:TIMEr*` | Not exposed | **Not covered / start denied by default** | Tables, templates, and run state change real output over time; current scalar snapshots cannot restore them | **P2:** bounded query-only profile first; execution needs a plan, timeout, stop, and restore |
| Delay output | `:DELAY:*` | Not exposed | **Not covered / start denied by default** | Conditions, cycles, and terminal state can change output | Model separately from timer; do not execute without complete snapshot and finally-stop behavior |
| Monitor | `:MONItor:*` | Not exposed | **Not covered** | Conditions and stop actions can turn outputs off or signal alarms; option-dependent on non-A models | **P2:** option-gated query-only status first; writes must integrate output recovery |
| Trigger input/output and triggered supply actions | `:TRIGger:*`, `:INITiate`, `*TRG`, trigger coupling | Not exposed | **Denied by default** | Can change trigger V/I, switch outputs, drive digital ports, or couple channels | Requires a trigger topology, electrical limits, complete snapshot, and human confirmation |
| Channel selection | `:INSTrument:NSELect` / `:SELect` | Deliberately unused; every current command carries `CH<n>` | **Intentionally not covered** | Changing current channel introduces hidden global state | Preserve explicit channels rather than shortening SCPI through mutable current-channel state |
| Recorder | `:RECorder:*` | Not exposed | **Not covered / start-stop denied by default** | Stop writes an internal/external file; period, destination, and storage lifecycle are unmodeled | **P3:** query-only destination/period/state first, then bounded artifact export |
| Analyzer | `:ANALyzer:*` | Not exposed | **Not covered** | Depends on a valid recorded file and options; selecting files/windows/object then running analysis mutates state | Consider query-only result/value only after recorder lifecycle is defined |
| Internal state and user presets | `:MEMory:*`, `:PRESet:*`, local recall/store, `*SAV/*RCL` | Not exposed | **Denied by default** | Saves, overwrites, locks, deletes, or recalls persistent whole-instrument state and may alter all outputs | Use host-side snapshots; do not substitute instrument slots for experiment transactions |
| External storage | `:MMEMory:*`, external recall/store | Not exposed | **Denied by default** | Paths, creation, deletion, overwrite, and load are persistent and media-dependent | Exclude from ordinary plugin unless path sandboxing and explicit permissions are designed |
| Display and front panel | `:DISPlay:*`, brightness/contrast/RGB/saver, lock/local/remote | Not exposed | **Not covered / writes denied by default** | Global UI changes and lock/remote can impede human takeover | Consider read-only status only when diagnostically useful; measurement flows must not change UI |
| System diagnostics and status registers | self-test, SCPI version, `:STATus:QUEStionable:*` | Not exposed | **Not covered** | Some event reads clear bits; self-test conditions and latency are undefined | Start with a non-consuming condition/version snapshot and document event side effects |
| Network, serial, GPIB, and global system settings | `:SYSTem:COMMunicate:*`, language, power-on, OTP, ON/OFF sync, track mode | Not exposed | **Denied by default** | LAN/IP/DHCP changes can sever the session; others alter persistent/global behavior | Never write interfaces through normal experiments; redact even read-only network state |
| License and option installation | `:LIC:SET` | Not exposed | **Denied by default** | Changes licensed/option state and belongs to maintenance | Keep outside normal WaveBench capabilities |

## SCPI directly used today

The following uses normalized long-form manual spellings. The implementation uses legal short
forms such as `APPL`, `MEAS`, `OUTP`, and `SYST:ERR?`. This is not a raw command log and does not
claim separate accuracy or all-model acceptance for every line.

```text
*IDN?
SYSTem:ERRor?

APPLy? CH<n>
MEASure:ALL[:DC]? CH<n>
OUTPut[:STATe]? CH<n>
OUTPut:MODE? CH<n>
OUTPut:OVP[:STATe]? CH<n>
OUTPut:OVP:VALue? CH<n>
OUTPut:OVP:QUES? CH<n>
OUTPut:OCP[:STATe]? CH<n>
OUTPut:OCP:VALue? CH<n>
OUTPut:OCP:QUES? CH<n>

APPLy CH<n>,<voltage>,<current>
OUTPut[:STATe] CH<n>,ON|OFF
OUTPut:OVP:VALue CH<n>,<voltage>
OUTPut:OVP[:STATe] CH<n>,ON|OFF
OUTPut:OCP:VALue CH<n>,<current>
OUTPut:OCP[:STATe] CH<n>,ON|OFF
```

`power.status` is not one query: it reads `APPLy?`, `MEASure:ALL?`, output state, and regulation
mode in sequence. `power.protection` similarly reads six protection fields. The current
implementation returns no partial public model if an intermediate query fails.

## WaveBench guarantees that are not manual-command coverage

- Core limits, OVP/OCP relationship checks, pre-enable checks, run plans, and experiment-level
  restoration belong to WaveBench policy/services, not to a DP800 SCPI command.
- The 2026-07-24 normal-path acceptance snapshotted all three channels before writes and independently
  verified exact restoration, outputs OFF, and an empty error queue. Controlled fault injection on
  2026-07-27 additionally accepted M2 output, protection, and `APPLy` recovery/latch semantics. Real
  instrument restoration is not database-atomic; unverifiable outcomes still fail and latch writes off.
- Descriptor capability validation proves that declared methods exist, not SCPI semantics,
  responses, load wiring, measurement accuracy, or compatibility with every DP800 model.
- Core-configured settle delays do not prove that the output has stabilized to an accuracy target.

## Recommended roadmap

1. **P1: device health and query-only channel profile.** Add non-consuming health plus option/model-gated
   range, Sense, tracking, timer, and
   monitor status while retaining explicit channels.
2. **P2: timer, delay, and monitor.** Begin query-only, then require bounded steps, timeout,
   finally-stop, complete snapshots, and multi-channel restoration for execution.
3. **P3: recorder/analyzer.** Define storage lifecycle, size limits, and artifact semantics before
   recording or exposing query-only analysis results.
4. **Keep denied by default:** network/interface writes, license, reset/preset, instrument state
   slots, file deletion/load, and raw trigger actions require a different permission model and
   human confirmation.

## Evidence boundary

- **Manual:** the local Chinese DP800 transcription under `vendor-local` is for internal audit only;
  this document neither copies the full manual nor packages it.
- **Implementation:** external `driver.py`, `descriptor.py`, FakeTransport, lifecycle, and wheel
  tests, plus the public WaveBench PowerService contract.
- **Hardware:** controlled DP832A LAN normal-path acceptance on 2026-07-24 covered real-wheel
  install/routing, three-channel status and protection reads, conservative CH1 setpoint and OVP/OCP
  writes, unloaded output ON/OFF, full restoration, and error-queue verification. M2 acceptance on
  2026-07-27 added a distinct-target readback/restore cycle, five controlled fault cases, and separate-session
  final-state verification after every case.
- **Not accepted:** other DP800 models, loaded transients, measurement accuracy, range/Sense/tracking,
  timer/delay, monitor, trigger, recorder/analyzer, storage, and system configuration.

A feature is promoted to **external hardware accepted** only when current external code, targeted
offline tests, real command acceptance/readback, and required restoration evidence all exist.
