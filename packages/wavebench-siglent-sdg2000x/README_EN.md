# WaveBench SIGLENT SDG2000X Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the SIGLENT SDG2042X, SDG2082X, and SDG2122X function/arbitrary waveform generators.

## Current development baseline

Version `0.1.0` is an M0 identity-query baseline that declares only `source.idn`. The driver accepts both `*IDN?` response formats documented by the programming guide and rejects models outside the SDG2000X family. Status reads, the error queue, output control, fixed waveforms, modulation, sweep, burst, arbitrary-wave upload, and counter capabilities remain disabled.

This boundary is intentionally conservative. A command is not added to the descriptor until it has passed programming-guide review, fake-transport tests, and controlled hardware acceptance.

## Identity and compatibility

- Distribution: `wavebench-siglent-sdg2000x`
- Canonical driver ID: `siglent.sdg2000x`
- Registered models: `SDG2042X`, `SDG2082X`, `SDG2122X`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

The plugin declares no aliases and does not override a bundled WaveBench driver. Select the explicit canonical ID `siglent.sdg2000x` after installation.

## Local programming manual

Place the vendor programming guide under ignored [`doc/vendor-local/`](doc/vendor-local/README.md). The recommended filename is:

```text
SDG_Series_Programming_Guide_E05C.pdf
```

The original manual is excluded from Git and release artifacts. See the [SDG2000X coverage matrix](doc/SDG2000X_COVERAGE_MATRIX_EN.md) for public command status and the [SDG2000X coverage milestones](doc/SDG2000X_COVERAGE_MILESTONES_EN.md) for staged development gates.

## Safety boundary

- Descriptor import creates no transport and performs no instrument I/O.
- The factory opens only the core-provided transport from `DriverContext`.
- Default tests use a fake transport and neither scan resources nor connect to instruments.
- The current driver has no write methods and cannot send reset, output, or waveform-configuration commands.
- Hardware tests require separate authorization and prior confirmation of the resource, firmware, termination, output state, and restoration procedure.

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
