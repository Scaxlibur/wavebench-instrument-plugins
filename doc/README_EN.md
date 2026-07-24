# WaveBench Instrument Plugins

[中文](../README.md)

This repository is reserved for independently packaged WaveBench instrument plugins. The intended layout is one package per instrument or instrument family, with each package discovered by WaveBench as an external driver.

## Current status

The source packages are maintained independently: `wavebench-rigol-ds1000z`, `wavebench-rigol-dg4000`, the LAN-only `wavebench-rigol-dm3000`, and `wavebench-rigol-dp800` have completed offline, managed-lifecycle, and controlled hardware acceptance; `wavebench-rohde-schwarz-rtm2000` has entered offline migration and is awaiting controlled dual-channel RTM2032 hardware acceptance; `wavebench-shengpu-sp3000a` is at the SP30120 query-only M3 stage. WaveBench 0.7 already provides local package inspection and managed install, status, upgrade, downgrade, removal, and conservative transaction recovery. This repository owns plugin source packages and does not duplicate the installer or a remote catalog.

## Planned layout

```text
packages/
├── wavebench-rigol-dg4000/
├── wavebench-rigol-dm3000/
├── wavebench-rigol-dp800/
├── wavebench-rigol-ds1000z/
├── wavebench-rohde-schwarz-rtm2000/
├── wavebench-shengpu-sp3000a/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

Each Python plugin is an independent distribution registered through the `wavebench.instruments` entry-point group with a canonical driver ID. Trusted Python drivers may implement complex protocols. The executable boundary for declarative SCPI packages has not been finalized.

## Current plugin

- [`wavebench-rigol-ds1000z`](../packages/wavebench-rigol-ds1000z/README_EN.md): four-channel RIGOL DS1104Z / DS1000Z series, canonical ID `rigol.ds1000z`.
- [`wavebench-rigol-dg4000`](../packages/wavebench-rigol-dg4000/README_EN.md): dual-channel RIGOL DG4202 / DG4000 series, canonical ID `rigol.dg4202`.
- [`wavebench-rigol-dm3000`](../packages/wavebench-rigol-dm3000/README_EN.md): LAN-only RIGOL DM3000 / DM3058 multimeter, canonical ID `rigol.dm3000`; short aliases retain the built-in dual-backend fallback.
- [`wavebench-rigol-dp800`](../packages/wavebench-rigol-dp800/README_EN.md): RIGOL DP800 / DP832 / DP832A programmable DC power supply, canonical ID `rigol.dp800`; it targets the current WaveBench HEAD and keeps the short alias on the built-in fallback.
- [`wavebench-rohde-schwarz-rtm2000`](../packages/wavebench-rohde-schwarz-rtm2000/README_EN.md): R&S RTM2000 / RTM2032 oscilloscope, canonical ID `rohde-schwarz.rtm2032`; offline migration is complete and controlled dual-channel hardware acceptance remains pending.

## Incubating plugin

- [`wavebench-shengpu-sp3000a`](../packages/wavebench-shengpu-sp3000a/README_EN.md): query-only Shengpu SP30120 sweep-analyzer driver, canonical ID `shengpu.sp30120`; only the verified identity capability is declared while trace and write operations remain disabled.

## Security boundary

Python plugins run with the permissions of the WaveBench user; they are not sandboxed. Review and trust a plugin before installing or loading it. Public repository content must not contain real instrument addresses, serial numbers, credentials, private keys, raw captures, or laboratory-specific configuration.

## License

This repository and its maintained official plugins are licensed under the [MIT License](../LICENSE). Each independent distribution also carries a license file in its package directory and declares the SPDX `MIT` identifier in package metadata.

The source is now maintained publicly. PyPI publication, version tags, and the formal contribution process remain future decisions.

## Development environment

The repository provides a standard PEP 660 editable development-environment tool. After the initial core and plugin synchronization, ordinary source edits do not require repeated installation; release gates continue to use real wheels and disposable virtual environments. See [Plugin development environment](DEVELOPMENT_EN.md).
