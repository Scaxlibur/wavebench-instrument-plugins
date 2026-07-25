# SP30120 Command Certification Matrix

[中文](COMMAND_CERTIFICATION_MATRIX.md) | [Certification rules](COMMAND_CERTIFICATION_PLAN_EN.md)

Statuses apply only to the observed non-A SP30120. `W/Q` means setter/query. Items above M3 are outside the current hardware authorization. M1 may exercise an unverified query below, but a response alone does not advertise a generic capability.

|Command family|W/Q|Stage|Current status|Boundary|
|---|---|---:|---|---|
|`*IDN`|Q|M1|`verified-read`|SP3000 family only|
|`BEEP`, `SYSTem:LOCal`|W/Q|M2|Observed query/confirmation `unsupported-firmware`|No BEEP response; no documented LOC|
|`CENS`, `STAS`, `CWFREQ`, `FREQOFFSET`, `SWET`|W/Q|M3|Q `verified-read`; W `untested`|Core frequency/timing state|
|`CENT`, `SPAN`, `STOP`|W/Q|M3|Q `verified-read`; W `untested`|Independent frequency-window views|
|`STARt`|W/Q|M3|Q `unsupported-firmware`; W `untested`|Query returns deterministic `Error`|
|`SWETAUTO`, `SWET:AVER`, `SWET:AVER:STATe`|W/Q|M3|Q `unsupported-firmware`; W `untested`|Queries return undocumented `Error`|
|`SWET:MODE`|W/Q|M3|LIN Q `verified-read`; LOG W `unsafe-quarantined`|LOG freezes remote access and panel|
|`POWEr`|W/Q|M4|Q `unsupported-firmware`; W `manual-only`|Real output stage|
|`OUTOHMSEL`|W/Q|M4|Q `verified-read`; W `manual-only`|Real impedance verification deferred|
|`INPZ`|W/Q|M3|Q `verified-read`; W `untested`|50/75/HIGHZ|
|`INPLSW`|W/Q|M3|Q `verified-read`; W `untested`|Internal-detector input range|
|External detector (`DETMODE`, `EXTDETPOL`, `EXTDETIN`, `EXTDETIN:SENS`)|W/Q|option|`option-absent`; DETMODE Q is also `unsupported-firmware`|Option not confirmed installed|
|`FMT`, `SETSCALE`, `SETREFL`|W/Q|M2|Q `verified-read`; W `untested`|Display mode, amplitude scale, and reference level|
|`SETREFPH`, `SETPHSCAL`|W/Q|M2|Q `unsupported-firmware`; W `untested`|Reference-phase query returns `Error`; phase-scale query is silent|
|`SETREFP`|W/Q|M2|`verified-control`|`4→5→4` passed 3/3 with independent readback and full fingerprint restoration|
|`MARKn`|W/Q|M2/M5|Q `verified-read`; W `untested`|Markers 1–5 read 20/40/60/80/100 MHz consistently|
|`MARD`|W/Q|M2|Q `manual-only`; W `untested`|One OFF observation, below the three-run gate|
|`CLEMn`, `DISMn`|W/Q|M2|Q `unsupported-firmware`; W `untested`|Queries for markers 1–5 return deterministic `Error`|
|`OUTPMARK`, `OUTPMARKV`|Q|M1|`manual-only`|Explicit no-active-marker response observed; active state not covered|
|`MARKVn`, `MARKDISP:MEAS`|Q|M1/M5|`untested`|Marker measurement scope was excluded from this run|
|Marker search, bandwidth, Q, reflection, VSWR, S-parameters, and limit line|W/Q|M5/option|`manual-only`|Analysis/calibration/fixture prerequisites|
|Storage (`SAVTA`, `*SAV`, `*RCL`, `CONFIGI/O`, `TRACEI/O`)|W/Q|M6|Q `untested`; W `manual-only`|Writes and recalls prohibited in this run|
|`TRIM`|W/Q|M2|`verified-control`|Silent SING/CONT writes with readback|
|`EXTT`|W/Q|M2/M3|`verified-control`|`OFF→ONSWEE→OFF` passed 3/3 with readback and full restoration|
|`CONT`, `SING`|W|M2|`doc-ambiguous`|Possible standalone aliases, no query|
|`RFSTAT`|W/Q|M4/interlock|Q `verified-read`; OFF has one-way safety evidence; ON `manual-only`|Safely forced from ON to OFF and kept OFF; not a generic reversible control|
|`SETCDATE`|W/Q|M2|Q `doc-ambiguous`; W `untested`|Current response is not a valid date; writes prohibited|
|`SETCTIME`|W/Q|M2|Q `verified-read`; W `untested`|Time is readable; device clock was not changed|
|`CLOCKSW`|W/Q|M2|`verified-control`|`ON→OFF→ON` passed 3/3 and restored|
|`LANGSEL`|W/Q|M2|`verified-control`|`CHINESE→ENGLISH→CHINESE` passed 3/3 and restored|
|`*RST`, `PRES`|W|M6|`manual-only`|Reset prohibited in this run|
|`OUTPRFORM?`|Q|M1/M3|`manual-only`|Stable 501+501 frame; mode/unit not closed|
|`OUTPRFORM:CONT`, `MODE`, `POINT`, `POINT:DATA`|W/Q|M3|`unsupported-firmware`|Queries silent; writes have no observable effect|
|`OUTSTATEC?`|Q|M1|`manual-only`|327-byte/50-token ASCII; complete schema open|
|`OUTPMEMOV n?`, `OUTPMEMOS n?`|Q|M1/M6|`untested`|Stored-data reads; slot/schema conflicts|
|`OUTPMEMOS n`|W|M6|`manual-only`|State recall prohibited in this run|
|`FUNC`|W/Q|M3|Q `unsupported-firmware`; W `untested`|Query silent|
|`AMPMEAS`, `PHAMEAS`|W/Q|M3|`unsupported-firmware`|Queries silent; writes did not change independent state|

USB Device, LAN, and optional GPIB are transport claims, not automatic consequences of the RS-232 command set, and remain uncertified. Conflicting slot ranges, spacing examples, and mnemonics stay `doc-ambiguous` or stricter; the runner does not explore a speculative alias product.
