# SDG2000X Coverage Matrix

[中文](SDG2000X_COVERAGE_MATRIX.md)

## Current conclusion

The current version is an M0 identity-query baseline. Only `*IDN?` has a public capability, offline parser tests, and wrong-model rejection tests. Every other command domain remains disabled until the local programming guide has been audited.

## Coverage status

| Command domain | WaveBench capability | Current status | Exit condition |
| --- | --- | --- | --- |
| Instrument identity | `source.idn` | Implemented for both documented response formats | Controlled hardware confirmation of model, firmware, and termination |
| System error queue | None | Disabled | Confirm the query, empty-queue semantics, and whether reads consume state |
| Basic channel status | None | Disabled | Audit CH1/CH2 read commands, units, and enums |
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
- [SIGLENT SDG Series Programming Guide](https://int.siglent.com/u_file/download/24_06_07/SDG_Programming%20Guide_PG02-E05C.pdf)
- Local guide: `doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`
- Current descriptor, driver, and fake-transport tests
