# WaveBench SIGLENT SDG2000X Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the SIGLENT SDG2042X, SDG2082X, and SDG2122X function/arbitrary waveform generators.

## Current development baseline

Version `0.3.0` is the M3 `source.output` baseline. It declares `source.idn`, `source.status`, and `source.output`. The driver accepts both documented `*IDN?` formats and maps CH1/CH2 `OUTP?`, `BSWV?`, and `SWWV?` responses to the core `SourceStatus` model. Output control uses a complete pre-write snapshot, one target write, independent readback, fail-safe OFF recovery, and a session latch. Error-queue, fixed-wave configuration, modulation, sweep, burst, arbitrary-wave upload, and counter capabilities remain disabled.

An `SDG2122X` running firmware `2.01.01.39R7T2` has completed hardware acceptance for identity, CH1/CH2 status, and `source.output`. Both channels retained their 1 kHz, 4 Vpp, 0 V offset sine configuration, passed closed-loop measurement through high-impedance RTM2032 inputs, and ended OFF. `SDG2042X` and `SDG2082X` expose `source.output` under the same documented command contract, but hardware evidence from the `SDG2122X` is not extrapolated to them.

## Identity and compatibility

- Distribution: `wavebench-siglent-sdg2000x`
- Canonical driver ID: `siglent.sdg2000x`
- Registered models: `SDG2042X`, `SDG2082X`, `SDG2122X`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

The plugin declares no aliases and does not override a bundled WaveBench driver. Select the explicit canonical ID `siglent.sdg2000x` after installation.

## Local programming manual

The vendor programming guide is stored under ignored [`doc/vendor-local/`](doc/vendor-local/README.md):

```text
SDG_Series_Programming_Guide_E05C.pdf
```

The original manual is excluded from Git and release artifacts. See the [SDG2000X coverage matrix](doc/SDG2000X_COVERAGE_MATRIX_EN.md) for public command status, the [SDG2000X coverage milestones](doc/SDG2000X_COVERAGE_MILESTONES_EN.md) for staged development gates, the [read-only hardware acceptance](doc/SDG2000X_READONLY_ACCEPTANCE_EN.md), and the [output-control hardware acceptance](doc/SDG2000X_OUTPUT_ACCEPTANCE_EN.md).

## Configuration example

Merge this fragment into a valid `wavebench.toml` that already contains `[connection]` and `[scope]`. It uses an RFC 5737 documentation address and starts in the safer `read_only` state. Explicitly change to `read_write` for `source.output` while retaining the Vpp safety limit.

```toml
[source]
driver = "siglent.sdg2000x"
resource = "TCPIP::192.0.2.40::INSTR"
default_channel = 1
check_errors = false
access = "read_only"

[safety_limits]
max_source_vpp = 10.0
```

Change `access` to `read_write` before calling `source.output`. With `read_only`, identity and status remain available while the core denies writes. `check_errors = false` records that no error-queue capability has been accepted; the driver does not pretend to perform an error-queue check during `source.output`.

## Safety boundary

- Descriptor import creates no transport and performs no instrument I/O.
- The factory opens only the core-provided transport from `DriverContext`.
- Default tests use a fake transport and neither scan resources nor connect to instruments.
- Before enabling, `source.output` requires FIX mode, sweep OFF, known Vpp amplitude and offset, and core enforcement of `max_source_vpp`.
- The target state is written once. Any post-write failure attempts OFF recovery and latches further ON writes for the session.
- Frequency, function, amplitude, duty-cycle, and advanced command-domain writes remain disabled.
- Hardware tests require separate authorization and prior confirmation of the resource, firmware, termination, output state, safety limit, and restoration procedure.

## Development checks

```bash
python -m pytest -q packages/wavebench-siglent-sdg2000x/tests
python -m ruff check packages/wavebench-siglent-sdg2000x
python -m wavebench plugin package check packages/wavebench-siglent-sdg2000x
```

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for ordinary source work. Formal acceptance still uses a real wheel and a disposable virtual environment.

## License

This plugin is licensed under the [MIT License](LICENSE).

## Public references

- [SIGLENT SDG2000X product page](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT waveform-generator document downloads](https://siglentna.com/resources/documents/waveform-generators/)
- [SDG2000X protocol audit](doc/SDG2000X_PROTOCOL_AUDIT_EN.md)
- [SDG2000X read-only hardware acceptance](doc/SDG2000X_READONLY_ACCEPTANCE_EN.md)
- [SDG2000X output-control hardware acceptance](doc/SDG2000X_OUTPUT_ACCEPTANCE_EN.md)
