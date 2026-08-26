# WaveBench RIGOL DSG830 Plugin

[中文](README.md)

This is a WaveBench executable instrument plugin for the RIGOL DSG830 RF signal generator. The
DSG800 programming guide covers DSG830 and DSG815; this initial package registers DSG830 only.

## Current status

Version `0.2.0` completes the RF M0 read-only migration, M1 offline CW mapping, M2 offline output
mapping, M3 internal-sine modulation mapping, and the first M4 Pulse subset: its descriptor uses
`kind="rf_source"`, declares one `rf_out` port with static limits and a 50-ohm dBm reference, and ships a
strict snapshot parser plus one-write `:FREQ`/`:LEV`/`:OUTP ON|OFF` mappings, internal-sine AM/FM/PM
configuration/readback mappings, and internal/single Pulse timing/polarity mapping.

A1 read-only evidence, A2 controlled-output evidence, and A3 CW-loopback evidence have completed and been reviewed.
The production descriptor declares `rf_source.idn`, `rf_source.snapshot`, `rf_source.cw_configure`, and
`rf_source.output`. A `read_write` CW request requires target RF OFF and the complete OFF-only preflight; RF ON/OFF
also requires complete per-port safety configuration, a fresh snapshot, and independent readback. The example
configuration remains `read_only` and does not enable writes by default.

The local A2 controlled-output harness, regression tests, and resource-free setup template remain in the source
checkout as regression protection for this acceptance protocol. The evidence confirms final RF OFF; after the
production descriptor declares `rf_source.output`, the harness refuses reruns so a temporary descriptor cannot bypass
the production capability. A2 itself does not authorize CW; the separate A3 evidence promotes it.

The local A3 CW-loopback harness, regression tests, and resource-free setup template are also in the source checkout.
They require initial RF OFF, independent readback for two OFF-only CW writes, one low-power RF ON/OFF, and a current
CH2-buffer signal observation. CH2 only establishes visible signal; source readback remains the frequency and power
evidence. Its completed, reviewed evidence separately promotes `rf_source.cw_configure`.

The M3 driver implements offline state readback plus `get_rf_modulation_snapshot()`, `configure_rf_modulation()`, and
`disable_rf_modulation()` mappings for internal Sine only: AM depth `0–100 %`, FM deviation `0.1 Hz–1 MHz`, PM
deviation `0–5 rad`, and a `10 Hz–100 kHz` internal frequency for each mode. Core requires RF OFF, all AM/FM/PM modes
disabled, Pulse/Sweep disabled, and no active protection condition before a configuration write. The shared FM/PM
selection is read separately: when all modes are disabled, a different inactive selection may be changed to the
requested type, and postcondition then requires that target type, exactly the target mode, and the global modulation
switch. `disable_rf_modulation()` only disables the requested mode and global modulation when RF is OFF and that mode is
the only active one; it is not a reset and does not retry an uncertain write.

The source checkout includes an A4 RF-OFF modulation-evidence harness, fake regressions, and a resource-free setup
template. Each invocation validates one internal-Sine mode; after configuration readback, it disables that same mode and
the final state must establish both RF output and modulation OFF. Explicit `--recover` only restores a known single
active mode and writes a private recovery record. Explicit `--diagnose` retains the original `read_only` configuration,
reads the initial/final RF snapshots and one requested profile, and requires a zero-write transport audit. A4 does not
read CH2 or invoke RF-output control; recovery and diagnostic records are not capability-promotion evidence. The AM and
FM RF-OFF sequences passed; PM still has a strict readback mismatch, so the overall modulation capability remains closed.

The M4 Pulse subset is internal/single only. `configure_rf_pulse()` fixes source, mode, period, width, and polarity,
then ends with `:PULM:STAT OFF`; it never invokes RF output, rear Pulse I/O, or trigger commands. The source checkout
now includes `tools/a4_pulse_evidence.py`, fake regressions, and a resource-free setup template. Its `--execute` path
allows one RF-OFF/Pulse-OFF configuration and independent readback, while `--diagnose` preserves `read_only` and has a
zero-write audit. Neither path reads CH1/CH2. Hardware evidence is still pending, so `rf_source.pulse_configure` remains
outside the production descriptor.

The production descriptor declares no error queue, modulation, Pulse, Sweep, trigger, or arbitrary SCPI passthrough.
`rf_source.cw_configure` covers only audited OFF-only single-field frequency/dBm writes on `rf_out`, and
`rf_source.output` only audited `rf_out` ON/OFF. `rf_source.modulation_configure` and
`rf_source.pulse_configure` remain behind their A4 hardware evidence; a driver method or an offline test does not
promote either. Every other capability remains behind its A4–A5 evidence gate.

## Development documentation

- [DSG830 plugin documentation](doc/README_EN.md)
- [DSG830 coverage milestones](doc/DSG830_COVERAGE_MILESTONES_EN.md)
- [A2 local-evidence setup template](tools/a2_output_evidence.setup.template.toml)
- [A3 local-evidence setup template](tools/a3_cw_evidence.setup.template.toml)
- [A4 local-evidence setup template](tools/a4_modulation_evidence.setup.template.toml)
- [A4 Pulse local-evidence setup template](tools/a4_pulse_evidence.setup.template.toml)

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
- Default tests use fake transport and never connect to hardware. A normal production `read_only` configuration does
  not reset the device or change RF output, power, frequency, trigger, modulation, or sweep; A2/A3 evidence separately
  opens safety-gated output and OFF-only CW, while ordinary writes still require explicit `read_write`, capability, and
  complete preflight.
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
