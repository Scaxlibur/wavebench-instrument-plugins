# SP3000A Development Documentation

[中文](README.md)

This directory contains project-authored, publishable development documentation for the SP3000A plugin.
The production descriptor remains authoritative for current capabilities; audits, plans, and acceptance
records do not independently promote public capabilities.

## Current Reference

- [Command certification matrix](COMMAND_CERTIFICATION_MATRIX_EN.md): command-level implementation and evidence status.

## Audits and plans

- [Remote protocol and capability audit](PROTOCOL_AUDIT_EN.md)
- [Command certification plan](COMMAND_CERTIFICATION_PLAN_EN.md)

## Historical acceptance evidence

- [RS-232 read-only protocol acceptance](RS232_READONLY_ACCEPTANCE_EN.md)

Development material is organized around:

1. model, firmware, interface, and impedance capability matrices;
2. communication parameters for LAN, USB Device, RS-232, and optional GPIB;
3. identity, error-queue, sweep-configuration, and read-only status commands;
4. magnitude, phase, and trace-data response formats;
5. staged acceptance plans for through calibration, DUT measurements, and cross-checks.

Every document must identify its source and verification state. Manual claims must not be presented as hardware-verified behavior. Keep the complete local manual under [`vendor-local/`](vendor-local/README.md); Git will not track it.
