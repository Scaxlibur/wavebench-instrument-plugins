# WaveBench RIGOL DM3000 Plugin

Executable WaveBench driver plugin for RIGOL DM3000/DM3058 digital multimeters. This
package supports LAN/VXI-11 connections through PyVISA only.

## Identity and migration boundary

- Distribution: `wavebench-rigol-dm3000`
- Canonical driver ID: `rigol.dm3000`
- WaveBench: `>=0.8.11,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa` (LAN only)
- VISA resource scheme: `TCPIP`; `ASRL`, `USB`, and `GPIB` are rejected

This package targets WaveBench `v0.8.11` and does not automatically claim compatibility with a future `0.9` core.

The plugin declares no aliases. When installed, the canonical ID selects this external LAN
implementation. The short aliases `dm3000` and `dm3058` keep resolving to WaveBench's built-in
fallback with both serial and PyVISA support. Removing the plugin restores the built-in
implementation for the canonical ID as well.

An explicit serial backend is rejected for the external canonical driver. A non-TCPIP VISA
resource such as `ASRL`, `USB`, or `GPIB` is also rejected for `lan`, `visa`, and `pyvisa`
backends before any transport opens. Use a short alias when the built-in RS-232 path is required.

## Capabilities

- `dmm.idn`
- `dmm.read`
- `dmm.function_status`
- `dmm.set_function`
- `dmm.measurement_profile`
- `dmm.trigger_status`
- `dmm.calculation_status`
- `dmm.calculation_statistics`
- `dmm.system_interface_status`
- `dmm.set_voltage_range`
- `dmm.set_dcv_impedance`

`wavebench dmm profile` does not switch function, write range, or consume the error queue. In the
DM3000 command set, range code `0` is the smallest range, not autorange. The instrument exposes no
matching query for automatic-versus-manual measurement mode, so `auto_range=n/a`. Continuity and
diode report `n/a` for range fields because no accepted range query is available for those modes.

The setters do not switch function implicitly. Voltage range accepts codes `0..4` only for the
already-active DCV or ACV function. DCV impedance accepts `10M` or `10G`, with `10G` limited to
range codes `0..2`. Both setters read before write and verify readback. A failed range transaction
latches configuration writes even when its range is restored, because any range write forces
manual measurement mode and the prior automatic/manual mode cannot be queried. An ambiguous first
write or failed restoration also latches the instance.

M4 queries do not switch function, enable or clear a calculation, or fire a trigger. The statistics
CLI requires `--calculation-active-confirmed`, and the driver independently verifies that the
currently active calculation matches the requested `average`, `min`, or `max`. The CLI commands are
`wavebench dmm trigger status`, `wavebench dmm calculation status`, and
`wavebench dmm calculation statistics average|min|max --calculation-active-confirmed`.

The M5 command `wavebench dmm system-interface status` emits only eleven allowlisted fields. Any
missing, unknown, or out-of-range response fails the whole snapshot without partial output. The
path sends no writes, `*CLS`, or error-queue queries.

The package reuses WaveBench's public `DmmReading`, `DmmDriver`, and `DmmService` contracts. It
contains only the vendor protocol implementation and its descriptor.

See the [DM3000 coverage matrix](doc/DM3000_COVERAGE_MATRIX_EN.md) for the vendor-manual command
domains, the eleven current capabilities, per-measurement offline/hardware evidence, and commands
denied by default. The local vendor manual is under ignored `doc/vendor-local/` and is excluded
from release packages.

See the [DM3000 feature-coverage milestones](doc/DM3000_COVERAGE_MILESTONES_EN.md) for the staged
implementation plan, exact hardware command surface, protocol-acceptance rules, and the accepted,
failed, and skipped boundaries from 2026-07-26. Diagnostic probes are not public capabilities and
do not establish measurement accuracy or calibration acceptance.

## Example

The address below is reserved for documentation:

```toml
[dmm]
driver = "rigol.dm3000"
backend = "lan"
resource = "TCPIP::192.0.2.40::INSTR"
timeout_ms = 3000
settle_ms_before_read = 0
settle_ms_after_function_change = 500
```

Descriptor import performs no instrument I/O. Offline tests do not discover resources or send
SCPI. Do not commit real addresses, serial numbers, readings, screenshots, or command logs.

The external wheel completed controlled LAN acceptance on 2026-07-24: managed install and
healthy/load checks, canonical-versus-alias routing, 20/20 finite DCV reads, function-status
query, a reversible cross-voltage-function switch with state restoration, managed removal with
built-in fallback, and a final canonical IDN/DCV smoke test after reinstall all passed. The
acceptance did not modify the real `wavebench.toml` and did not retain real addresses, serial
numbers, readings, or command logs. RS-232 remains outside this package and is available through
the built-in short-alias path.

Version 0.1.0 was migrated from WaveBench's built-in DM3000/DM3058 implementation and preserves
its SCPI, parsing, and error semantics. This package is licensed under the [MIT License](LICENSE).

Version 0.2.0 adds the query-only current measurement profile without changing instrument state.

Version 0.3.0 adds function-gated, readback-verified DCV/ACV range and DCV impedance setters and
corrects the earlier mislabeling of range code `0` as autorange.

Version 0.4.0 adds query-only trigger status, calculation status, and existing
min/max/average statistics; it introduces no trigger or calculation write path.

Version 0.5.0 adds a redacted query-only system/interface status snapshot. It reads only beeper,
language, numeric-format, brightness, option-presence, DHCP, GPIB-address, and RS-232 settings. It
does not query or print IDN, MAC, IP, hostname, domain, clock, or raw responses, and performs no
interface or front-panel configuration writes.
