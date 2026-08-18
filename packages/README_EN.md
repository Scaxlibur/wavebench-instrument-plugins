# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. The installable packages include five optional external editions of bundled drivers, the M3 query-only `wavebench-shengpu-sp3000a`, the Source V2 C3-audited `wavebench-siglent-sdg2000x`, and `wavebench-siglent-sds800x-hd` `0.6.0`, with SDS804X HD acceptance for waveform transfer, PNG screenshots, and standalone acquisition control. Future packages should continue the one-instrument-or-family layout without treating bundled-driver removal as a goal or defining a second manifest, installer, or catalog protocol here.

Each package declares its own WaveBench `0.8.x` minimum. SDS800X HD `0.6.0` requires `wavebench>=0.8.23,<0.9`, and SDG2000X `0.8.2` requires `wavebench>=0.8.24,<0.9`. These packages do not run with `v0.7.0` and do not automatically assume compatibility with a future `0.9` core.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- a package-local MIT license file and SPDX package metadata;
- no real device resources, credentials, raw waveforms, or private experiment records.

## Incubation directory

- [`wavebench-siglent-sds3000`](wavebench-siglent-sds3000/README_EN.md): an early SIGLENT SDS3000 family directory whose MAUI programming manual is under review, initially targeting the SDS3054.

Before its protocol boundary is frozen, an incubation directory provides no `pyproject.toml`, entry point, or capability. The repository development environment skips such directories so an unaudited driver does not enter the maintained plugin set.
