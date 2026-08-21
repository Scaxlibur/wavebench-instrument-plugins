# SDG2000X Protocol Audit

[中文](SDG2000X_PROTOCOL_AUDIT.md)

## Audit baseline

- Programming guide: SIGLENT *SDG Series Programming Guide*, revision `PG02_E05C`, 201 pages.
- Local file: `doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`.
- SHA-256: `a27c841ef10ebeba8c437be88933079b358d80d55d20b0d3bbf032cbc8b7125d`.
- Supporting material: `SDG2000X_UserManual_CN03A` and `SDG2000X_DataSheet_CN02H`.
- Supported models: `SDG2042X`, `SDG2082X`, and `SDG2122X`; all have two channels.

Vendor PDFs remain under `vendor-local/`, which Git and the sdist exclude. Public documentation records only the command facts and implementation decisions needed by the plugin.

## Communication boundary

The guide documents USB and LAN remote control. LAN supports VXI-11, Socket, and Telnet. Socket uses port `5025`, Telnet uses port `5024`, and the Socket example terminates SCPI commands with `\n`.

The plugin declares only WaveBench's existing `pyvisa` backend. It does not create Socket or Telnet connections. Transport construction, timeouts, audit logging, and configured-resource enforcement remain owned by the core `DriverContext` and transport layer.

The compatibility table marks `COMM_HEADER` as unavailable on SDG2000X. The driver must not mutate this global response-format setting. Parsers accept the documented short response headers directly and fail closed on missing, duplicate, or unknown required fields.

## Confirmed queries

| Command | Confirmed response | WaveBench mapping | Current decision |
| --- | --- | --- | --- |
| `*IDN?` | Manufacturer, model, serial, firmware; or the `*IDN,SDG,...` format | `source.idn` | Exposed |
| `C<n>:OUTP?` | Output state, load, and polarity; SDG2122X hardware also returned `POWERON_STATE` | `SourceStatus.output`; all other fields are validated and reserved for a later profile | Used by M2 |
| `C<n>:BSWV?` | Current basic-wave type and applicable unit-bearing parameters | Function, frequency, amplitude, offset, phase, duty cycle, and `apply_raw` in `SourceStatus` | Used by M2 |
| `C<n>:SWWV?` | `STATE,OFF`, or the complete sweep parameters when enabled | `SourceStatus.frequency_mode` and `sweep_enabled` | Used by M2 |
| `C<n>:MDWV?` | `STATE,OFF`, or modulation type and complete parameters | Future modulation profile | Audited, not exposed |
| `C<n>:BTWV?` | `STATE,OFF`, or burst and carrier parameters | Future burst profile | Audited, not exposed |
| `C<n>:SYNC?` | Sync state and source type | Future dedicated sync model | Audited, not exposed |

`<n>` is restricted to `1` or `2`. The M2 read order is frozen as identity validation, `OUTP?`, `BSWV?`, and `SWWV?`; the operation must issue no writes.

## Exposed write transactions

The E05C Output Command defines `C<n>:OUTP ON|OFF`. M3 maps that command to the core `source.output` capability without exposing a generic raw-SCPI escape hatch.

The E05C Basic Wave Command defines `WVTP`, `FRQ`, `AMP`, and `DUTY` writes. They map to `source.set_function`, `source.set_frequency`, `source.set_amplitude_vpp`, and `source.set_square_duty_cycle`. Function is limited to Sine, Square, Ramp, Pulse, Noise, and DC; Noise/DC require output OFF. Frequency uses model/function limits, amplitude accepts 2 mVpp through 10 Vpp, and duty cycle applies only to FIX-mode square waves.

The transaction boundary is:

- `set_output(channel, enabled, *, check_errors=True) -> SourceStatus` matches the core `SourceDriver` interface.
- Because the guide defines no error queue, `check_errors` must explicitly be `false`. Any other value is rejected before I/O.
- Before ON, the driver reads a complete `SourceStatus` and requires FIX mode, sweep OFF, and known Vpp amplitude and offset. The core `SourceService` enforces the Vpp safety limit.
- Idempotent calls do not write. Other calls send the target command once, reread complete status, and require every non-output field to remain unchanged.
- Any post-write failure latches further ON writes for the session and performs one OFF recovery plus `OUTP?` readback. Failed recovery reports uncertain output state. Emergency OFF remains available while latched.

All three registered models expose `source.output` under the same documented contract. Fake transports cover all three identities. Current hardware evidence applies only to `SDG2122X` firmware `2.01.01.39R7T2`; see the [output-control hardware acceptance](SDG2000X_OUTPUT_ACCEPTANCE_EN.md).

## Hardware-observed firmware extension

An `SDG2122X` running firmware `2.01.01.39R7T2` returned `POWERON_STATE,ON|OFF` from `OUTP?` in addition to the E05C fields. The parser accepts only this closed enum and continues to require `LOAD` and `PLRT`. The field is not mapped into the core `SourceStatus` model and does not expand any capability. See the [read-only hardware acceptance](SDG2000X_READONLY_ACCEPTANCE_EN.md) for the complete boundary.

## Core interface mapping

The current descriptor declares `source.status`, all four basic configuration writes, and `source.output`; all return the public core model `wavebench.instruments.SourceStatus`.

Harmonic Command is available only when the basic wave is SINE. The driver therefore uses state-dependent querying: non-SINE snapshots omit `HARM?`, while returning to SINE queries it again to detect a stored harmonic state that may become active. Hardware timeout evidence and injected-fault tests cover this behavior.

| `SourceStatus` field | SDG2000X source |
| --- | --- |
| `channel` | Validated requested channel |
| `output` | `ON` or `OFF` from `OUTP?` |
| `function` | `WVTP` from `BSWV?`, normalized to the core short enum |
| `frequency_hz` | `FRQ`, converted to Hz when applicable |
| `amplitude` | `AMP` when applicable |
| `amplitude_unit` | `VPP`, following the guide's `AMP` semantics |
| `offset_v` | `OFST`, converted to V when applicable |
| `phase_deg` | `PHSE` when applicable |
| `frequency_mode` | `SWE` when sweep is on, otherwise `FIX` |
| `sweep_enabled` | `STATE` from `SWWV?` |
| `apply_raw` | Raw, stripped `BSWV?` response |
| `square_duty_cycle_percent` | `DUTY` for square waves, otherwise `None` |

## Deferred capabilities

- `source.errors`: the E05C command table defines no error-queue query, empty-queue response, or consuming-read semantics.
- `source.channel_profile`: the core model requires a complete sync polarity, marker state, pulse hold, and other fields without an unambiguous one-to-one mapping in the audited command set.
- Remaining write capabilities: sweep, burst, trigger, and arbitrary-wave writes remain disabled.
- Raw SCPI: no escape hatch bypasses capabilities, transport guards, or parameter validation.

## Offline acceptance

- Fake transports cover CH1 and CH2, and complete status reads always leave the write list empty.
- Numeric units are parsed explicitly. Non-finite values, unknown units, wrong channel headers, missing required fields, and duplicate fields raise `DataError`.
- Declared capabilities pass the core `validate_declared_capabilities` check.
- Fake transports cover CH1/CH2, ON/OFF, idempotency, all three model identities, readback mismatch, state drift, ambiguous writes, OFF recovery, failed recovery, and session latching.
- Core `SourceService` safety tests allow the 10 Vpp boundary and reject 10.0001 Vpp without a write.
- Isolated wheel installation, entry-point discovery, vendor-manual exclusion from sdist, and the full repository test suite pass.
