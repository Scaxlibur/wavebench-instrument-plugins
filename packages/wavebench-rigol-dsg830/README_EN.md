# WaveBench RIGOL DSG830 Plugin

[中文](README.md)

This is a WaveBench executable instrument plugin for the RIGOL DSG830 RF signal generator. The
DSG800 programming guide covers DSG830 and DSG815; this initial package registers DSG830 only.

## Current status

Version `0.2.0` completes the RF M0 read-only migration, M1 offline CW mapping, and M2 offline output
mapping: its descriptor uses `kind="rf_source"`, declares one `rf_out` port with
static limits and a 50-ohm dBm reference, and ships a strict snapshot parser plus one-write
`:FREQ`/`:LEV`/`:OUTP ON|OFF` driver mappings.

A1 read-only evidence and A2 controlled-output evidence have completed and been reviewed. The production descriptor
declares `rf_source.idn`, `rf_source.snapshot`, and `rf_source.output`. With a `read_write` session and complete
per-port safety configuration, Core Service, CLI, and the run step may perform one-port RF ON/OFF with a fresh
snapshot and independent readback. The example configuration remains `read_only` and does not enable output by default.

The local A2 controlled-output harness, regression tests, and resource-free setup template remain in the source
checkout as regression protection for this acceptance protocol. The evidence confirms final RF OFF; after the
production descriptor declares `rf_source.output`, the harness refuses reruns so a temporary descriptor cannot bypass
the production capability. M1 CW writes still require A3 and are not authorized by this A2 acceptance.

The production descriptor declares no error queue, CW write, modulation, Pulse, Sweep, trigger, or arbitrary SCPI
passthrough. `rf_source.output` covers only audited `rf_out` ON/OFF; every other capability remains behind its A3–A5
evidence gate.

## Development documentation

- [DSG830 plugin documentation](doc/README_EN.md)
- [DSG830 coverage milestones](doc/DSG830_COVERAGE_MILESTONES_EN.md)
- [A2 local-evidence setup template](tools/a2_output_evidence.setup.template.toml)

The milestone document distinguishes the current seed, offline contracts, and A1–A5 hardware evidence. A
production descriptor capability is not promoted by seed code or fake-transport tests alone.

## Identity and compatibility

- Distribution: `wavebench-rigol-dsg830`
- Canonical driver ID: `rigol.dsg830`
- Registered model: `DSG830`
- WaveBench: `>=0.8.25,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`
- Manual-backed connection routes: USB and LAN

The plugin declares no alias and does not replace a bundled WaveBench driver. Configure canonical ID
`rigol.dsg830` explicitly.

## Local programming guide

Store vendor source material in the ignored [`doc/vendor-local/`](doc/vendor-local/README.md) directory.
Recommended filenames:

```text
DSG800_ProgrammingGuide_EN.pdf
DSG800_ProgrammingGuide_EN.md
```

The official source is [DSG800 ProgrammingGuide V1.0](https://www.rigol.com/intl/dam/global/downloads/brochures/en/program-guide/rf-signal-generators/DSG800_ProgrammingGuide_EN.pdf).
The RIGOL download page records version `V1.0` and date `2019-09-30`. Its introduction states that the
DSG800 series includes DSG830 and DSG815 and uses DSG830 as the default command example. Do not add the
original PDF or converted copy to Git or a distribution.

## Current configuration (read-only identity and status)

This example uses an RFC 5737 documentation address and uses `read_only` access for identity and status queries:

```toml
[rf_source]
driver = "rigol.dsg830"
resource = "TCPIP::192.0.2.83::INSTR"
access = "read_only"
```

This `[rf_source]` configuration is for the production descriptor's `rf_source.idn` and `rf_source.snapshot`. It is outside the
normal source Vpp, channel, and run-plan workflow. Future energy-related capabilities also require complete
per-`port_id` safety configuration and a physical-termination declaration; the package never infers actual
termination from a connector label.

## Safety boundary

- Descriptor import does not create a transport, scan ports, or send SCPI.
- The factory opens only the configured transport through `DriverContext`.
- Default tests use fake transport only and never connect to hardware.
- The snapshot path issues only `*IDN?`, `:FREQ?`, `:LEV?`, `:OUTP?`, `:MOD:STAT?`, `:PULM:STAT?`,
  `:SWE:STAT?`, and `:STAT:QUES:POW:COND?`; A1 exposes this read-only path as a production capability.
- The production descriptor and default tests do not reset the device or change RF output, power, frequency,
  trigger, modulation, or sweep; only fake descriptors cover the frozen offline write mappings.
- Hardware testing requires separate authorization and a reviewed resource, firmware, terminator, RF-output
  state, safety limit, and restoration procedure.

## Development verification

```bash
python -m pytest -q packages/wavebench-rigol-dsg830/tests
python -m ruff check packages/wavebench-rigol-dsg830
python -m wavebench plugin package check packages/wavebench-rigol-dsg830
```

Use the repository [editable development environment](../../doc/DEVELOPMENT_EN.md) for regular source
development. Release acceptance still uses a real wheel and a disposable virtual environment.

## License

This plugin is distributed under the [MIT License](LICENSE).
