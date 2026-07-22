# WaveBench SP3000A Plugin (Incubating)

[中文](README.md)

A documentation-first incubation directory for an external WaveBench plugin targeting the SP3000A sweep-analyzer family. SP30120A is the provisional first model.

## Current status

This directory currently establishes only the documentation and source-material boundaries. It does not yet contain an installable distribution, entry point, or instrument driver. The manual protocol audit is complete; instrument identity and transport details still require staged verification:

- Planned distribution: `wavebench-shengpu-sp3000a`
- Provisional canonical driver ID: `shengpu.sp30120a`
- Planned instrument kind: `sweep_analyzer`

`frequency_response` is a generic capability and data domain, not a second instrument kind. Public sweep-plan and frequency-response models must first be reviewed in the core repository. This plugin will not duplicate core safety policy, state restoration, reporting, or artifact handling. See the [remote protocol and capability audit](doc/PROTOCOL_AUDIT_EN.md).

## Manual drop location

Copy the local Markdown manual to:

```text
doc/vendor-local/SP3000A_manual.md
```

Git ignores all content under `doc/vendor-local/` except its explanatory README. Project-authored capability matrices, communication notes, SCPI summaries, trace-format documentation, and acceptance plans will live under `doc/` and will distinguish manual claims from hardware-verified behavior.

## License

Project-authored code and documentation in this directory are licensed under the [MIT License](LICENSE). Locally retained vendor manuals and transcriptions do not thereby become MIT-licensed and are not part of the public distribution.
