# WaveBench Instrument Plugins

[中文](../README.md)

This repository is reserved for independently packaged WaveBench instrument plugins. The intended layout is one package per instrument or instrument family, with each package discovered by WaveBench as an external driver.

## Current status

The first source packages are now maintained independently: `wavebench-rigol-ds1000z` has completed offline lifecycle acceptance and its first hardware regression, while `wavebench-rigol-dg4000` has completed protocol migration and offline acceptance. WaveBench 0.7 already provides local package inspection and managed install, status, upgrade, downgrade, removal, and conservative transaction recovery. This repository owns plugin source packages and does not duplicate the installer or a remote catalog.

## Planned layout

```text
packages/
├── wavebench-rigol-ds1000z/
├── wavebench-rigol-dg4000/
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

## Security boundary

Python plugins run with the permissions of the WaveBench user; they are not sandboxed. Review and trust a plugin before installing or loading it. Public repository content must not contain real instrument addresses, serial numbers, credentials, private keys, raw captures, or laboratory-specific configuration.

## Development note

No remote repository or repository-wide open-source license has been selected yet. The DS1000Z package preserves the MIT package metadata of the WaveBench pilot from which it was migrated; the DG4000 package has no selected license. Release and contribution policies still require an explicit decision.
