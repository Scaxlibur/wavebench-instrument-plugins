# WaveBench RIGOL DP800 plugin

[中文](README.md)

An executable WaveBench instrument plugin for the RIGOL DP800 family, with DP832/DP832A
as the current public compatibility scope.

## Identity and development baseline

- distribution: `wavebench-rigol-dp800`
- canonical driver ID: `rigol.dp800`
- development baseline: WaveBench `a3e13fd`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- transport backend: `pyvisa`

This plugin targets the WaveBench `v0.8.0` release. It does not maintain a legacy-core
compatibility matrix, run with `v0.7.0`, or automatically claim compatibility with a future `0.9` core. When installed, the explicit canonical ID `rigol.dp800` selects the external
implementation. The short alias `dp800` always selects WaveBench's built-in fallback. Removing the
plugin restores the built-in implementation for the canonical ID as well.

## Capabilities

- `*IDN?` and error queue;
- channel setpoints, output state, CV/CC mode, and voltage/current/power measurements;
- voltage and current-limit settings;
- explicit output control;
- OVP/OCP thresholds, enable states, and trip states.

The plugin owns DP800 SCPI, parsing, and readback. WaveBench core retains safety limits, protection
relationships, pre-output checks, services, run plans, and experiment-level state restoration.
Failed writes are not retried blindly.

## Configuration example

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.50::INSTR"

[safety_limits]
max_power_voltage_v = 5.0
max_power_current_limit_a = 0.2

[power]
driver = "rigol.dp800"
default_channel = 1
check_errors = true
settle_ms_after_set = 2000
settle_ms_after_output = 500
```

The example uses an RFC 5737 documentation address. Offline tests do not scan resources, connect to
instruments, or send real SCPI.

## Acceptance status

Version 0.2.0 completes M1 read-path hardening: the first channel access identifies a supported
model and channel count through `*IDN?`; `APPLy?`, `MEASure:ALL?`, and OVP/OCP thresholds reject
non-finite values; output, mode, protection-enable, and trip responses use strict enums; and any
query failure fails an aggregate snapshot as a whole. On 2026-07-27, all three DP832A channels
passed a 31-query, zero-write hardware gate with all outputs left OFF. This evidence is not
extrapolated to other models and does not establish measurement accuracy. The driver recognizes
channel counts for DP811/821/831/832 and A-models and fails closed, but public compatibility is not
expanded to DP811/821/831 until the corresponding write paths are accepted per model.

Version 0.1.0 completed controlled DP832A LAN acceptance with a real wheel on 2026-07-24. Managed
installation, healthy/load checks, canonical-versus-short-alias routing, three-channel read-only
status and protection snapshots, conservative CH1 voltage/current-limit writes, OVP/OCP write and
readback, unloaded output ON/OFF, removal fallback, and reinstallation all passed. All three channels
were snapshotted before mutation; a separate session then confirmed exact restoration, all outputs
OFF, and an empty error queue. The acceptance did not modify the real `wavebench.toml` or commit real
addresses, serial numbers, snapshots, measurements, or command logs.

See the [DP800 programming-manual coverage matrix](doc/DP800_COVERAGE_MATRIX_EN.md) for the manual
command domains, public API mapping, evidence levels, uncovered areas, and commands denied by
default. The [DP800 command coverage development milestones](doc/DP800_COVERAGE_MILESTONES_EN.md)
define each stage's exact commands, safety boundary, and acceptance gate.

## Development checks

```bash
python -m pytest -q packages/wavebench-rigol-dp800/tests
python -m ruff check packages/wavebench-rigol-dp800
python -m wavebench plugin package check packages/wavebench-rigol-dp800
```

Do not commit real addresses, serial numbers, setpoint snapshots, measurements, or command logs.
This package is licensed under the [MIT License](LICENSE).

## Origin

Version 0.1.0 was migrated from the built-in DP800 protocol implementation at WaveBench `a3e13fd`.
Only the vendor driver, descriptor, entry point, and FakeTransport tests moved into this package.
