# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. The maintained packages include five optional external editions of bundled drivers, the M3 query-only `wavebench-shengpu-sp3000a`, the Source V2 C3-audited `wavebench-siglent-sdg2000x`, `wavebench-siglent-sds3000` adopting WaveBench `0.8.24` transport/session P0, `wavebench-siglent-sds800x-hd` `0.6.0` with SDS804X HD acceptance for waveform transfer, PNG screenshots, and standalone acquisition control, and `wavebench-rigol-mso8000` `0.9.0` for MSO8104, with controlled acceptance for bounded waveform/capture, Screenshot V2, acquisition control, and cursor readout. Future packages should continue the one-instrument-or-family layout without treating bundled-driver removal as a goal or defining a second manifest, installer, or catalog protocol here.

`wavebench-rigol-dsg830` `0.2.0` participates in the repository development environment, completes the offline `rf_source` M0 migration, and requires Core `>=0.8.25,<0.9`. Its production descriptor remains `rf_source.idn` only and declares neither snapshot nor RF control before A1.

Each package declares its own WaveBench `0.8.x` minimum. SDS800X HD `0.6.0` requires `wavebench>=0.8.23,<0.9`, while SDG2000X `0.8.2`, SDS3000, and MSO8000 require `wavebench>=0.8.24,<0.9`. MSO8000 relies on current Core APIs that do not yet have an independent Core release, so it is not a compatibility-wheel release claim. These packages do not run with `v0.7.0` and do not automatically assume compatibility with a future `0.9` core.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- a package-local MIT license file and SPDX package metadata;
- no real device resources, credentials, raw waveforms, or private experiment records.

## Additional instrument families

- [`wavebench-rigol-mso8000`](wavebench-rigol-mso8000/README_EN.md): the RIGOL MSO8104 mixed-signal oscilloscope, canonical ID `rigol.mso8104`; bounded waveform/capture, Screenshot V2, acquisition control, status, and cursor-readout paths have controlled acceptance under recorded model, firmware, and LAN/PyVISA conditions.
- [`wavebench-rigol-dsg830`](wavebench-rigol-dsg830/README_EN.md): the RIGOL DSG830 RF signal generator, canonical ID `rigol.dsg830`; `0.2.0` completes the offline `rf_source` M0 migration while the production descriptor remains `rf_source.idn` only. Its [milestones](wavebench-rigol-dsg830/doc/DSG830_COVERAGE_MILESTONES_EN.md) define the A1–A5 gates.
- [`wavebench-shengpu-sp3000a`](wavebench-shengpu-sp3000a/README_EN.md): the Shengpu SP30120 sweep-analyzer plugin with a minimal query-only descriptor and certified RF-OFF controls.
- [`wavebench-siglent-sds3000`](wavebench-siglent-sds3000/README_EN.md): the early SIGLENT SDS3000 plugin, strictly supporting SDS3054 firmware `8.4.1`; identity, error registers, coupling, waveform reads, and single/dual-channel capture are implemented.
- [`wavebench-siglent-sdg2000x`](wavebench-siglent-sdg2000x/README_EN.md): the SIGLENT SDG2000X function/arbitrary waveform generator, with a completed Source V2 candidate-package audit.
- [`wavebench-siglent-sds800x-hd`](wavebench-siglent-sds800x-hd/README_EN.md): the SIGLENT SDS800X HD oscilloscope family, with accepted waveform, PNG screenshot, and standalone acquisition-control paths.

These packages provide an independent `pyproject.toml` and one canonical entry point, so they participate in the repository development environment. Incomplete capabilities are not declared.
