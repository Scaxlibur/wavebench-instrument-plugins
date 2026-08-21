# SDG2000X Coverage Matrix

[中文](SDG2000X_COVERAGE_MATRIX.md)

## Current conclusion

The current release exposes all five basic Source write capabilities in the core. Frequency, function, amplitude, square duty cycle, and output transactions cover every registered model, both channels, post-write drift, ambiguous writes, OFF recovery, and the session latch. SDG2122X CH2 completed periodic-wave loops; Noise/DC completed OFF-state readback only. Advanced modes remain separate domains with no raw-SCPI bypass.

## Coverage status

| Command domain | WaveBench capability | Current status | Exit condition |
| --- | --- | --- | --- |
| Instrument identity | `source.idn` | Passed on `SDG2122X` / `2.01.01.39R7T2`; other models remain unaccepted | Add redacted evidence per model and firmware |
| System error queue | None | Disabled | Confirm the query, empty-queue semantics, and whether reads consume state |
| Basic channel status | `source.status` | Three matching read-only rounds on SDG2122X; CH1/CH2 physical frequency, Vpp, and mean voltage also passed cross-check after output enable | Accept other models and firmware revisions individually |
| Output control | `source.output` | All three models pass the offline contract matrix; SDG2122X CH1/CH2 each completed one ON, fetch, and OFF sequence with zero unknown writes | Add SDG2042X and SDG2082X hardware evidence |
| Fixed-wave frequency | `source.set_frequency` | All three models pass the offline contract matrix; SDG2122X CH2 passed 2 kHz OFF-state and 5 kHz live ON-state RTM2032 loops | Add SDG2122X CH1 and other-model hardware evidence |
| Fixed-wave amplitude | `source.set_amplitude_vpp` | All models pass offline; SDG2122X CH2 2/3 Vpp OFF/ON writes pass closed loop | Add CH1 and other-model hardware evidence |
| Fixed-wave function | `source.set_function` | Four periodic functions pass live SDG2122X CH2 loops; Noise/DC have OFF-state readback only | Wait for a reusable Noise/DC safety model; test other models |
| Square-wave duty cycle | `source.set_square_duty_cycle` | SDG2122X CH2 20%/80% writes measured high fractions of 0.200/0.800 | Add frequency-dependent points, CH1, and other models |
| Harmonics | No lossless capability yet | SDG2122X H2–H16 slots pass; H2/H3 amplitude, H2 phase, and ALL/EVEN/ODD pass A4 spectrum tests | Declare after a variable/selected-only Source V2 model exists |
| Modulation | No lossless capability yet | SDG2122X internal AM/DSB-AM/FM/PM/PWM/ASK/FSK/PSK pass protocol and A4 waveform tests | Declare after Source V2 supports disabled-state absence and vendor ranges; wire external sources |
| Sweep and burst | None | Disabled | Establish strict protocol evidence per domain before evaluating writes |
| Arbitrary waveforms | None | Denied by default | Define data format, volatile side effects, size limits, and restoration boundary |
| Counter | None | Disabled | First establish a strict profile that does not change counter state |

## Denied by default

- Do not send `*RST` or another global preset command.
- Enable outputs only through `source.output` with a core `max_source_vpp` limit. Change frequency and amplitude only through their public capabilities; do not issue trigger, burst, or arbitrary-wave writes.
- Do not expose raw SCPI.
- Do not equate a product-page feature with an implemented capability.

## Sources of truth

- [SIGLENT SDG2000X product page](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT waveform-generator document downloads](https://siglentna.com/resources/documents/waveform-generators/)
- Local guide: `doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`, revision `PG02_E05C`
- [Protocol audit](SDG2000X_PROTOCOL_AUDIT_EN.md)
- [Read-only hardware acceptance](SDG2000X_READONLY_ACCEPTANCE_EN.md)
- [Output-control hardware acceptance](SDG2000X_OUTPUT_ACCEPTANCE_EN.md)
- [Frequency-write hardware acceptance](SDG2000X_FREQUENCY_ACCEPTANCE_EN.md)
- [Basic-write hardware acceptance](SDG2000X_BASIC_WRITE_ACCEPTANCE_EN.md)
- Current descriptor, driver, and fake-transport tests
