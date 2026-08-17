# WaveBench Instrument Plugins

[中文](../README.md)

This repository is reserved for independently packaged WaveBench instrument plugins. The intended layout is one package per instrument or instrument family, with each package discovered by WaveBench as an external driver.

## Current status

The source packages are maintained independently: `wavebench-rigol-ds1000z`, `wavebench-rigol-dg4000`, the LAN-only `wavebench-rigol-dm3000`, `wavebench-rigol-dp800`, and `wavebench-rohde-schwarz-rtm2000` have completed offline, managed-lifecycle, and controlled hardware acceptance; `wavebench-shengpu-sp3000a` is at SP30120 M3.5 with a minimal query-only descriptor and five certified vendor-specific RF-OFF controls; `wavebench-siglent-sds800x-hd` is at `0.3.0` with offline-verified strict identity, analog-channel coupling, and conservative stopped-record `DMAX` waveform reads, while hardware acceptance remains pending. The first five are optional external editions of drivers that remain bundled with WaveBench for first-use operation; they provide an independent upgrade, transport, and extension path rather than replacing or deprecating the bundled baseline. WaveBench v0.8.0 provides local package inspection and managed install, status, upgrade, downgrade, removal, and conservative transaction recovery. This repository owns plugin source packages and does not duplicate the installer or a remote catalog.

> [!IMPORTANT]
> The WaveBench `v0.7.0` release does not contain Instrument API V2, the managed plugin lifecycle, or canonical override slots. These packages target the WaveBench `v0.8.0` release and uniformly require `wavebench>=0.8,<0.9`; they do not run with `v0.7.0` and do not assume compatibility with a future `0.9` core.

## Planned layout

```text
packages/
├── wavebench-rigol-dg4000/
├── wavebench-rigol-dm3000/
├── wavebench-rigol-dp800/
├── wavebench-rigol-ds1000z/
├── wavebench-rohde-schwarz-rtm2000/
├── wavebench-shengpu-sp3000a/
├── wavebench-siglent-sds800x-hd/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

Each Python plugin is an independent distribution registered through the `wavebench.instruments` entry-point group with a canonical driver ID. Trusted Python drivers may implement complex protocols. The executable boundary for declarative SCPI packages has not been finalized.

## Bundled baseline and external editions

WaveBench permanently bundles the RTM2000, DS1000Z, DG4000, DP800, and DM3000 families. An external package supplies an optional implementation only when the user explicitly installs it and selects its canonical ID; built-in short aliases remain pinned to the bundled implementation. DG4000, DM3000, DP800, and RTM2000 use core-controlled canonical-ID plus distribution allowlist slots, and removing the package restores the bundled canonical implementation. DS1000Z uses the separate external canonical ID `rigol.ds1000z`, while built-in `ds1104` and `ds1000z` aliases remain unaffected. Historical source may call the allowlist a migration slot; that term does not imply removal of bundled drivers.

## Current plugin

- [`wavebench-rigol-ds1000z`](../packages/wavebench-rigol-ds1000z/README_EN.md): four-channel RIGOL DS1104Z / DS1000Z series, canonical ID `rigol.ds1000z`.
- [`wavebench-rigol-dg4000`](../packages/wavebench-rigol-dg4000/README_EN.md): dual-channel RIGOL DG4202 / DG4000 series, canonical ID `rigol.dg4202`.
- [`wavebench-rigol-dm3000`](../packages/wavebench-rigol-dm3000/README_EN.md): LAN-only RIGOL DM3000 / DM3058 multimeter, canonical ID `rigol.dm3000`; short aliases retain the built-in dual-backend fallback.
- [`wavebench-rigol-dp800`](../packages/wavebench-rigol-dp800/README_EN.md): RIGOL DP800 / DP832 / DP832A programmable DC power supply, canonical ID `rigol.dp800`; its short alias remains on the built-in fallback.
- [`wavebench-rohde-schwarz-rtm2000`](../packages/wavebench-rohde-schwarz-rtm2000/README_EN.md): R&S RTM2000 / RTM2032 oscilloscope, canonical ID `rohde-schwarz.rtm2032`; controlled dual-channel `DEF`, `MAX`, `DMAX`, autoscale, screenshot, and restoration acceptance is complete.

## Incubating plugin

- [`wavebench-shengpu-sp3000a`](../packages/wavebench-shengpu-sp3000a/README_EN.md): Shengpu SP30120 sweep-analyzer driver, canonical ID `shengpu.sp30120`; its descriptor declares identity only, while five certified typed vendor-specific RF-OFF controls are available and trace plus generic configuration remain disabled.
- [`wavebench-siglent-sds800x-hd`](../packages/wavebench-siglent-sds800x-hd/README_EN.md): SIGLENT SDS800X HD oscilloscope-family `0.3.0` driver, canonical ID `siglent.sds800x-hd`; it declares identity, coupling, and Stop/non-sequence `DMAX` waveform fetch, with hardware acceptance pending.

## Security boundary

Python plugins run with the permissions of the WaveBench user; they are not sandboxed. Review and trust a plugin before installing or loading it. Public repository content must not contain real instrument addresses, serial numbers, credentials, private keys, raw captures, or laboratory-specific configuration.

## License

This repository and its maintained official plugins are licensed under the [MIT License](../LICENSE). Each independent distribution also carries a license file in its package directory and declares the SPDX `MIT` identifier in package metadata.

The source is now maintained publicly. PyPI publication, version tags, and the formal contribution process remain future decisions.

## Development environment

The repository provides a standard PEP 660 editable development-environment tool. After the initial core and plugin synchronization, ordinary source edits do not require repeated installation; release gates continue to use real wheels and disposable virtual environments. See [Plugin development environment](DEVELOPMENT_EN.md).
