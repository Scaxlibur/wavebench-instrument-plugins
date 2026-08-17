# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. The current maintained packages are `wavebench-rigol-ds1000z`, `wavebench-rigol-dg4000`, the LAN-only `wavebench-rigol-dm3000`, `wavebench-rigol-dp800`, the SocketIO-data-path hardware-accepted `wavebench-rohde-schwarz-rtm2000`, the M3 query-only `wavebench-shengpu-sp3000a`, and the M0 identity-only `wavebench-siglent-sdg2000x`. The first five are optional external editions of drivers bundled with the main package. Future packages should continue the one-instrument-or-family layout without treating bundled-driver removal as a goal or defining a second manifest, installer, or catalog protocol here.

These packages target the WaveBench `v0.8.0` release and uniformly declare `wavebench>=0.8,<0.9`. They do not run with `v0.7.0` release and do not automatically assume compatibility with a future `0.9` core.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- a package-local MIT license file and SPDX package metadata;
- no real device resources, credentials, raw waveforms, or private experiment records.
