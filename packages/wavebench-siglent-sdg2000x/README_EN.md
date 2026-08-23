# WaveBench SIGLENT SDG2000X Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the SIGLENT SDG2042X, SDG2082X, and SDG2122X function/arbitrary waveform generators.

## Current development baseline

Version `0.8.2` retains the eight legacy V1 capabilities and adds `source.snapshot_v2`,
`source.basic_configure_v2`, `source.output_v2`, and `source.harmonics_disable_v2`. All four have A0
offline contracts. An `SDG2122X` running firmware `2.01.01.39R7T2` has completed A1 for the V2 snapshot and
limited A2 normal-path acceptance for Basic, Output, and Harmonic disable. A3 waveform loopback, other models
or firmware, hardware fault recovery, and release sign-off remain incomplete. C3 has audit preparation only;
it is not a completed release. See the [Source V2 A0 offline adapter record](doc/SDG2000X_SOURCE_V2_A0_EN.md),
[Source V2 A1/A2 hardware acceptance](doc/SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE_EN.md), and
[Source V2 C3 release-audit preparation](doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md).

The V1 basic surface remains `source.set_frequency`, `source.set_function`,
`source.set_amplitude_vpp`, `source.set_square_duty_cycle`, `source.output`, and read-only
`source.arbitrary_probe`. V2 Basic currently covers Sine, Square, Ramp, and Pulse function changes,
frequency, Vpp, and square duty cycle. Each request writes one field; `offset_v` is not yet exposed.
Noise/DC retain their V1 output-OFF configuration semantics: the adapter does not represent `STDEV` or a
nominal value as Vpp, and the core retains the V1 `set_function` setter when no lossless V2 state exists.
Modulation, sweep, burst, arbitrary-wave upload, and counter capabilities remain disabled.

`source.harmonics_disable_v2` only disables an observed Harmonic state; it neither configures nor enables
Harmonic. It applies to CH1/CH2 only while an `SDG2122X` with firmware `2.01.01.39R7T2` is in Sine with
the target output OFF. An already-disabled state sends no MAIN write; an enabled state sends only one
`HARMSTATE,OFF` command. The core then independently reads Harmonic and output state. Other models,
firmware revisions, and all Harmonic-configuration writes remain denied.

An `SDG2122X` running firmware `2.01.01.39R7T2` has completed hardware acceptance for the eight legacy V1
capabilities. All five basic writes passed core `SourceService` closed loops on CH1 and CH2. Harmonic,
modulation, Sweep, Burst, Pulse, Noise/DC, TARB, all 199 built-ins, Combine, phase/invert,
tracking/coupling/copy, and auxiliary global state also completed protocol or A4 acceptance where available
wiring allowed it. This evidence does not establish Source V2 A3. The maximum measured output was 4.24
Vpp; a final independent read-only session confirmed Sine / 1 kHz / 4 Vpp / OFF on both channels, with all
composite modes other than restored original Harmonic states disabled and no RTM2032 overload.

## Identity and compatibility

- Distribution: `wavebench-siglent-sdg2000x`
- Canonical driver ID: `siglent.sdg2000x`
- Registered models: `SDG2042X`, `SDG2082X`, `SDG2122X`
- WaveBench: `>=0.8.24,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

The plugin declares no aliases and does not override a bundled WaveBench driver. Select the explicit canonical ID `siglent.sdg2000x` after installation.

## Local programming manual

The vendor programming guide is stored under ignored [`doc/vendor-local/`](doc/vendor-local/README.md):

```text
SDG_Series_Programming_Guide_E05C.pdf
```

The original manual is excluded from Git and release artifacts. See the [SDG2000X coverage matrix](doc/SDG2000X_COVERAGE_MATRIX_EN.md) for command-domain status and the [SDG2000X coverage milestones](doc/SDG2000X_COVERAGE_MILESTONES_EN.md) for staged gates. Final dual-channel evidence for the basic public surface is in [public Source API acceptance](doc/SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE_EN.md); the remaining domain-specific evidence is listed under “Public references.”

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

Change `access` to `read_write` before calling a basic Source write capability. With `read_only`, identity and status remain available while the core denies writes. `check_errors = false` records that no error-queue capability has been accepted; the driver does not pretend to perform an error-queue check.

## Safety boundary

- Descriptor import creates no transport and performs no instrument I/O.
- The factory opens only the core-provided transport from `DriverContext`.
- Default tests use a fake transport and neither scan resources nor connect to instruments.
- Before enabling, `source.output` requires FIX mode, sweep OFF, known Vpp amplitude and offset, every known composite-wave mode OFF, and core enforcement of `max_source_vpp`.
- `source.set_frequency` enforces model/function limits. Automatic Sweep-to-FIX selection is allowed only while output is OFF.
- `source.set_amplitude_vpp` accepts 2 mVpp through 10 Vpp and requires the amplitude-plus-offset envelope to remain within ±10 V.
- `source.set_function` allows live switching among four bounded periodic waves. Noise/DC require output OFF and do not bypass output-enable safety.
- `source.set_square_duty_cycle` applies only to FIX-mode square waves. Frequency-dependent clamping must fail readback closed.
- Source V2 Basic and Output MAIN each send one audited write, followed by an independent core snapshot. The contract permits independent outputs to be ON together, but that combination has no Source V2 hardware acceptance yet.
- Source V2 Harmonic disable applies only to the exact runtime model/firmware while Sine and output OFF are proven; it does not configure or enable Harmonic, sends no write when already disabled, and otherwise sends at most one `HARMSTATE,OFF` before the core independently reads Harmonic and output state.
- Source V2 does not guess a Noise/DC Vpp. Legacy `set_function` calls without a lossless V2 representation retain the V1 setter; output enable still requires final readable Vpp and Offset.
- Each target configuration is written once. Any post-write failure attempts OFF recovery and latches all configuration writes for the session.
- Other advanced command domains have separate hardware evidence, but their write capabilities remain disabled until the core has lossless models; no raw-SCPI endpoint is exposed.
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
- [SDG2000X basic-write hardware acceptance](doc/SDG2000X_BASIC_WRITE_ACCEPTANCE_EN.md)
- [SDG2000X Source V2 A0 offline adapter record](doc/SDG2000X_SOURCE_V2_A0_EN.md)
- [SDG2000X Source V2 A1/A2 hardware acceptance](doc/SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE_EN.md)
- [SDG2000X Source V2 C3 release-audit preparation](doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md)
- [Source V2 capability, state, and composite-output safety RFC](doc/RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md)
- [SDG2000X harmonic protocol and spectrum acceptance](doc/SDG2000X_HARMONIC_ACCEPTANCE_EN.md)
- [SDG2000X modulation protocol and waveform acceptance](doc/SDG2000X_MODULATION_ACCEPTANCE_EN.md)
- [SDG2000X sweep protocol and waveform acceptance](doc/SDG2000X_SWEEP_ACCEPTANCE_EN.md)
- [SDG2000X Burst protocol and waveform acceptance](doc/SDG2000X_BURST_ACCEPTANCE_EN.md)
- [SDG2000X Pulse protocol and waveform acceptance](doc/SDG2000X_PULSE_ACCEPTANCE_EN.md)
- [SDG2000X read-only arbitrary probe acceptance](doc/SDG2000X_ARBITRARY_PROBE_ACCEPTANCE_EN.md)
- [SDG2000X full built-in arbitrary catalog acceptance](doc/SDG2000X_BUILTIN_ARB_ACCEPTANCE_EN.md)
- [SDG2000X special-waveform protocol and hardware acceptance](doc/SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE_EN.md)
- [SDG2000X dual-channel waveform Combine acceptance](doc/SDG2000X_COMBINE_ACCEPTANCE_EN.md)
- [SDG2000X phase mode, equal-phase, and invert acceptance](doc/SDG2000X_PHASE_INVERT_ACCEPTANCE_EN.md)
- [SDG2000X tracking, coupling, copy, and dual-trigger acceptance](doc/SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE_EN.md)
- [SDG2000X auxiliary and global-state read-only acceptance](doc/SDG2000X_AUXILIARY_READONLY_ACCEPTANCE_EN.md)
- [SDG2000X public Source API dual-channel acceptance](doc/SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE_EN.md)
