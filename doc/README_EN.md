# WaveBench Instrument Plugins

[中文](../README.md)

This repository maintains independently installable WaveBench instrument plugins. Each package targets one instrument or a closely related model family and registers its drivers through the `wavebench.instruments` entry-point group.

## Start here

- [Find plugins, models, compatibility ranges, and declared capabilities](reference/plugin-catalog-en.md)
- [Browse plugin packages](../packages/README_EN.md)
- [Install and manage plugins with WaveBench Core](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)
- [Develop a WaveBench plugin](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md)
- [Configure this repository's editable development environment](DEVELOPMENT_EN.md)
- [Read plugin-side interface proposals and historical records](rfcs/README.md)

## Repository responsibility

This repository owns model-specific behavior, vendor SCPI, private parameters, instrument quirks, model profiles, capability declarations, and hardware evidence. Each package's `pyproject.toml` and production descriptor are authoritative for its metadata version, entry points, compatibility range, and current capabilities. The generated [plugin catalog](reference/plugin-catalog-en.md) reads those sources directly.

WaveBench Core owns the common CLI, plugin installation and management, configuration model, run plans, artifacts, safety contract, sessions and recovery, and the plugin API. This repository documents only model-specific boundaries and links common workflows to the [WaveBench Core documentation](https://github.com/Scaxlibur/wavebench/tree/master/docs).

## Package layout

Each plugin is an independent Python distribution and may declare one or more canonical driver IDs:

```text
packages/wavebench-<vendor>-<instrument>/
├── pyproject.toml
├── README.md
├── README_EN.md
├── src/
└── tests/
```

A package README identifies supported models, the minimum configuration, and safety boundaries. The descriptor declares exact capabilities. Milestones, RFCs, and acceptance records preserve design and hardware evidence but do not replace the current Reference.

## Security boundary

Python plugins run with the permissions of the WaveBench user and are not sandboxed. Confirm the source and review the code before installation or loading. Public content must not contain real instrument addresses, serial numbers, credentials, private keys, raw captures, or laboratory-specific configuration.

Default tests use fake transports and do not connect to real instruments. Hardware operations still require separate authorization and must follow the WaveBench Core safety and recovery contracts.

## Development and contribution

See the [development environment guide](DEVELOPMENT_EN.md) for this repository's test and packaging entry points. Plugin changes should also follow the Core [plugin development guide](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md) and [instrument driver guide](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/instrument-drivers.md).

## License

This repository and its maintained official plugins use the [MIT License](../LICENSE). Each distribution also carries a package-local license file and declares the SPDX `MIT` identifier in its package metadata.
