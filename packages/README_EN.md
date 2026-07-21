# Plugin packages

[中文](README.md)

This directory contains independently packaged WaveBench instrument plugins. It currently includes `wavebench-rigol-ds1000z` and `wavebench-rigol-dg4000`. Future migrations should add one package per instrument or closely related family without defining a second manifest, installer, or catalog protocol here.

Each maintained package should include:

- its own `pyproject.toml` and version;
- a `wavebench.instruments` entry point;
- a canonical driver ID and an explicit WaveBench compatibility range;
- unit tests that do not access real instruments;
- bilingual user-facing documentation;
- no real device resources, credentials, raw waveforms, or private experiment records.
