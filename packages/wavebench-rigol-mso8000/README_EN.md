# WaveBench RIGOL MSO8000 Plugin (In Development)

This directory is the starting point for a WaveBench plugin for the RIGOL MSO8000 series, with the MSO8104 as the first target model. The MSO8104 is a 1 GHz, four-analog-channel mixed-signal oscilloscope; the programming guide also covers the MSO8064 and MSO8204.

## Current status

The M0 contract and distribution boundary are documented, while the M1 identity plugin is not active yet. This is not currently an installable distribution and does not claim an implemented capability. `pyproject.toml` remains absent so the repository-level `scripts/dev_env.py` skips an unfinished descriptor.

This development pass is offline-only. It uses the manual, FakeTransport tests, fault injection, builds, and installation lifecycle checks, and does not connect to hardware. Model, firmware, transport, throughput, restoration, and measurement claims remain unverified.

Planned identity, to be frozen after manual review and FakeTransport tests:

- Distribution: `wavebench-rigol-mso8000`
- Canonical driver ID: `rigol.mso8104`
- Kind: `scope`
- Target model: `MSO8104`
- Python: `>=3.11`
- WaveBench: `>=0.8.22,<0.9`

## Directory layout

- `doc/vendor-local/`: local vendor manuals. Keep the original PDF and the converted Markdown here; all files except its README are ignored and excluded from distributions.
- `src/wavebench_rigol_mso8000/`: descriptor and driver placeholders.
- `tests/`: FakeTransport unit tests; default tests must not connect to hardware.
- `pyproject.toml.example`: metadata and entry-point template for formal activation. Copy it to `pyproject.toml` only after the descriptor, driver, and tests are ready, then update the repository package lists and environment tests.
- `doc/`: public coverage matrices and acceptance notes. Keep vendor source material out of public documentation.

## Design documents

- [MSO8104 coverage milestones](doc/MSO8104_COVERAGE_MILESTONES_EN.md)
- [MSO8104 programming-guide coverage matrix](doc/MSO8104_COVERAGE_MATRIX_EN.md)

## Safety boundary

Descriptor import must not open a transport, scan ports, send SCPI, or create files. Never commit real resources, serial numbers, credentials, captures, screenshots, or command logs. Do not blindly retry instrument writes or acquisition triggers. When the core lacks a required safety interface, add an RFC and skip the capability instead of adding a raw SCPI escape hatch.
