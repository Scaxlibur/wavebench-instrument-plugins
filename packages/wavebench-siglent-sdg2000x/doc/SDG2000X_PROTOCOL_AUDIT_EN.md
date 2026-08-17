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
| `C<n>:OUTP?` | Output state, load, and polarity | `SourceStatus.output`; load and polarity are reserved for a later profile | Used by M2 |
| `C<n>:BSWV?` | Current basic-wave type and applicable unit-bearing parameters | Function, frequency, amplitude, offset, phase, duty cycle, and `apply_raw` in `SourceStatus` | Used by M2 |
| `C<n>:SWWV?` | `STATE,OFF`, or the complete sweep parameters when enabled | `SourceStatus.frequency_mode` and `sweep_enabled` | Used by M2 |
| `C<n>:MDWV?` | `STATE,OFF`, or modulation type and complete parameters | Future modulation profile | Audited, not exposed |
| `C<n>:BTWV?` | `STATE,OFF`, or burst and carrier parameters | Future burst profile | Audited, not exposed |
| `C<n>:SYNC?` | Sync state and source type | Future dedicated sync model | Audited, not exposed |

`<n>` is restricted to `1` or `2`. The M2 read order is frozen as identity validation, `OUTP?`, `BSWV?`, and `SWWV?`; the operation must issue no writes.

## Core interface mapping

M2 declares only `source.status` and returns the public core model `wavebench.instruments.SourceStatus`.

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
- All write capabilities: this phase sends no output, fixed-wave, sweep, burst, trigger, or arbitrary-wave writes.
- Raw SCPI: no escape hatch bypasses capabilities, transport guards, or parameter validation.

## Offline acceptance

- Fake transports cover CH1 and CH2, and complete status reads always leave the write list empty.
- Numeric units are parsed explicitly. Non-finite values, unknown units, wrong channel headers, missing required fields, and duplicate fields raise `DataError`.
- Declared capabilities pass the core `validate_declared_capabilities` check.
- Isolated wheel installation, entry-point discovery, vendor-manual exclusion from sdist, and the full repository test suite pass.
