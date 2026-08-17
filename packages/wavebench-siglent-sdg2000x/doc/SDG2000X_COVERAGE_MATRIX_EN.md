# SDG2000X Coverage Matrix

[中文](SDG2000X_COVERAGE_MATRIX.md)

## Current conclusion

The current release completes the strict query-only M2 implementation. `source.idn` and `source.status` have offline protocol evidence, strict parsing, and zero-write tests. Hardware acceptance remains closed, and every other command domain remains disabled.

## Coverage status

| Command domain | WaveBench capability | Current status | Exit condition |
| --- | --- | --- | --- |
| Instrument identity | `source.idn` | Implemented for both documented response formats | Controlled hardware confirmation of model, firmware, and termination |
| System error queue | None | Disabled | Confirm the query, empty-queue semantics, and whether reads consume state |
| Basic channel status | `source.status` | Implemented with the core `SourceStatus` model | Confirm CH1/CH2 responses and firmware differences on controlled hardware |
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
- Current descriptor, driver, and fake-transport tests
