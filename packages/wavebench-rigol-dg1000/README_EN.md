# WaveBench RIGOL DG1000 Plugin

[中文](README.md)

An executable WaveBench instrument plugin for dual-channel RIGOL DG1022, DG1022A, DG1022Z,
DG1032Z, DG1062Z, and compatible DG1000/DG1000Z function/arbitrary waveform generators.

## Identity and compatibility

- Distribution: `wavebench-rigol-dg1000`
- Canonical driver ID: `rigol.dg1000`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

The plugin declares the canonical ID `rigol.dg1000` and no short aliases. After installation,
select it explicitly with `driver = "rigol.dg1000"` in the WaveBench configuration.

## Capabilities

- `*IDN?` and error queue;
- CH1/CH2 output, function, frequency, VPP amplitude, offset, phase, sweep state, and square duty
  cycle status;
- fixed frequency, function, VPP amplitude, and square duty-cycle settings;
- explicit output control;
- optional explicit sweep disable before setting a fixed frequency through WaveBench source config.

The public surface is intentionally limited to basic source control. The plugin does not claim the
DG4000/DG4202 arbitrary-waveform upload path, harmonic mode, modulation, burst, counter profile,
or a complete sweep profile. The DG1000 front-panel/vendor add or harmonic-superposition feature
is outside this plugin's supported surface; when it is enabled, the actual fundamental and harmonic
outputs are likely to differ from the configured values, so basic status readback must not be used
as accurate harmonic acceptance evidence. WaveBench core retains safety limits, services, run
plans, state restoration, and artifacts; this package owns only DG1000-family SCPI, parsing, and
readback.

The driver covers two known command layouts: the legacy `:CH2` suffix layout used by DG1022/DG1022A
and the `:SOUR<n>:` prefixed layout used by DG1022Z/DG1032Z/DG1062Z. Unknown models fail closed.

## Safety boundary

Descriptor import performs no instrument I/O. The factory opens only the configured transport
through WaveBench `DriverContext`. Default offline tests use FakeTransport only; they do not scan
resources, connect to instruments, or send real SCPI. After an ambiguous write, the driver instance
latches later configuration writes off and requires the caller to reopen the session and verify
instrument state independently.

The example uses an RFC 5737 documentation address:

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.30::INSTR"

[source]
driver = "rigol.dg1000"
default_channel = 1
check_errors = true
ensure_fix_mode_on_set_frequency = true
settle_ms_after_set_frequency = 500
```

Do not commit real addresses, serial numbers, waveforms, screenshots, or command logs.

## License

This plugin is licensed under the [MIT License](LICENSE).

## Development checks

Run the package tests, Ruff, WaveBench package inspection, and a managed-install dry run from an
environment containing the matching WaveBench `v0.8.0` release.

```bash
python -m pytest -q packages/wavebench-rigol-dg1000/tests
python -m ruff check packages/wavebench-rigol-dg1000
python -m wavebench plugin package check packages/wavebench-rigol-dg1000
python -m wavebench plugin install packages/wavebench-rigol-dg1000 --dry-run
```

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for daily
source work. Formal acceptance still uses a real wheel and a disposable virtual environment.

## Hardware acceptance boundary

The public `0.1.0` gate currently covers offline FakeTransport tests, managed-install lifecycle
checks, and wheel checks. A DG1032Z-to-oscilloscope closed-loop bench can serve as a future
hardware gate. Until a reproducible, sanitized hardware record exists, this package does not
extrapolate DG1032Z behavior to other DG1000/DG1000Z models or to the legacy DG1022/DG1022A
command layout.

Hardware records must not commit real resources, serial numbers, raw waveforms, screenshots, or
command logs. The current capability surface still means basic source control only; it does not
cover arbitrary-waveform upload, offset/symmetry setters, modulation, burst, counter, or a complete
sweep profile.

## Provenance

- `0.1.0` migrated the WaveBench core DG1000 draft into an independent plugin package, preserving
  the vendor driver, descriptor, entry point, and FakeTransport tests. The package currently
  declares only basic source capabilities.
