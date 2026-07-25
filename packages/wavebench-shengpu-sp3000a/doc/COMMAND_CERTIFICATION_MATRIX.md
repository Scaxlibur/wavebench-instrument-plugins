# SP30120 命令认证矩阵

[English](COMMAND_CERTIFICATION_MATRIX_EN.md) | [认证规则](COMMAND_CERTIFICATION_PLAN.md)

状态限定到当前无 A 后缀 SP30120。`W/Q` 表示设置命令/查询；阶段高于 M3 的条目不在当前实机授权范围内。M1 会测试表内尚未认证的纯查询，但不会自动把“有响应”升级为通用 capability。

|命令族|W/Q|阶段|当前状态|说明|
|---|---|---:|---|---|
|`*IDN`|Q|M1|`verified-read`|只确认 SP3000 系列|
|`BEEP`|W/Q|M2|Q `unsupported-firmware`；W `untested`|`BEEP?` 无响应|
|`SYSTem:LOCal`|W|M2|`unsupported-firmware`|未收到手册声明的 `LOC`；不能作为自动恢复|
|`CENS`|W/Q|M3|Q `verified-read`；W `untested`|中心频率/带宽|
|`CENT` / `SPAN`|W/Q|M3|Q `verified-read`；W `untested`|同一频率窗口的独立视图|
|`STAS`|W/Q|M3|Q `verified-read`；W `untested`|起始/终止成对视图|
|`STARt`|W/Q|M3|Q `unsupported-firmware`；W `untested`|Q 返回确定性 `Error`|
|`STOP`|W/Q|M3|Q `verified-read`；W `untested`|独立终止频率视图|
|`CWFREQ`|W/Q|M3|Q `verified-read`；W `untested`|点频频率|
|`FREQOFFSET`|W/Q|M3|Q `verified-read`；W `untested`|频率偏移|
|`SWET`|W/Q|M3|Q `verified-read`；W `untested`|手动扫频时间|
|`SWETAUTO`|W/Q|M3|Q `unsupported-firmware`；W `untested`|Q 返回未文档化 `Error`|
|`SWET:MODE`|W/Q|M3|LIN Q `verified-read`；LOG W `unsafe-quarantined`|LOG 会锁死远控和前面板|
|`SWET:AVER`|W/Q|M3|Q `unsupported-firmware`；W `untested`|Q 返回 `Error`|
|`SWET:AVER:STATe`|W/Q|M3|Q `unsupported-firmware`；W `untested`|Q 返回 `Error`|
|`POWEr`|W/Q|M4|Q `unsupported-firmware`；W `manual-only`|真实 RF 输出阶段；本轮不写|
|`OUTOHMSEL`|W/Q|M4|Q `verified-read`；W `manual-only`|真实输出阻抗认证属于 M4|
|`INPZ`|W/Q|M3|Q `verified-read`；W `untested`|50/75/HIGHZ|
|`INPLSW`|W/Q|M3|Q `verified-read`；W `untested`|内检波输入量程|
|`DETMODE`|W/Q|M3/选件|Q `unsupported-firmware`；OUT W `option-absent`|Q 无响应；外检波未确认安装|
|`EXTDETPOL` / `EXTDETIN` / `EXTDETIN:SENS`|W/Q|选件|`option-absent`|外检波选件未确认安装|
|`FMT` / `SETSCALE` / `SETREFL`|W/Q|M2|Q `verified-read`；W `untested`|显示模式、幅度刻度和幅度参考值|
|`SETREFPH`|W/Q|M2|Q `unsupported-firmware`；W `untested`|Q 返回确定性 `Error`|
|`SETPHSCAL`|W/Q|M2|Q `unsupported-firmware`；W `untested`|Q 无响应，健康复核正常|
|`SETREFP`|W/Q|M2|`verified-control`|`4→5→4` 连续 3/3，独立回读与完整指纹恢复通过|
|`MARKn:RMEAS`|W/Q|M5/选件|`manual-only`|S 参数/反射测量，需夹具和校准|
|`MARKn:RVAL` / `MARKn:RTVAL?`|W/Q|M5/选件|`manual-only`|`RVAL AUTO` 会采集全反射基准|
|`MARKn`|W/Q|M2/M5|Q `verified-read`；W `untested`|1–5 号频率稳定读回 20/40/60/80/100 MHz|
|`MARD`|W/Q|M2|Q `manual-only`；W `untested`|单次读回 OFF，未达到三轮门禁|
|`CLEMn` / `DISMn`|W/Q|M2|Q `unsupported-firmware`；W `untested`|1–5 号 query 均返回确定性 `Error`|
|`OUTPMARK?` / `OUTPMARKV?`|Q|M1|`manual-only`|无活动 Marker 时返回明确文本，尚未覆盖活动状态|
|`MARKVn?`|Q|M1|`untested`|本轮不进入 M5 Marker 测量|
|`MARKDISP:N3DB` / `N20DB` / `QVALUE`|W/Q|M5|`manual-only`|仪器端带宽/Q 分析|
|`MARKDISP:PPBW` / `PP` / `DATA?`|W/Q|M5|`manual-only`|峰峰分析和结果|
|`MARKDISP:REF` / `SELMARK`|W/Q|M2|Q `unsupported-firmware`；W `untested`|Q 返回确定性 `Error`|
|`MARKDISP:AUTO` / `START` / `STOP`|W|M5|`manual-only`|会改变 Marker 或扫描窗口|
|`MARKDISP:MEAS?`|Q|M1|`untested`|活动 Marker 幅相数据|
|`MARKDISP:RCOEF` / `SWRAT`|W/Q|M5/选件|`manual-only`|反射系数/驻波比，需夹具和校准|
|`MARKMEAS` / `MARKRELn`|W/Q|M5|`manual-only`|搜索和 Δ 运算，本轮不进入|
|`MARKPOLA`|W/Q|M5|Q `unsupported-firmware`；W `manual-only`|Q 返回确定性 `Error`|
|`LIMLINE` / `LIMPP`|W/Q|M5|Q `unsupported-firmware`；W `manual-only`|Q 无响应但健康；不进入搜索|
|`LIMSER`|W|M5|`manual-only`|参考线搜索，本轮不进入|
|`SAVTA`|W/Q|M6|Q `untested`；W `manual-only`|存储总开关，本轮只可查询|
|`*SAV` / `*RCL`|W|M6|`manual-only`|工作状态保存/调用，本轮禁止|
|`CONFIGI` / `CONFIGO`|W|M6|`manual-only`|工作状态保存/调用，本轮禁止|
|`TRACEI` / `TRACEOn`|W|M6|`manual-only`|曲线保存/显示，本轮禁止|
|`TRIM`|W/Q|M2|`verified-control`|SING/CONT 静默写入及 `TRIM?` 回读已通过|
|`EXTT`|W/Q|M2/M3|`verified-control`|`OFF→ONSWEE→OFF` 连续 3/3，独立回读与完整指纹恢复通过|
|`CONT` / `SING`|W|M2|`doc-ambiguous`|可能是 `TRIM` 的独立别名，无 query|
|`RFSTAT`|W/Q|M4/互锁|Q `verified-read`；OFF W 仅有单向安全证据；ON `manual-only`|本轮从 ON 安全关闭并保持 OFF，但不作为通用可逆控制|
|`SETCDATE`|W/Q|M2|Q `doc-ambiguous`；W `untested`|当前返回异常字符序列，禁止写入|
|`SETCTIME`|W/Q|M2|Q `verified-read`；W `untested`|时间可读；未改变设备时钟|
|`CLOCKSW`|W/Q|M2|`verified-control`|`ON→OFF→ON` 连续 3/3，恢复通过|
|`LANGSEL`|W/Q|M2|`verified-control`|`CHINESE→ENGLISH→CHINESE` 连续 3/3，恢复通过|
|`*RST` / `PRES`|W|M6|`manual-only`|高副作用复位，本轮禁止|
|`OUTPRFORM?`|Q|M1/M3|`manual-only`|稳定 501+501 帧；模式/单位未关闭|
|`OUTPRFORM:CONT`|W/Q|M3|`unsupported-firmware`|Q 无响应；W 无可见效果|
|`OUTPRFORM:MODE`|W/Q|M3|`unsupported-firmware`|Q 无响应；W 无可见效果|
|`OUTPRFORM:POINT:DATA`|W/Q|M3|`unsupported-firmware`|20/200/730 均无可见效果|
|`OUTPRFORM:POINT`|W/Q|M3|`unsupported-firmware`|Q 无响应；W 无可见效果|
|`OUTSTATEC?`|Q|M1|`manual-only`|327-byte/50-token ASCII；完整 schema 未认证|
|`OUTPMEMOV n?`|Q|M1/M6|`untested`|存储曲线只读；槽范围 1–9/1–10 冲突|
|`OUTPMEMOS n?`|Q|M1/M6|`untested`|存储状态只读；C 风格 schema 未冻结|
|`OUTPMEMOS n`|W|M6|`manual-only`|会调用保存状态，本轮禁止|
|`FUNC`|W/Q|M3|Q `unsupported-firmware`；W `untested`|Q 无响应|
|`AMPMEAS` / `PHAMEAS`|W/Q|M3|`unsupported-firmware`|Q 无响应；W 未改变独立状态|

手册中的 USB Device、LAN 和可选 GPIB 是 transport 能力，不是当前 RS-232 命令认证的自动延伸；本矩阵不据此声明支持。手册在曲线槽范围、示例空格和若干助记符上存在冲突，冲突项保持 `doc-ambiguous` 或更严格状态，不尝试别名笛卡尔积。
