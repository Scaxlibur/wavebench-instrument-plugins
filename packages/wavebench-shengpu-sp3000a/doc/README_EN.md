# SP3000A Development Documentation

[中文](README.md)

This directory contains project-authored, publishable development documentation for the SP3000A plugin. After the manual arrives, the first pass will extract:

1. model, firmware, interface, and impedance capability matrices;
2. communication parameters for LAN, USB Device, RS-232, and optional GPIB;
3. identity, error-queue, sweep-configuration, and read-only status commands;
4. magnitude, phase, and trace-data response formats;
5. staged acceptance plans for through calibration, DUT measurements, and cross-checks.

Every document must identify its source and verification state. Manual claims must not be presented as hardware-verified behavior. Keep the complete local manual under [`vendor-local/`](vendor-local/README.md); Git will not track it.
