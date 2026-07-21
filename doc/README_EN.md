# WaveBench Instrument Plugins

[中文](../README.md)

This repository is reserved for independently packaged WaveBench instrument plugins. The intended layout is one package per instrument or instrument family, with each package discovered by WaveBench as an external driver.

## Current status

Only the repository skeleton exists. No plugin, catalog, or package-management interface has been released yet. Package and lifecycle contracts will be introduced after WaveBench's local plugin-management design is stabilized.

## Planned layout

```text
packages/
└── wavebench-<vendor>-<instrument>/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    └── tests/
```

Each Python plugin will be an independent distribution registered through the `wavebench.instruments` entry-point group with a canonical driver ID. Trusted Python drivers may implement complex protocols. The executable boundary for declarative SCPI packages has not been finalized.

## Security boundary

Python plugins run with the permissions of the WaveBench user; they are not sandboxed. Review and trust a plugin before installing or loading it. Public repository content must not contain real instrument addresses, serial numbers, credentials, private keys, raw captures, or laboratory-specific configuration.

## Development note

No open-source license or remote repository has been selected yet. Release, compatibility, and contribution policies will be added when the first plugin enters development.
