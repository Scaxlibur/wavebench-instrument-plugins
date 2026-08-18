# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. It now also contains `wavebench-rigol-mso8000`: its first target is MSO8104, and version `0.1.0` has only an offline `scope.idn` contract with no hardware connection. DG4000, DM3000, DP800, DS1000Z, and RTM2000 are optional external editions of bundled drivers; MSO8000 and Shengpu SP3000A use independent canonical IDs. Future packages keep the one-instrument-or-family layout and do not define a second manifest, installer, or catalog protocol here.

These packages target WaveBench `0.8.x`, declare the minimum version required by their public API usage, and exclude a future `0.9` core. MSO8000 currently requires `wavebench>=0.8.22,<0.9`.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- a package-local MIT license file and SPDX package metadata;
- no real device resources, credentials, raw waveforms, or private experiment records.
