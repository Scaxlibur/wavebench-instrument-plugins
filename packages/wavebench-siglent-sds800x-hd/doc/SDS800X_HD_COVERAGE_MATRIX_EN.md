# SDS800X HD Programming-Guide Coverage Matrix

[中文](SDS800X_HD_COVERAGE_MATRIX.md)

This page maps SIGLENT SDS Series Programming Guide `CN11G` domains to the WaveBench capabilities
currently exposed by the external `wavebench-siglent-sds800x-hd` plugin. The
[package metadata](../pyproject.toml) is authoritative for version, dependencies, and entry point;
the [production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py) for models, resource
schemes, configuration fields, and capabilities; [profiles](../src/wavebench_siglent_sds800x_hd/profiles.py)
for screenshot and acquisition-control boundaries; and the
[driver](../src/wavebench_siglent_sds800x_hd/driver.py) for exact SCPI and transaction behavior.

The [feature-coverage development roadmap](SDS800X_HD_COVERAGE_MILESTONES_EN.md) records stage
status and future exit gates. The [hardware acceptance record](SDS800X_HD_HARDWARE_ACCEPTANCE_EN.md)
and [Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md) retain evidence for particular devices,
firmware, transports, and procedures. Those records support traceability and do not independently
add a current capability.

## Scope

`CN11G` is shared across multiple SDS families and does not annotate every command by applicable
series. A command in the shared manual is not automatically an SDS800X HD capability. The local
transcription is for internal audit only and lives under the Git-ignored, sdist-excluded
`doc/vendor-local/` directory.

This matrix answers what the production descriptor currently exposes and the boundaries of that
behavior. A new Core contract, Python method, offline test, or one successful hardware run cannot
replace a descriptor declaration.

## Functional coverage

| Domain | Manual surface | Current public capability | Current boundary |
|---|---|---|---|
| Identity | `*IDN?` | `scope.idn` | Strictly parses four identity fields and uses the descriptor model to validate channel count. Unknown manufacturer, model, or format fails. |
| Analog-channel coupling | `:CHANnel<n>:COUPling?` | `scope.channel_coupling` | Accepts only `AC`, `DC`, or `GND`; identity determines the channel limit. The family policy is fixed high impedance. |
| Input-termination writes | Shared-manual `ONEMeg`, `FIFTy` | Not declared | The `FIFTy` setter for other SDS families is not projected onto this family. |
| Error queue | No reliable query in `CN11G` | Not declared | Does not guess `SYSTem:ERRor?` or fabricate an empty list. Waveform operations require `check_errors=false`. |
| Stopped-record read | waveform source, range, format, preamble, data | `scope.fetch_waveform` | Accepts only `points="dmax"` and `check_errors=false`; requires acquisition Stop and Sequence OFF and restores transfer state after reading. |
| Single/multi-channel capture | trigger mode/run/stop/status, waveform | `scope.capture_waveform`, `scope.capture_waveforms` | Configures all target channels, performs one SINGLE, then reads each channel. `*OPC?` is not trigger-completion evidence. |
| Measurement statistics | mode, slot, type, statistics, history | `scope.measurement_statistics` | Reads an enabled Advanced measurement slot only; never configures, enables, or clears statistics. Buffer is read only when requested. |
| Screenshot | `:PRINt? PNG,NORMal`/`INVerted` | `scope.screenshot_profile`, `scope.screenshot_v2` | Accepts only profile color/inverted variants, uses MESSAGE framing, validates PNG in memory, and changes no persistent display state. |
| Acquisition run state | `:TRIGger:STATus?` | `scope.acquisition_run_state` | Maps vendor tokens to public state. Acquisition count is diagnostic and cannot prove completion by itself. |
| Acquisition control | trigger mode, run, stop, single | `scope.acquisition_control` | Continuous mode supports `auto`/`normal` only. SINGLE uses `configure_then_arm`; failure cleanup and restoration order come from the profile. |
| Autoset | `:AUToset` | Not declared | Mutates trigger, vertical, and timebase without a complete restoration contract; denied by default. |
| Math/FFT | function, operator, source, scale, span | No corresponding extension capability declared | Frequency axis, ready state, RBW, sample rate, and payload lack a complete public contract. |
| Typed trace | source, metadata, data | Not declared | Supported long records and the Core typed-trace point limit do not yet form a complete declarable profile. |
| Snapshot, measurement configuration, digital, Sequence/history | Shared SDS subsystems | Not declared | Each needs model/option, readable-field, and restoration review; no falsely complete model is exposed. |
| Reset, system setup, instrument files | `*RST`, system, save/recall, image save | Not declared | Mutates global, network, or persistent state and stays outside the base driver. |

## Waveform behavior

Before any waveform write, `fetch_waveform()` validates `points="dmax"`, `check_errors=false`, the
target channel, `TRIGger:STATus? = Stop`, and `ACQuire:SEQuence? = OFF`. It then saves
`SOURCE/START/INTERVAL/POINT/WIDTH/BYTEorder` and configures the target source, `WORD`, LSB,
`START 0`, `INTERVAL 1`, and `POINT 0` for this read.

`PREamble?` must contain exactly the 346-byte descriptor after Core removes the IEEE binary-block
envelope. An appended Sequence timestamp or ambiguous descriptor byte order fails. The driver
checks source, sample width, byte order, points, and data-byte count, then queries `MAXPoint?` for
the chunk limit and reads the complete record. Success, protocol failure, and transport failure all
attempt to restore the original transfer state; restoration failure does not hide a primary error.

Analog conversion uses:

```text
vdiv = vertical_scale_raw * probe
offset = vertical_offset_raw * probe
voltage = raw_code * (vdiv / code_per_div) - offset
x[i] = horizontal_delay - timebase * 10 / 2 + i * sample_interval
```

Eight-bit samples are signed integers. Wider ADC samples use `WORD`, LSB, and signed 16-bit
decoding. Higher-resolution samples remain left-aligned as documented; the driver does not shift
them. `DEF` and `MAX` fail before instrument I/O rather than sending undocumented point keywords.

## Screenshot and acquisition profiles

- The screenshot profile declares color and inverted PNG requests only, uses MESSAGE framing,
  bounds response/operation payload, and requires one `0A` content-trailing byte after canonical
  PNG. It captures, changes, and restores no persistent display fields.
- The acquisition-control profile declares `auto` and `normal` continuous modes only. SINGLE
  configures then arms, and a mode change resets acquisition count. Failure restoration handles
  acquisition then trigger and finally reconfirms Stop.
- Exact payload limits, step budgets, and profile semantics remain canonical in
  [profiles.py](../src/wavebench_siglent_sds800x_hd/profiles.py), not a second numeric table here.

## SCPI used directly today

This list indexes protocol domains from the current driver. The complete source remains
[driver.py](../src/wavebench_siglent_sds800x_hd/driver.py).

```text
*IDN?
:CHANnel<n>:COUPling?
:CHANnel<n>:SWITch
:CHANnel<n>:SCALe
:TIMebase:SCALe
:TRIGger:MODE[?]
:TRIGger:RUN
:TRIGger:STOP
:TRIGger:STATus?
:ACQuire:NUMACq?
:ACQuire:MODE[?]
:ACQuire:SEQuence?
:PRINt? PNG,NORMal
:PRINt? PNG,INVerted
:MEASure:MODE?
:MEASure:ADVanced:P<n>?
:MEASure:ADVanced:P<n>:TYPE?
:MEASure:ADVanced:P<n>:STATistics?
:MEASure:ADVanced:P<n>:SHIStory?
:MEASure:ADVanced:STATistics?
:WAVeform:SOURce[?]
:WAVeform:START[?]
:WAVeform:INTerval[?]
:WAVeform:POINt[?]
:WAVeform:MAXPoint?
:WAVeform:WIDTH[?]
:WAVeform:BYTeorder[?]
:WAVeform:PREamble?
:WAVeform:DATA?
```

## Related sources

- [Production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py)
- [Descriptor profiles](../src/wavebench_siglent_sds800x_hd/profiles.py)
- [Driver implementation](../src/wavebench_siglent_sds800x_hd/driver.py)
- [Feature-coverage development roadmap](SDS800X_HD_COVERAGE_MILESTONES_EN.md)
- [Hardware acceptance record](SDS800X_HD_HARDWARE_ACCEPTANCE_EN.md)
- [Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md) (Chinese)
