# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. The current installable packages are `wavebench-rigol-ds1000z`, `wavebench-rigol-dg4000`, the LAN-only `wavebench-rigol-dm3000`, `wavebench-rigol-dp800`, the SocketIO-data-path hardware-accepted `wavebench-rohde-schwarz-rtm2000`, the M3 query-only `wavebench-shengpu-sp3000a`, and `wavebench-siglent-sds800x-hd` `0.6.0`, with SDS804X HD acceptance for waveform transfer, PNG screenshots, and standalone acquisition control. The first five are optional external editions of drivers bundled with the main package. Future packages should continue the one-instrument-or-family layout without treating bundled-driver removal as a goal or defining a second manifest, installer, or catalog protocol here.

Each package declares its own WaveBench `0.8.x` minimum. SDS800X HD `0.6.0` requires `wavebench>=0.8.23,<0.9`. These packages do not run with `v0.7.0` and do not automatically assume compatibility with a future `0.9` core.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- a package-local MIT license file and SPDX package metadata;
- no real device resources, credentials, raw waveforms, or private experiment records.
