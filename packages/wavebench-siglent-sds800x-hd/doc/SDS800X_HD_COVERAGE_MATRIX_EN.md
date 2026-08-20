# SDS800X HD Programming-Guide Coverage Matrix

[中文](SDS800X_HD_COVERAGE_MATRIX.md)

## Purpose and evidence boundary

This matrix compares the SIGLENT SDS Series Digital Oscilloscope Programming Guide,
revision `CN11G`, with the external WaveBench `siglent.sds800x-hd` plugin. It separates
manual claims, offline implementation, and hardware acceptance. A command in the shared SDS
manual is not automatically treated as an SDS800X HD capability.

The local conversion is split across three directories because of converter limits. Their three
`full.md` files remain under `doc/vendor-local/`, excluded from Git and the sdist. The manual's
support table gives `1.1.3.1` as the minimum SDS800X HD firmware, but it does not mark every
command by supported family. Model and firmware behavior therefore still require target-hardware
confirmation.

Evidence labels used here:

- **Hardware accepted**: current external-plugin code, a target SDS800X HD, and controlled evidence all exist.
- **Implemented / offline verified**: driver and FakeTransport tests exist for that item, without corresponding hardware evidence.
- **Manual reviewed**: command and response semantics were reviewed, but no capability is exposed yet.
- **Core interface blocked**: the vendor protocol cannot be represented completely by the current WaveBench transport or public model.
- **Hardware blocked**: offline code cannot establish response framing, state transitions, or hardware-specific behavior.
- **Rejected by default**: the operation changes global state, writes instrument storage, or lacks a reliable restore boundary.

## Current coverage

| Domain | Manual surface | WaveBench mapping | Status | Boundary and next step |
|---|---|---|---|---|
| Identity | `*IDN?` | `scope.idn` | **SDS804X HD hardware accepted** | Four fields, manufacturer, model, 14-character ASCII serial, and firmware format passed; other models remain pending |
| Analog-channel coupling | `:CHANnel<n>:COUPling?`, returning `AC`, `DC`, or `GND` | `scope.channel_coupling` | **SDS804X HD hardware accepted** | CH1–CH4 returned DC; two-channel models and other coupling states remain pending |
| Input termination | Shared manual lists `ONEMeg` and `FIFTy` | No standalone capability | **Rejected by default** | SDS800X HD product material specifies fixed `1 MΩ`; do not project the shared `FIFTy` setter onto this family |
| Error queue | CN11G documents no error-queue query | `scope.errors` | **Not covered** | Do not guess `SYSTem:ERRor?`; consuming queries also conflict with automatic retries on ordinary core queries |
| Waveform read | `SOURce`, `STARt`, `INTerval`, `POINt`, `MAXPoint?`, `WIDTh`, `BYTeorder`, `PREamble?`, and `DATA?` | `scope.fetch_waveform` | **SDS804X HD multi-chunk hardware accepted** | Stop, sequence OFF, CH1/CH2 `DMAX`, WORD/LSB, numeric results, and success/failure restoration passed; a `10M` record passed as `5M + 5M`, while USB remains pending |
| Sequence gate | `:ACQuire:SEQuence?` | `scope.fetch_waveform` precondition | **SDS804X HD hardware accepted** | Established Stop + sequence ON in `NORMAL` trigger mode; the driver rejected before any waveform write or binary query |
| Measurement statistics | `:MEASure:MODE?`, `ADVanced:P<n>?`, `TYPE?`, `STATistics?`, and `SHIStory?` | `scope.measurement_statistics` | **SDS804X HD hardware accepted** | Query-only access to an existing slot; all six P3 `PKPK` fields and five stopped-history values passed with no driver writes |
| Single and multichannel capture | `TRIGger:MODE`, `RUN`, `STOP`, `STATus?`, and `*OPC?` | `scope.capture_waveform`, `scope.capture_waveforms` | **Hardware blocked** | The manual does not guarantee that `*OPC?` after `RUN` waits for a physical trigger; multichannel capture must read all channels after one acquisition |
| Trigger run state | `:TRIGger:STATus?` returns `Arm`, `Ready`, `Auto`, `Trig'd`, `Stop`, or `Roll` | No standalone capability | **Manual reviewed** | It cannot be mapped to public `ScopeAcquisitionStatus`, which describes averaging and segmented acquisition |
| Screenshot | `:PRINt? PNG,NORMal` or inverted form | `scope.screenshot` | **Core interface blocked / hardware blocked** | The example reads raw image bytes while the core exposes only definite-block queries; the command also has no reliable menu control |
| Autoset | `:AUToset` | `scope.autoscale` | **Rejected by default** | Changes trigger, vertical, and horizontal state without an error queue or restore loop |
| Acquisition status | `ACQuire:TYPE?`, `SEQuence?`, `NUMACq?`, and related queries | `scope.acquisition_status` | **Not covered** | Missing `average_complete`, option identity, capacity, and available-segment semantics prevent constructing the public model |
| Snapshot, measurement configuration, digital, history, and analysis | Shared SDS subsystems | Corresponding optional Scope capabilities | **Not covered** | Review each capability for model, option, public-model, and restore semantics |
| Reset, system, and instrument filesystem | `*RST`, system settings, save/recall, image save, and related commands | No baseline capability | **Rejected by default** | May alter global state, networking, or persistent storage |

## Confirmed waveform-protocol boundary

`PREamble?` returns a definite-length binary block. Its fixed descriptor portion is 346 bytes, and
sequence data may append timestamps. The current pure parser supports only non-sequence analog
channels, so it requires exactly 346 bytes after the core removes the IEEE block envelope and
explicitly rejects timestamp appendices instead of discarding them. `DATA?` also uses a declared-
length block; the core transport extracts its payload, and the plugin must never apply `rstrip()`
to binary data.

On the SDS804X HD with firmware `4.8.12.1.1.6.5`, a real preamble confirmed the non-sequence
signature `read_frames=0`, `sum_frames=1`, `segment=-1`. The manual's `segment=1` form remains
accepted; other frame combinations are still rejected. The same WORD preamble reported `100000`
points, `200000` bytes, and a `50.000000584 ns` sample interval, consistent with the parser. A
supplementary long-record run confirmed two chunks at `START 0` and `START 5000000` for
`10000000` points with `MAXPoint=5000000`.

The first analog conversion uses these documented fields:

```text
vdiv = vertical_scale_raw * probe
offset = vertical_offset_raw * probe
voltage = raw_code * (vdiv / code_per_div) - offset
```

With `STARt 0` and `INTerval 1`, the time axis is:

```text
x[i] = horizontal_delay - timebase * 10 / 2 + i * sample_interval
```

Eight-bit samples are signed integers. ADC widths above eight bits use `WORD`, explicit LSB order,
and signed 16-bit decoding. The manual describes higher-resolution samples as left-aligned with
zero-filled low bits; the first version does not shift them. The driver must query `MAXPoint?`
instead of hard-coding the example limit.

The exposed transaction accepts only WaveBench `DMAX`. Page 385 of CN11G defines the
`WAVeform:POINt` argument as an integer NR1 and provides no `DEF/MAX/DMAX` instrument keywords;
the driver uses `POINT 0` from the vendor waveform-reconstruction example to select the full
record. `DEF` and `MAX` fail before any I/O rather than sending undocumented commands.

The transaction first requires `TRIGger:STATus? = Stop` and `ACQuire:SEQuence? = OFF`, then saves
`SOURCE/START/INTERVAL/POINT/WIDTH/BYTEorder`. It fixes `WORD`, LSB, `START 0`, and `INTERVAL 1`,
uses the preamble for total points, and uses `MAXPoint?` for the per-query limit. It attempts to
restore all transfer state after success, protocol failure, or transport failure; restoration
failure does not hide an existing primary exception. The path sends no `RUN`, `SINGLE`, or `STOP`
and reads only an already-stopped record.

## WaveBench core constraints

- The driver obtains a core transport only through `DriverContext.open_transport()` and owns idempotent cleanup.
- A capability is declared only after its public method is complete; runtime callability checks do not replace signature and semantic tests.
- `fetch_waveform(channel, points="dmax", check_errors=True)` returns the core `WaveformData` and `WaveformHeader` models rather than plugin-local copies.
- CN11G provides no error queue, so waveform use must explicitly set `scope.check_errors=false`; a direct driver call with `check_errors=True` fails before any I/O.
- The current `points` implementation supports only `DMAX`. The public signature remains `fetch_waveform(channel, points="dmax", check_errors=True)` without inventing `DEF/MAX` mappings.
- Multichannel capture configures every channel, performs one acquisition, and then reads each channel. It must not retrigger per channel.
- The current core PyVISA path does not apply the separate `opc_timeout_ms` to `query_opc()`, so acquisition cannot yet claim a separate OPC timeout guarantee.

## Development order

1. M1: strict identity parsing and read-only `scope.channel_coupling`, with offline tests.
2. M2: the 346-byte preamble, data conversion, and stopped analog-record `scope.fetch_waveform` transaction have offline coverage; hardware evidence remains absent.
3. M3: TCPIP WORD/LSB readout, CH1/CH2 numeric checks, transfer-state restoration, a real `10M` multi-chunk read, and safe sequence-ON rejection are complete on one SDS804X HD; USB and additional models remain pending.
4. M4: independently validate trigger transitions, OPC waiting, and one multichannel acquisition before considering capture capabilities.
5. Track screenshot, digital channels, FFT, sequence/history, Autoset, and writes as separate work items; do not bypass gates with raw SCPI.

## SCPI used directly today

```text
*IDN?
:CHANnel<n>:COUPling?
:TRIGger:STATus?
:ACQuire:SEQuence?
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

A command appearing in this matrix is not necessarily declared by the descriptor or verified on hardware.
