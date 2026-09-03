# Plugin packages

[中文](README.md)

`packages/` contains the independently packaged WaveBench plugin distributions maintained in this repository. Each subdirectory targets one instrument or a closely related model family.

## Find a plugin

The generated [plugin catalog](../doc/reference/plugin-catalog-en.md) lists every distribution, driver ID, registered model, WaveBench compatibility range, and capability declared by the production descriptor. It is generated from package metadata, so this page does not maintain a second status table.

Each package README provides the next level of detail:

- applicable models and connection routes;
- minimum configuration and a read-only starting example;
- model-specific safety boundaries and restrictions;
- links to current Reference, historical acceptance evidence, and vendor material.

## Package contract

Each maintained package includes:

- its own `pyproject.toml`, metadata version, and `wavebench.instruments` entry point;
- a canonical driver ID and explicit WaveBench compatibility range;
- a production descriptor and offline tests that do not access real instruments;
- Chinese and English user entry pages;
- a package-local MIT license file and SPDX package metadata;
- public content without real device resources, credentials, raw waveforms, or private experiment records.

One distribution may declare multiple driver entry points with distinct purposes. A README, milestone, or acceptance record must not present a capability as current before it enters the production descriptor.

## Add a plugin

Read the WaveBench Core [plugin development guide](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/plugin-development.md) and [instrument driver guide](https://github.com/Scaxlibur/wavebench/blob/master/docs/development/instrument-drivers.md) before adding a package. The [development environment guide](../doc/DEVELOPMENT_EN.md) covers editable installation, checks, and tests for this repository.
