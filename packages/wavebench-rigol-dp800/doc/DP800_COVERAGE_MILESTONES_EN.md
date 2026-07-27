# DP800 Command Coverage Development Milestones

[中文](DP800_COVERAGE_MILESTONES.md)

This document turns the [DP800 programming-manual coverage matrix](DP800_COVERAGE_MATRIX_EN.md)
into an implementable, verifiable, and incremental delivery plan. The objective is not a risk-blind
command-coverage percentage. Every public command surface must have an explicit typed model,
model/option applicability, failure semantics, and real-instrument restoration evidence.

The external plugin is currently version `0.2.0` and exposes six capabilities: `power.idn`,
`power.status`, `power.measurement`, `power.set_voltage_current_limit`, `power.output`, and
`power.protection`. Controlled DP832A LAN acceptance on 2026-07-24 showed these paths can work;
it did not prove that every exceptional path in the current driver already provides transactional
rollback and ambiguous-write latching.

The manual covers multiple DP800 models, A/non-A variants, and option combinations. Model gating
below is part of the contract: DP832A evidence must not be extrapolated to DP811, DP821, DP831,
or the whole family, and option data returned by `*OPT?` does not replace checks of physical
interfaces, channels, loads, and wiring.

## Acceptance standard

### Evidence levels

- **Static complete**: manual command, model/option conditions, response type, and side effects are documented.
- **Offline complete**: public typed model, driver contract, descriptor capability, Service/CLI
  preflight, and exact FakeTransport command-sequence tests exist.
- **Query hardware accepted**: the complete response arrives within a bounded timeout and passes
  strict enum/range/finite-number parsing; command capture proves zero writes. This does not prove accuracy.
- **Controlled-write hardware accepted**: all affected fields are saved, a distinct safe target is
  written, readback is verified, the original state is restored in `finally`, and a separate session
  verifies every restored field. Same-value writeback alone does not pass.
- **Accuracy accepted**: a traceable source/load, documented wiring, and an error budget are required;
  this remains separate from protocol acceptance.

### Rules shared by all milestones

- Readings, setpoints, thresholds, and power must be finite; reject `NaN` and positive/negative infinity.
- Strictly validate channels, enums, ranges, units, and binary-block lengths. Unknown responses must not downgrade silently.
- Every channel-addressed public API carries an explicit channel. A current-channel profile is an
  explicit exception: it must not change hidden state through `:INSTrument:SELect` and returns the
  channel actually read; timer/delay transactions that truly require current-channel must save and restore it.
- Instrument writes, output control, and triggers are never blindly retried. A timeout, disconnect,
  or ambiguous result on the first write latches configuration writes off for that driver instance
  until the session is closed and recreated.
- If any step in a multi-write transaction fails, restore the original snapshot. A restoration failure
  must fail and latch the instance; reporting only the last readable state is not sufficient.
- Output ON, timer/delay start, monitor actions, recorder file writes, and trigger execution require
  explicit user intent. Ordinary snapshots never perform them implicitly.
- Real evidence must not retain real addresses, serial numbers, MAC addresses, raw logs, or load data;
  documentation examples use reserved addresses.

## Roadmap

| Milestone | Main command surface | Target |
|---|---|---|
| M0 | Manual's 22 domains, package boundary, current 6 capabilities | **Complete** |
| M1 | Existing status, measurement, and protection queries | **Complete** |
| M2 | `APPLy`, output switch, OVP/OCP writes | Transactional current writes |
| M3 | Options, SCPI version, self-test, non-consuming status | Zero-write health snapshot |
| M4 | Range, Sense, Track, selected-channel state | Model/option-gated channel profile |
| M5 | `TIMEr` / `OUTPut:TIMEr` queries | Zero-write timer profile |
| M6 | Bounded timer configuration and execution | Bounded sequenced output |
| M7 | `DELAY` queries | Zero-write delay profile |
| M8 | Bounded delay configuration and execution | Bounded delayed output |
| M9 | `MONItor` query and controlled interlock | Monitor profile and safe action |
| M10 | `RECorder` / `ANALyzer` | Bounded artifact lifecycle |
| M11 | `TRIGger` topology queries | Option-gated, zero execution by default |
| M12 | Multi-model regression and release closure | Stable compatibility matrix |

M1–M4 are the current priority. M5 and later begin only after the preceding transactional semantics
are stable. M10/M11 must not send high-side-effect commands merely to advance milestone numbering.

## M0: command inventory and publication boundary — complete

### Completed work

- Chinese and English coverage matrices map all 22 manual command domains to plugin APIs, tests,
  and DP832A evidence.
- Direct SCPI usage, uncovered domains, and default-denied surfaces are explicit.
- Vendor manuals remain under `doc/vendor-local/`, are Git-ignored, and are explicitly excluded from Hatch sdists.
- Wheel/sdist regression tests prevent vendor material from entering artifacts while public matrices remain in the sdist.

### Current baseline commands

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

## M1: harden the existing read-only capabilities — complete

### Commands

```text
*IDN?
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
```

`SYSTem:ERRor?` remains an explicit queue-consuming diagnostic operation and is excluded from ordinary status snapshots.

### Implementation

- Add finite-number validation to every field from `APPLy?` and `MEASure:ALL?`.
- Accept only `ON/OFF` output state, hardware-confirmed `CV/CC/UR` modes, `ON/OFF` protection
  enable, and `YES/NO` trip state.
- Validate channel count through an IDN/model profile instead of checking only `channel >= 1`.
- Keep aggregate snapshots all-or-nothing: a mid-query failure returns no partial `PowerStatus` or
  `PowerProtectionStatus`.
- IDN may remain interactive, but reports and committed evidence redact serial numbers by default.

### Exit gate

- Exact offline tests cover unknown enums, non-finite values, missing/extra fields, invalid channels,
  and every mid-sequence failure.
- Zero-write queries pass on all three DP832A channels. Numeric accuracy is not part of this gate.

### Acceptance evidence

- Core `0.8.12` and external plugin `0.2.0` implement model/channel gating, finite-number and strict-enum validation, and all-or-nothing snapshots.
- Offline fault injection covers all four status query positions, all six protection query positions, six enums, missing/extra fields, and non-finite values.
- The manual-defined two-field response to targetless single-channel `:APPL?` is covered offline with rating reported as unavailable; that path remains hardware-unverified.
- On 2026-07-27, all three DP832A channels passed a 31-query, zero-write gate; all three outputs remained OFF.
- This evidence covers only the DP832A protocol responses. It is not extrapolated to DP811/821/831 and does not establish measurement accuracy.

## M2: transactional current write capabilities

### Commands

```text
APPLy CH<n>,<voltage>,<current>
OUTPut[:STATe] CH<n>,ON|OFF
OUTPut:OVP:VALue CH<n>,<voltage>
OUTPut:OVP[:STATe] CH<n>,ON|OFF
OUTPut:OCP:VALue CH<n>,<current>
OUTPut:OCP[:STATe] CH<n>,ON|OFF
```

Readback uses M1's setpoint, output, and protection queries. Optional queue inspection remains an
explicit `SYSTem:ERRor?` operation.

### Implementation

- Serialize all transport I/O on one reentrant lock per driver instance.
- Before `APPLy`, save voltage/current, write and verify both, and restore both on failure. An ambiguous
  first write immediately latches configuration writes off.
- Save output state before changing it. Before ON, the Service rechecks safety limits, protection
  thresholds, requested setpoints, and explicit user confirmation. The driver never retries ON blindly.
- An OVP/OCP transaction saves all four configuration fields and both trip fields, writes in an order
  that never temporarily weakens protection, and verifies each step. Trip state is not “restored” by CLEAR.
- Align configured and method-level `check_errors_after_ops` semantics so descriptor values are not ignored.

### Hardware acceptance

- Output is OFF and unloaded, or attached to a documented safe electronic load; use distinct conservative targets.
- CH1 passes setpoint, OVP/OCP, and unloaded ON/OFF target/readback/restore cycles, followed by an
  independent all-channel state check.
- Fault injection covers first-write ambiguity, later-write failure, readback mismatch, and restoration failure.

## M3: option and non-consuming health snapshot

### Commands

```text
*OPT?
*STB?
*TST?
SYSTem:VERSion?
SYSTem:OTP?
SYSTem:SELF:TEST:BOARD? [TOP|BOTTOM]
SYSTem:SELF:TEST:FAN?
SYSTem:SELF:TEST:TEMP?
STATus:QUEStionable:CONDition?                         # applicable models only
STATus:QUEStionable:INSTrument:ISUMmary<n>:CONDition? # multi-channel models
```

### Boundary

- Return typed options, SCPI version, self-test, and current condition only; retain no serial, MAC, or IP.
- `*STB?` and condition registers do not clear events and may enter the snapshot.
- `*ESR?`, `:STATus:...:EVENt?`, and `*CLS` remain excluded because they consume or clear state.
- Expose `*TST?` only after confirming it reports prior power-on self-test state without launching a disruptive test.
- Choose single- versus multi-channel status trees by model profile; never probe every tree blindly.

### Exit gate

- Strictly parse model/option enums, bit masks, and finite temperature; preserve unknown option tokens
  as unknown rather than claiming support.
- The DP832A full snapshot passes with zero writes and no event-register reads.

## M4: channel feature profile (Range, Sense, Track)

### Commands

```text
INSTrument[:SELect]?
INSTrument:NSELect?
OUTPut:RANGe?               # DP811A/DP811 only
OUTPut:SENSe? CH<n>         # supported channel or NONE
OUTPut:TRACk[:STATe]? CH<n> # supported channel or NONE
SYSTem:TRACKMode?
SYSTem:ONOFFSync?
```

### Implementation and boundary

- Query selected channel and Range/Sense/Track/sync state without changing current-channel.
- Preserve `NONE` as unsupported; do not reinterpret it as `OFF`.
- Gate DP811 Range, DP821 Sense, and DP831/DP832 Track by explicit model/channel tables.
- Do not expose writes yet: Range changes the safety envelope, Sense requires remote-sense wiring,
  and Track/ON-OFF sync couples channels.

### Exit gate

- Offline matrix tests cover every supported and unsupported model/channel pair.
- A zero-write three-channel DP832A profile passes and agrees with the manual's applicability table.

## M5: zero-write Timer profile

### Commands

```text
INSTrument[:SELect]?
TIMEr:CYCLEs?
TIMEr:ENDState?
TIMEr:GROUPs?
TIMEr:PARAmeter? <first>[,<count>]
TIMEr[:STATe]?
TIMEr:TEMPlet:FALLRate?
TIMEr:TEMPlet:INTErval?
TIMEr:TEMPlet:INVErt?
TIMEr:TEMPlet:MAXValue?
TIMEr:TEMPlet:MINValue?
TIMEr:TEMPlet:OBJect?
TIMEr:TEMPlet:PERIod?
TIMEr:TEMPlet:POINTs?
TIMEr:TEMPlet:RISERate?
TIMEr:TEMPlet:SELect?
TIMEr:TEMPlet:SYMMetry?
TIMEr:TEMPlet:WIDTh?
OUTPut:TIMEr? {P8V|P30V|N30V}        # manual-listed range names; model applicability must be proven first
OUTPut:TIMEr:STATe? {P8V|P30V|N30V}
```

### Constraints

- Generic `TIMEr:*?` reads current-channel. Return that channel's complete snapshot and never send
  `INSTrument:SELect` merely to read another channel.
- The manual lists only `P8V/P30V/N30V` for `OUTPut:TIMEr?`, while the same manual maps DP832(A)
  channels to `P30V/P30V2/P5V`. Until a read-only hardware diagnostic resolves that conflict,
  `OUTPut:TIMEr?` is not a formal DP832A path and undocumented `P30V2/P5V` syntax must not be guessed;
  the initial DP832A profile uses current-channel `TIMEr:*?` instead.
- Validate `TIMEr:PARAmeter?` definite-length block framing, group/field count, finite voltage/current,
  positive duration, and maximum points/response size. If separately authorized on an applicable model,
  parse `OUTPut:TIMEr?` as its documented plain semicolon-separated string, not as the same block format.
- Send no template-building, parameter-write, or timer ON/OFF command.

### Exit gate

- Offline tests cover normal, truncated, oversized, duplicate-index, and invalid-group responses.
- A DP832A snapshot passes while Timer is OFF, with zero writes and unchanged output/current-channel.

## M6: bounded Timer configuration and execution

### Commands

```text
INSTrument[:SELect] CH<n> / ?
TIMEr:GROUPs <count>
TIMEr:CYCLEs N,<count>
TIMEr:ENDState OFF
TIMEr:PARAmeter <index>,<voltage>,<current>,<seconds>
TIMEr[:STATe] ON|OFF / ?
OUTPut[:STATe] CH<n>,ON|OFF / ?
```

`OUTPut:TIMEr` / `OUTPut:TIMEr:STATe` become an equivalent supplemental path only after M5 proves
that a specific model accepts the manual-listed range name. The initial DP832A release sends neither.

### Safety contract

- First release permits finite `N` cycles only, never `I`; end state is forced to `OFF`, never `LAST`.
- Core safety limits cover every step's voltage, current, power, total duration, and point count.
- Accept only sessions where Timer, Delay, and the target output were initially OFF; never take over a running user sequence.
- Save original current-channel, target-channel `APPLy?` setpoints, the complete active Timer table,
  cycle/end state, and output. If the original group count exceeds the bounded backup limit, reject
  before the first write; configure while output is OFF.
- Reconfirm Delay is OFF before starting; Timer and Delay cannot run simultaneously.
- The fixed start order is: configure and read back Timer, start Timer and verify its state, then enable
  the target output only after safety review and explicit user confirmation. A watchdog bounds execution;
  cancellation, timeout, or error first turns the target output OFF and verifies it in `finally`, then
  turns Timer OFF and verifies stop, and finally restores parameters, setpoints, and current-channel.
- Ambiguous first write, unconfirmed stop, or restoration failure latches the instance and demands manual output confirmation.
- Instrument template writes remain private; host code expands templates into validated explicit points.

### Hardware acceptance

- Begin unloaded at low voltage/current with two points and one cycle; independently observe timing with a scope or DMM.
- A separate session confirms Timer OFF, all channel output states, and original parameters after the run.

## M7: zero-write Delay profile

### Commands

```text
INSTrument[:SELect]?
DELAY:CYCLEs?
DELAY:ENDState?
DELAY:GROUPs?
DELAY:PARAmeter? <first>[,<count>]
DELAY[:STATe]?
DELAY:STATe:GEN?
DELAY:STOP?
DELAY:TIME:GEN?
```

Like M5, read current-channel only. Strictly parse parameter-block indices, ON/OFF states, durations,
length, and stop condition/comparator/finite threshold. Hardware acceptance requires a zero-write
DP832A snapshot while Delay is OFF and unchanged selected channel/output.

## M8: bounded Delay configuration and execution

### Commands

```text
INSTrument[:SELect] CH<n> / ?
DELAY:GROUPs <count>
DELAY:CYCLEs N,<count>
DELAY:ENDState OFF
DELAY:PARAmeter <index>,ON|OFF,<seconds>
DELAY:STOP {NONE|<V|>V|<C|>C|<P|>P}[,<value>]
DELAY[:STATe] ON|OFF / ?
```

`DELAY:STATe:GEN` and `DELAY:TIME:GEN` are expanded by the host in the first release and are not public writes.

### Safety contract

- Permit finite cycles and `ENDState OFF` only; the explicit table must begin and end with OFF.
- Stop thresholds must stay inside channel ratings and core safety limits.
- Accept only sessions where Timer, Delay, and the target output were initially OFF. Save and restore
  selected channel, the complete active Delay table, stop condition, output, and generation parameters.
  If the original group count exceeds the bounded backup limit, reject before the first write;
  cancellation/timeout uses finally-stop. Failed restore or unconfirmed stop latches the instance.
- Hardware work begins unloaded with one OFF→ON→OFF cycle and independent timing observation.

## M9: Monitor profile and controlled interlock

### M9A zero-write profile

```text
MONItor:CURRent:CONDition?
MONItor:CURRent[:VALue]?
MONItor:POWER:CONDition?
MONItor:POWER[:VALue]?
MONItor[:STATe]?
MONItor:STOPway?
MONItor:VOLTage:CONDition?
MONItor:VOLTage[:VALue]?
```

Gate Monitor by model and `*OPT?`; read current-channel only and return typed logic/condition/action.
Zero-write acceptance must prove no output, alarm, or beeper change.

### M9B controlled interlock

```text
MONItor:VOLTage:CONDition <condition>,<logic>
MONItor:VOLTage[:VALue] <value>
MONItor:CURRent:CONDition <condition>,<logic>
MONItor:CURRent[:VALue] <value>
MONItor:POWER:CONDition <condition>
MONItor:POWER[:VALue] <value>
MONItor:STOPway {OUTOFF|WARN|BEEPER},ON|OFF
MONItor[:STATe] ON|OFF
```

- The first release permits the demonstrably safer `OUTOFF` action only; WARN/BEEPER do not replace shutdown.
- Save all conditions, thresholds, all three independent stop actions, and Monitor state; validate threshold relations against
  setpoints and protection before writes.
- Configure and verify while output is OFF, then require explicit enable intent; disable/restore in `finally`.
- A controllable load must prove the output actually turns off. Command response alone does not pass.

## M10: Recorder and Analyzer artifact lifecycle

### M10A zero-write status

```text
RECorder:DESTination?
RECorder:PERIod?
RECorder[:STATe]?
MEMory[:STATe]:VALid? ROF,<slot>
ANALyzer:FILE?
ANALyzer:OBJect?
ANALyzer:STARTTime?
ANALyzer:ENDTime?
ANALyzer:CURRTime?
ANALyzer:RESult?
ANALyzer:VALue? <time>
```

Analyzer queries require an already-open valid file; absence is a precondition failure, not an empty
result. Public artifacts redact file paths and bound response size/time indices.

### M10B bounded recording and analysis

```text
RECorder:PERIod <seconds>
RECorder:MEMory <slot>,<filename>
RECorder[:STATe] ON|OFF
ANALyzer:MEMory <slot>
ANALyzer:OBJect V|C|P
ANALyzer:STARTTime <seconds>
ANALyzer:ENDTime <seconds>
ANALyzer:ANALyze
ANALyzer:RESult?
```

- Accept only a session where Recorder was already OFF; never take over or stop an active user recording.
- Use only a dedicated internal slot whose state was checked with `MEMory:STATe:VALid? ROF,<slot>`
  and for which the user explicitly authorized overwrite; first release never writes arbitrary MMEMory paths.
- Bound period, duration, and estimated samples; explain that stopping Recorder writes a file.
- Save original Recorder/Analyzer state; timeout/cancellation stops Recorder and final state remains
  OFF. Analyzer opens only the artifact created and verified by this transaction; result metadata
  records the retained internal artifact and any authorized overwrite.
- File deletion, arbitrary paths, unknown-slot overwrite, and `MMEMory:*` remain denied.

## M11: read-only Trigger topology audit

Only after `*OPT?` confirms Trigger support and physical D0–D3 interfaces/levels are checked may these queries run:

```text
TRIGger[:SEQuence]:SOURce?
TRIGger[:SEQuence]:DELay?
TRIGger:IN:CHTYpe?
TRIGger:IN[:ENABle]? D0|D1|D2|D3
TRIGger:IN:RESPonse? D0|D1|D2|D3
TRIGger:IN:SENSitivity? D0|D1|D2|D3
TRIGger:IN:SOURce? D0|D1|D2|D3
TRIGger:IN:TYPE? D0|D1|D2|D3
TRIGger:OUT[:ENABle]? D0|D1|D2|D3
TRIGger:OUT:CONDition? D0|D1|D2|D3
TRIGger:OUT:DUTY? D0|D1|D2|D3
TRIGger:OUT:PERIod? D0|D1|D2|D3
TRIGger:OUT:POLArity? D0|D1|D2|D3
TRIGger:OUT:SIGNal? D0|D1|D2|D3
TRIGger:OUT:SOURce? D0|D1|D2|D3
```

This milestone explicitly sends no `:INITiate`, `:TRIGger:IN:IMMEdiate`, `*TRG`, triggered
voltage/current setting, or input/output enable. A successful query profile proves topology only,
not trigger execution. Execution needs a separate authorized milestone with level certification,
fixtures, and output restoration.

## M12: multi-model regression and release closure

- Build a model/channel/option matrix that distinguishes at least DP811, DP821, DP831, DP832 and A/non-A variants.
- Each capability must explicitly support, return unavailable, or reject; never blind-probe unsupported models.
- Run full core/plugin tests, Ruff, package check, wheel/sdist inspection, and lifecycle dry-run.
- Update both coverage matrices, milestones, and changelog. Real addresses, serials, snapshots, and raw logs do not enter commits.
- Versioning, commit, push, tag, and publication remain separately user-authorized actions.

## Long-term default-denied or separately authorized commands

Manual availability is not sufficient reason to expose these as ordinary lab capabilities:

- Reset/recall/preset: `*RST`, `*RCL`, `:PRESet[:APPLy]`, `:RECAll:*`, `:MEMory:*:LOAD`.
- Persistent storage/deletion: `*SAV`, `:STORe:*`, `:MEMory:*:STORe/DELete/LOCK`, and
  `:MMEMory:STORe/LOAD/DELete/MDIRectory`.
- Network/interface writes: `:SYSTem:COMMunicate:LAN:*` and GPIB/RS232 configuration.
- License installation: `:LIC:SET`.
- Protection clears: `:OUTPut:OVP:CLEAR`, `:OUTPut:OCP:CLEAR`, and output-reenabling
  `:SOURce:*:PROTection:CLEar`; these require a separate human-confirmed fault-recovery flow.
- Consuming status: `*CLS`, `*ESR?`, and `:STATus:*:EVENt?`; any future API must state “read and clear.”
- Front-panel/global behavior writes: display/text, language, immediate beeper, local/remote lock,
  power-on behavior, ON/OFF sync, and tracking mode without a dedicated restoration contract.
- Infinite Timer/Delay loops, `LAST` end state, arbitrary file paths, and unconfirmed slot overwrite.

## Release gate for every milestone

A capability becomes “hardware accepted” in the matrix only when all of the following exist:

1. Public typed model and serialization format;
2. Driver protocol, capability mapping, and descriptor declaration;
3. Service/CLI preflight before opening transport for missing capability and high-risk parameters;
4. Exact FakeTransport query/write order plus malformed, timeout, readback-mismatch, and restore-failure tests;
5. Current-version wheel lifecycle and sdist privacy-boundary tests;
6. Real-instrument command acceptance and parsing evidence;
7. Distinct-value readback, restoration, and independent-session final-state evidence for every write;
8. Independent observation for output-affecting operations, plus a dedicated fixture for accuracy claims.

Diagnostic probes, same-value writeback, one successful response, or core safety checks alone do not replace this gate.
