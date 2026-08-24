# SDG2000X Read-only Hardware Acceptance

[中文](SDG2000X_READONLY_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` completed controlled hardware acceptance for `source.idn` and `source.status`. The target firmware was `2.01.01.39R7T2`. Three consecutive CH1 and CH2 reads in one session returned identical results. The WaveBench transport audit recorded 19 queries, zero write requests, and zero instrument-mutation writes.

This acceptance covers identity, output-state, basic-wave, and sweep-state queries only on the named model and firmware. `SDG2042X`, `SDG2082X`, and other firmware revisions remain unaccepted.

## Test environment

- Plugin: `wavebench-siglent-sdg2000x` 0.2.0.
- Core: WaveBench 0.8.23.
- Signal generator: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Wiring: SDG CH1 → RTM CH1 and SDG CH2 → RTM CH2.
- Resources and serial numbers remained local to the session and are absent from public documentation.
- Access policy: `read_only` for both instruments.

## First observed difference and fix

The first `C1:OUTP?` response was:

```text
C1:OUTP OFF,LOAD,HZ,POWERON_STATE,OFF,PLRT,NOR
```

The E05C Output Command response documents output state, `LOAD`, and `PLRT`, but not `POWERON_STATE`. The initial parser therefore failed closed and did not continue or guess the field's meaning.

The hardware-driven fix accepts only `POWERON_STATE,ON|OFF` while still requiring `LOAD` and `PLRT`. Unknown values, duplicate fields, and any other unknown fields continue to raise `DataError`. The extension is validated but not exposed as a fabricated field absent from the core `SourceStatus` model.

## Signal-generator results

The corrected persistent session issued one `*IDN?`, followed by three rounds of `OUTP?`, `BSWV?`, and `SWWV?` on CH1 and CH2. All rounds agreed:

| Field | CH1 | CH2 |
| --- | --- | --- |
| Output | `OFF` | `OFF` |
| Function | `SIN` | `SIN` |
| Frequency | 1 kHz | 1 kHz |
| Amplitude | 4 Vpp | 4 Vpp |
| Offset | 0 V | 0 V |
| Phase | 0° | 0° |
| Frequency mode | `FIX` | `FIX` |
| Sweep | `OFF` | `OFF` |

WaveBench transport audit:

| Counter | Result |
| --- | ---: |
| Query | 19 |
| Write request | 0 |
| Write transmitted | 0 |
| Binary write transmitted | 0 |
| Instrument mutation write | 0 |

## Read-only oscilloscope cross-check

WaveBench `scope.snapshot` read CH1 and CH2 on the RTM2032, followed by one acquisition-status read. Both channels were enabled, used high-impedance `DCL` coupling, were set to 2 V/div, and were not overloaded. Waveform metadata reported 10,000 points and a 500 ns X increment on both channels. Status byte, questionable condition, and the error-queue-nonempty flag were all zero or false.

The oscilloscope session issued 108 queries and zero write requests or instrument-mutation writes.

## Deferred or unexecuted checks

- Both signal-generator outputs were OFF, so no physical frequency, amplitude, or phase cross-check was performed.
- No output enable, waveform configuration, sweep, burst, trigger, `*RST`, or error-queue query was sent.
- No `scope fetch`, `scope capture`, autoscale, or screenshot operation changed RTM2032 transfer, acquisition, or channel settings.
- The plugin still declares no `source.errors`, `source.channel_profile`, or write capability.

## Next gate

Physical signal-path acceptance requires explicit authorization to enable the outputs, or operator confirmation that both outputs have been enabled from the front panel. Only then may the controlled WaveBench oscilloscope path compare configured frequency, Vpp, offset, and measured waveforms. That work does not implicitly authorize M3 write-capability acceptance.
