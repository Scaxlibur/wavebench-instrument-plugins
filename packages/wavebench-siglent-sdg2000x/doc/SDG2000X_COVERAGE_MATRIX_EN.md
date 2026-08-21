# SDG2000X Coverage Matrix

[中文](SDG2000X_COVERAGE_MATRIX.md)

## Current conclusion

The current release completes the strict query-only M2 implementation. `source.idn` and `source.status` have passed zero-write CH1/CH2 hardware acceptance on one `SDG2122X` running firmware `2.01.01.39R7T2`. Other models, other firmware revisions, and physical waveform agreement remain unaccepted. Every other command domain remains disabled.

## Coverage status

| Command domain | WaveBench capability | Current status | Exit condition |
| --- | --- | --- | --- |
| Instrument identity | `source.idn` | Passed on `SDG2122X` / `2.01.01.39R7T2`; other models remain unaccepted | Add redacted evidence per model and firmware |
| System error queue | None | Disabled | Confirm the query, empty-queue semantics, and whether reads consume state |
| Basic channel status | `source.status` | Three matching CH1/CH2 rounds in one SDG2122X session, 19 queries and zero write requests | With outputs enabled, compare physical frequency, Vpp, and offset on the scope; accept other models individually |
| Output control | None | Denied by default | Test pre-state, explicit OFF, readback, and failure recovery |
| Fixed-wave configuration | None | Denied by default | Establish range, load, safety-limit, and transaction-restoration evidence |
| Modulation, sweep, and burst | None | Disabled | Build a separate read-only profile for each domain before evaluating writes |
| Arbitrary waveforms | None | Denied by default | Define data format, volatile side effects, size limits, and restoration boundary |
| Counter | None | Disabled | First establish a strict profile that does not change counter state |

## Denied by default

- Do not send `*RST` or another global preset command.
- Do not enable outputs or issue trigger, burst, sweep, or arbitrary-wave writes.
- Do not expose raw SCPI.
- Do not equate a product-page feature with an implemented capability.

## Sources of truth

- [SIGLENT SDG2000X product page](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT waveform-generator document downloads](https://siglentna.com/resources/documents/waveform-generators/)
- Local guide: `doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`, revision `PG02_E05C`
- [Protocol audit](SDG2000X_PROTOCOL_AUDIT_EN.md)
- [Read-only hardware acceptance](SDG2000X_READONLY_ACCEPTANCE_EN.md)
- Current descriptor, driver, and fake-transport tests
