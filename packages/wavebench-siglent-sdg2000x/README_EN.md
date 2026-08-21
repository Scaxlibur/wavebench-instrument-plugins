# WaveBench SIGLENT SDG2000X Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the SIGLENT SDG2042X, SDG2082X, and SDG2122X function/arbitrary waveform generators.

## Current development baseline

Version `0.6.0` adds `source.set_frequency`, `source.set_function`, and `source.set_amplitude_vpp` to the M3 baseline. Function writes support Sine, Square, Ramp, Pulse, Noise, and DC. Noise/DC may be configured only while output is OFF and remain blocked by the output-enable safety gate. Frequency and amplitude retain model/function limits and the 10 Vpp voltage envelope. Duty-cycle, modulation, sweep, burst, arbitrary-wave upload, and counter capabilities remain disabled.

An `SDG2122X` running firmware `2.01.01.39R7T2` has completed hardware acceptance for identity, CH1/CH2 status, and `source.output`. `source.set_frequency` separately passed a 2 kHz OFF-state write and a live 5 kHz ON-state write on CH2, with approximately 4.08 Vpp measured by the RTM2032. The original 1 kHz setting was restored and both outputs ended OFF. `SDG2042X` and `SDG2082X` expose the same documented command contract, but hardware evidence from the `SDG2122X` is not extrapolated to them.

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

The original manual is excluded from Git and release artifacts. See the [SDG2000X coverage matrix](doc/SDG2000X_COVERAGE_MATRIX_EN.md) for public command status, the [SDG2000X coverage milestones](doc/SDG2000X_COVERAGE_MILESTONES_EN.md) for staged development gates, the [read-only hardware acceptance](doc/SDG2000X_READONLY_ACCEPTANCE_EN.md), the [output-control hardware acceptance](doc/SDG2000X_OUTPUT_ACCEPTANCE_EN.md), and the [frequency-write hardware acceptance](doc/SDG2000X_FREQUENCY_ACCEPTANCE_EN.md).

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

Change `access` to `read_write` before calling a function, frequency, amplitude, or output write capability. With `read_only`, identity and status remain available while the core denies writes. `check_errors = false` records that no error-queue capability has been accepted; the driver does not pretend to perform an error-queue check.

## Safety boundary

- Descriptor import creates no transport and performs no instrument I/O.
- The factory opens only the core-provided transport from `DriverContext`.
- Default tests use a fake transport and neither scan resources nor connect to instruments.
- Before enabling, `source.output` requires FIX mode, sweep OFF, known Vpp amplitude and offset, every known composite-wave mode OFF, and core enforcement of `max_source_vpp`.
- `source.set_frequency` enforces model/function limits. Automatic Sweep-to-FIX selection is allowed only while output is OFF.
- `source.set_amplitude_vpp` accepts 2 mVpp through 10 Vpp and requires the amplitude-plus-offset envelope to remain within ±10 V.
- `source.set_function` allows live switching among four bounded periodic waves. Noise/DC require output OFF and do not bypass output-enable safety.
- Each target configuration is written once. Any post-write failure attempts OFF recovery and latches all configuration writes for the session.
- Duty-cycle and advanced command-domain writes remain disabled.
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
- [SDG2000X frequency-write hardware acceptance](doc/SDG2000X_FREQUENCY_ACCEPTANCE_EN.md)
