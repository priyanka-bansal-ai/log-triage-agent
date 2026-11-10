# Validation Failure Triage Report

Generated: 2026-10-29T10:23:43  
Logs: `data/logs`  
Analysis mode: **heuristic**

## Summary

| Total runs | Failed runs | Pass rate | Failure clusters | New (not in known issues) |
|---|---|---|---|---|
| 200 | 66 | 67.0% | 12 | 7 |

## Prioritised failures

| # | Priority | Severity | Category | Title | Runs | Known issue | Owner |
|---|---|---|---|---|---|---|---|
| 1 | 63.7 | 🔴 critical | Memory | Memory: MRC fatal error code 0x946f, halting boot at POST code 0x43 | 8 | **NEW** | BIOS / Memory |
| 2 | 45.4 | 🔴 critical | Firmware | Firmware: Embedded controller firmware assert at 0x6f1ff892 (ec_power_seq.c:599) | 3 | **NEW** | EC Firmware |
| 3 | 30.1 | 🔴 critical | Machine Check | Machine Check: mce: [Hardware Error]: CPU 4: Machine Check Exception: 5 Bank 7: b2000 | 1 | **NEW** | CPU / RAS |
| 4 | 27.3 | 🟠 high | Power Management | Power Management: Hibernation image restore failed: checksum mismatch at block 287 | 3 | **NEW** | Kernel / Power Management |
| 5 | 26.5 | 🟠 high | Memory | Memory: Correctable ECC error rate 18/min on Channel 1 DIMM 0 exceeds threshol | 9 | KI-1004 | Memory Validation |
| 6 | 23.4 | 🟠 high | Kernel/OS | Kernel/OS: watchdog: BUG: soft lockup - CPU#4 stuck for 47s! [stressapptest:8525] | 2 | **NEW** | Kernel |
| 7 | 21.8 | 🟠 high | PCIe | PCIe: Root Port 4 BDF 0000:03:00.1: link width mismatch, expected x16 negoti | 5 | KI-1001 | BIOS / PCIe |
| 8 | 21.8 | 🟠 high | Power Management | Power Management: S3 resume timeout after 6539 ms: device XHCI0 did not respond to D0 tr | 5 | KI-1005 | Power Management |
| 9 | 17.4 | 🟡 medium | Thermal | Thermal: PROCHOT# asserted, CPU9 throttled for 1168 ms, frequency capped at 120 | 6 | **NEW** | Thermal |
| 10 | 13.6 | 🟡 medium | PCIe | PCIe: AER: 0000:3b:00.1 PCIe Bus Error: severity=Corrected, type=Physical La | 3 | **NEW** | PCIe |
| 11 | 13.2 | 🟡 medium | USB | USB: usb 3-2: device descriptor read/64, error -71 | 9 | KI-1002 | USB |
| 12 | 1.4 | ⚪ low | Test Infrastructure | Test Infrastructure: SSH connection to PLAT-A0-03 lost during iteration 35 | 12 | KI-1003 | Lab Infrastructure |

## 1. [C04] Memory: MRC fatal error code 0x946f, halting boot at POST code 0x43

- **Severity:** critical  |  **Category:** Memory  |  **Owner:** BIOS / Memory
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 8 runs, 16 error lines, units PLAT-A0-01, PLAT-A0-02, PLAT-A0-03, PLAT-A0-04, PLAT-A0-06
- **Platforms / BIOS / kernel:** PLAT-A0 / A0.1.18 / 6.8.12, 6.9.3
- **Suites:** boot_stress, memory_stress
- **First / last seen:** 2026-03-02 21:01:07.848 / 2026-03-09 07:09:04.773

**Likely root cause**

Memory reference code failed DDR training, which blocks boot.

**Evidence**

- 8 of 200 runs affected (16 error lines)
- 100% of affected runs have bios=A0.1.18 (only 24% of all runs); failure rate with bios=A0.1.18 is 17%
- 100% of affected runs have platform=PLAT-A0 (only 52% of all runs); failure rate with platform=PLAT-A0 is 8%

**Next steps**

1. Compare training margins between BIOS versions
2. Swap DIMMs between channels to see if the failure follows the DIMM
3. Collect full MRC debug log

**Example log lines**

```
[RUN-0016] 2026-03-02 21:01:07.364 | WARN | MRC | Channel 1 DIMM 0: RxDqs margin 9 ticks close to minimum
[RUN-0016] 2026-03-02 21:01:07.848 | ERROR | MRC | Memory training failed: Channel 1 DIMM 0 Rank 0 step=RxDqsDelay margin=9 ticks below minimum 12
[RUN-0016] 2026-03-02 21:01:07.945 | FATAL | BIOS | MRC fatal error code 0x946f, halting boot at POST code 0x43
```

Affected runs: RUN-0016, RUN-0022, RUN-0063, RUN-0121, RUN-0128, RUN-0169, RUN-0177, RUN-0196

## 2. [C08] Firmware: Embedded controller firmware assert at 0x6f1ff892 (ec_power_seq.c:599)

- **Severity:** critical  |  **Category:** Firmware  |  **Owner:** EC Firmware
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 3 runs, 6 error lines, units PLAT-A0-04, PLAT-A0-05, PLAT-B1-03
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, A0.1.18, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** boot_stress, s4_hibernate_cycle
- **First / last seen:** 2026-03-03 00:18:04.649 / 2026-03-08 07:22:31.868

**Likely root cause**

Embedded controller firmware asserted and was reset by its watchdog.

**Evidence**

- 3 of 200 runs affected (6 error lines)

**Next steps**

1. Get the EC crash log and map the address to the firmware build
2. Check if it happens during power transitions only

**Example log lines**

```
[RUN-0021] 2026-03-03 00:18:04.649 | FATAL | EC | Embedded controller firmware assert at 0x6f1ff892 (ec_power_seq.c:599)
[RUN-0021] 2026-03-03 00:18:04.923 | ERROR | EC | EC watchdog reset, reset_reason=0xa703
```

Affected runs: RUN-0021, RUN-0085, RUN-0167

## 3. [C12] Machine Check: mce: [Hardware Error]: CPU 4: Machine Check Exception: 5 Bank 7: b2000

- **Severity:** critical  |  **Category:** Machine Check  |  **Owner:** CPU / RAS
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 1 runs, 2 error lines, units PLAT-A0-04
- **Platforms / BIOS / kernel:** PLAT-A0 / A0.1.17 / 6.8.12
- **Suites:** boot_stress
- **First / last seen:** 2026-03-05 16:54:42.717 / 2026-03-05 16:54:43.113

**Likely root cause**

Uncorrected machine check caused a kernel panic.

**Evidence**

- 1 of 200 runs affected (2 error lines)

**Next steps**

1. Decode the MCA bank status with the platform RAS tool
2. Check if the same CPU or bank repeats
3. Collect a crash dump on reproduction

**Example log lines**

```
[RUN-0093] 2026-03-05 16:54:42.717 | FATAL | KERNEL | mce: [Hardware Error]: CPU 4: Machine Check Exception: 5 Bank 7: b20000000005d8a
[RUN-0093] 2026-03-05 16:54:43.113 | FATAL | KERNEL | Kernel panic - not syncing: Fatal machine check
```

Affected runs: RUN-0093

## 4. [C10] Power Management: Hibernation image restore failed: checksum mismatch at block 287

- **Severity:** high  |  **Category:** Power Management  |  **Owner:** Kernel / Power Management
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 3 runs, 6 error lines, units PLAT-A0-06, PLAT-B1-04, PLAT-B1-05
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, B1.0.41, B1.0.42 / 6.9.3
- **Suites:** s4_hibernate_cycle
- **First / last seen:** 2026-03-06 12:55:25.107 / 2026-03-09 07:22:29.719

**Likely root cause**

Hibernation image restore fails with checksum mismatch.

**Evidence**

- 3 of 200 runs affected (6 error lines)
- 100% of affected runs have kernel=6.9.3 (only 52% of all runs); failure rate with kernel=6.9.3 is 3%
- 100% of affected runs have suite=s4_hibernate_cycle (only 14% of all runs); failure rate with suite=s4_hibernate_cycle is 10%

**Next steps**

1. Check if failures follow a kernel version
2. Bisect the kernel change between versions

**Example log lines**

```
[RUN-0115] 2026-03-06 12:55:25.107 | ERROR | PM | Hibernation image restore failed: checksum mismatch at block 287
[RUN-0115] 2026-03-06 12:55:25.595 | ERROR | PM | PM: Image restore failed, falling back to cold boot
```

Affected runs: RUN-0115, RUN-0149, RUN-0197

## 5. [C02] Memory: Correctable ECC error rate 18/min on Channel 1 DIMM 0 exceeds threshol

- **Severity:** high  |  **Category:** Memory  |  **Owner:** Memory Validation
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** KI-1004 High correctable ECC rate on unit PLAT-A0-05
- **Affected:** 9 runs, 9 error lines, units PLAT-A0-05
- **Platforms / BIOS / kernel:** PLAT-A0 / A0.1.17, A0.1.18 / 6.8.12, 6.9.3
- **Suites:** memory_stress, thermal_soak
- **First / last seen:** 2026-03-02 16:51:29.766 / 2026-03-08 01:35:31.214

**Likely root cause**

Correctable ECC errors above threshold suggest a marginal DIMM or memory channel. Only unit PLAT-A0-05 is affected, so a unit-specific hardware issue is likely.

**Evidence**

- 9 of 200 runs affected (9 error lines)
- 100% of affected runs have platform=PLAT-A0 (only 52% of all runs); failure rate with platform=PLAT-A0 is 9%
- 100% of affected runs have unit=PLAT-A0-05 (only 13% of all runs); failure rate with unit=PLAT-A0-05 is 35%
- Only unit PLAT-A0-05 is affected

**Next steps**

1. Swap the DIMM and re-run memory_stress
2. Check if errors stay on the same channel and DIMM

**Example log lines**

```
[RUN-0012] 2026-03-02 16:51:29.274 | WARN | MEM | EDAC MC0: 255 CE memory read error on Chan#1_DIMM#0 (page:0xadae9114 offset:0x0 grain:32)
[RUN-0012] 2026-03-02 16:51:29.766 | ERROR | MEM | Correctable ECC error rate 18/min on Channel 1 DIMM 0 exceeds threshold 10/min
```

Affected runs: RUN-0012, RUN-0019, RUN-0050, RUN-0053, RUN-0065, RUN-0079, RUN-0113, RUN-0150, RUN-0161

## 6. [C11] Kernel/OS: watchdog: BUG: soft lockup - CPU#4 stuck for 47s! [stressapptest:8525]

- **Severity:** high  |  **Category:** Kernel/OS  |  **Owner:** Kernel
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 2 runs, 4 error lines, units PLAT-A0-06, PLAT-B1-02
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.18, B1.0.41 / 6.8.12, 6.9.3
- **Suites:** boot_stress, s3_resume_cycle
- **First / last seen:** 2026-03-03 08:05:27.148 / 2026-03-04 12:32:45.202

**Likely root cause**

Kernel soft lockup or hung task during the test.

**Evidence**

- 2 of 200 runs affected (4 error lines)

**Next steps**

1. Collect sysrq task dump on reproduction
2. Check if a specific driver thread is involved

**Example log lines**

```
[RUN-0028] 2026-03-03 08:05:26.888 | WARN | KERNEL | rcu: INFO: rcu_preempt detected stalls on CPUs/tasks
[RUN-0028] 2026-03-03 08:05:27.148 | ERROR | KERNEL | watchdog: BUG: soft lockup - CPU#4 stuck for 47s! [stressapptest:8525]
[RUN-0028] 2026-03-03 08:05:27.222 | ERROR | KERNEL | INFO: task stressapptest:8525 blocked for more than 120 seconds.
```

Affected runs: RUN-0028, RUN-0061

## 7. [C06] PCIe: Root Port 4 BDF 0000:03:00.1: link width mismatch, expected x16 negoti

- **Severity:** high  |  **Category:** PCIe  |  **Owner:** BIOS / PCIe
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** KI-1001 PCIe Gen5 x16 slot downtrains to x8 on PLAT-B1 with BIOS B1.0.42
- **Affected:** 5 runs, 10 error lines, units PLAT-B1-01, PLAT-B1-03, PLAT-B1-05, PLAT-B1-06
- **Platforms / BIOS / kernel:** PLAT-B1 / B1.0.42 / 6.8.12, 6.9.3
- **Suites:** boot_stress, pcie_link_training
- **First / last seen:** 2026-03-03 12:37:57.933 / 2026-03-08 13:42:08.456

**Likely root cause**

PCIe link does not train to full width or speed.

**Evidence**

- 5 of 200 runs affected (10 error lines)
- 100% of affected runs have bios=B1.0.42 (only 23% of all runs); failure rate with bios=B1.0.42 is 11%
- 100% of affected runs have platform=PLAT-B1 (only 48% of all runs); failure rate with platform=PLAT-B1 is 5%
- Matches known issue KI-1001: PCIe Gen5 x16 slot downtrains to x8 on PLAT-B1 with BIOS B1.0.42

**Next steps**

1. Compare PCIe equalization settings between BIOS versions
2. Re-seat the add-in card and re-run
3. Capture LTSSM trace on the failing port

**Example log lines**

```
[RUN-0033] 2026-03-03 12:37:57.816 | WARN | PCIE | Root Port 4 BDF 0000:03:00.1: link training retry 32/3
[RUN-0033] 2026-03-03 12:37:57.933 | ERROR | PCIE | Root Port 4 BDF 0000:03:00.1: link width mismatch, expected x16 negotiated x4
[RUN-0033] 2026-03-03 12:37:58.472 | ERROR | PCIE | Root Port 4 BDF 0000:03:00.1: link speed downgraded from Gen5 to Gen4
```

Affected runs: RUN-0033, RUN-0037, RUN-0105, RUN-0124, RUN-0175

## 8. [C07] Power Management: S3 resume timeout after 6539 ms: device XHCI0 did not respond to D0 tr

- **Severity:** high  |  **Category:** Power Management  |  **Owner:** Power Management
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** KI-1005 S3 resume timeout, device does not respond to D0 transition
- **Affected:** 5 runs, 10 error lines, units PLAT-A0-04, PLAT-A0-05, PLAT-B1-01, PLAT-B1-02
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, A0.1.18, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** s3_resume_cycle
- **First / last seen:** 2026-03-04 19:37:58.420 / 2026-03-08 07:52:31.622

**Likely root cause**

A device does not return to D0 on S3 resume, so resume times out.

**Evidence**

- 5 of 200 runs affected (10 error lines)
- 80% of affected runs have kernel=6.8.12 (only 48% of all runs); failure rate with kernel=6.8.12 is 4%
- 100% of affected runs have suite=s3_resume_cycle (only 15% of all runs); failure rate with suite=s3_resume_cycle is 17%
- Matches known issue KI-1005: S3 resume timeout, device does not respond to D0 transition

**Next steps**

1. Identify the device from the logs and check its firmware version
2. Enable PM debug tracing and reproduce

**Example log lines**

```
[RUN-0070] 2026-03-04 19:37:58.301 | WARN | PM | Device XHCI0 slow to resume (6539 ms)
[RUN-0110] 2026-03-06 08:54:41.959 | WARN | PM | Device WLAN0 slow to resume (10112 ms)
[RUN-0070] 2026-03-04 19:37:58.420 | ERROR | PM | S3 resume timeout after 6539 ms: device XHCI0 did not respond to D0 transition
[RUN-0070] 2026-03-04 19:37:59.009 | ERROR | PMC | Wake event not acknowledged, PM1_STS=0xa34e PMC_FW_STATUS=0xa34e
[RUN-0110] 2026-03-06 08:54:42.363 | ERROR | PM | S3 resume timeout after 10112 ms: device WLAN0 did not respond to D0 transition
[RUN-0120] 2026-03-06 16:24:39.621 | ERROR | PM | S3 resume timeout after 10057 ms: device GFX0 did not respond to D0 transition
```

Affected runs: RUN-0070, RUN-0110, RUN-0120, RUN-0143, RUN-0168

## 9. [C05] Thermal: PROCHOT# asserted, CPU9 throttled for 1168 ms, frequency capped at 120

- **Severity:** medium  |  **Category:** Thermal  |  **Owner:** Thermal
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 6 runs, 6 error lines, units PLAT-A0-01, PLAT-A0-04, PLAT-A0-05, PLAT-B1-02, PLAT-B1-03, PLAT-B1-05
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, A0.1.18, B1.0.41, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** memory_stress, thermal_soak
- **First / last seen:** 2026-03-02 14:11:46.237 / 2026-03-09 07:49:01.586

**Likely root cause**

CPU throttling under load due to high package temperature.

**Evidence**

- 6 of 200 runs affected (6 error lines)
- 83% of affected runs have suite=thermal_soak (only 18% of all runs); failure rate with suite=thermal_soak is 14%

**Next steps**

1. Check thermal solution and paste on affected units
2. Compare lab ambient temperature at failure time

**Example log lines**

```
[RUN-0009] 2026-03-02 14:11:45.639 | WARN | THERMAL | Package temperature 93C above warning threshold 90C
[RUN-0080] 2026-03-05 04:19:54.366 | WARN | BIOS | Setup variable cache rebuilt
[RUN-0009] 2026-03-02 14:11:46.237 | ERROR | THERMAL | PROCHOT# asserted, CPU9 throttled for 1168 ms, frequency capped at 1200 MHz
```

Affected runs: RUN-0009, RUN-0080, RUN-0084, RUN-0098, RUN-0141, RUN-0198

## 10. [C09] PCIe: AER: 0000:3b:00.1 PCIe Bus Error: severity=Corrected, type=Physical La

- **Severity:** medium  |  **Category:** PCIe  |  **Owner:** PCIe
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** none, this is a NEW failure
- **Affected:** 3 runs, 6 error lines, units PLAT-A0-01, PLAT-B1-06
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, B1.0.41, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** memory_stress, pcie_link_training
- **First / last seen:** 2026-03-05 06:12:25.428 / 2026-03-08 13:02:24.549

**Likely root cause**

Burst of corrected PCIe physical layer errors, often signal integrity.

**Evidence**

- 3 of 200 runs affected (6 error lines)

**Next steps**

1. Check the slot and riser
2. Run a PCIe margining test on the port

**Example log lines**

```
[RUN-0083] 2026-03-05 06:12:25.074 | WARN | PCIE | AER: Corrected error received: 0000:3b:00.1
[RUN-0083] 2026-03-05 06:12:25.428 | ERROR | PCIE | AER: 0000:3b:00.1 PCIe Bus Error: severity=Corrected, type=Physical Layer, (Receiver ID) status=0x43d9ae8e
[RUN-0083] 2026-03-05 06:12:25.902 | ERROR | PCIE | AER: corrected error count 290 on 0000:3b:00.1 exceeds threshold 100 within 60s
```

Affected runs: RUN-0083, RUN-0156, RUN-0174

## 11. [C03] USB: usb 3-2: device descriptor read/64, error -71

- **Severity:** medium  |  **Category:** USB  |  **Owner:** USB
- **Product bug:** yes  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** KI-1002 USB device descriptor read error -71 on external test hub
- **Affected:** 9 runs, 18 error lines, units PLAT-A0-04, PLAT-B1-01, PLAT-B1-04, PLAT-B1-06
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, B1.0.41, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** s3_resume_cycle, usb_enumeration
- **First / last seen:** 2026-03-03 23:12:30.677 / 2026-03-09 09:00:29.572

**Likely root cause**

USB device fails to enumerate (protocol error -71).

**Evidence**

- 9 of 200 runs affected (18 error lines)
- 89% of affected runs have platform=PLAT-B1 (only 48% of all runs); failure rate with platform=PLAT-B1 is 8%
- Matches known issue KI-1002: USB device descriptor read error -71 on external test hub

**Next steps**

1. Re-run on a direct port without the shared hub
2. Try a different cable and device

**Example log lines**

```
[RUN-0044] 2026-03-03 23:12:30.105 | WARN | BIOS | Setup variable cache rebuilt
[RUN-0044] 2026-03-03 23:12:30.441 | WARN | USB | usb 3-2: new high-speed USB device number 74 using xhci_hcd
[RUN-0044] 2026-03-03 23:12:30.677 | ERROR | USB | usb 3-2: device descriptor read/64, error -71
[RUN-0044] 2026-03-03 23:12:30.845 | ERROR | USB | usb 3-2: unable to enumerate USB device
```

Affected runs: RUN-0044, RUN-0062, RUN-0103, RUN-0126, RUN-0135, RUN-0144, RUN-0181, RUN-0183, RUN-0199

## 12. [C01] Test Infrastructure: SSH connection to PLAT-A0-03 lost during iteration 35

- **Severity:** low  |  **Category:** Test Infrastructure  |  **Owner:** Lab Infrastructure
- **Product bug:** no (test infrastructure)  |  **Confidence:** 50%  |  **Analysis:** heuristic
- **Known issue:** KI-1003 Lab harness loses SSH to unit during long runs
- **Affected:** 12 runs, 24 error lines, units PLAT-A0-01, PLAT-A0-03, PLAT-A0-04, PLAT-A0-05, PLAT-B1-03, PLAT-B1-04, PLAT-B1-06
- **Platforms / BIOS / kernel:** PLAT-A0, PLAT-B1 / A0.1.17, A0.1.18, B1.0.41, B1.0.42 / 6.8.12, 6.9.3
- **Suites:** boot_stress, memory_stress, s3_resume_cycle, s4_hibernate_cycle, thermal_soak, usb_enumeration
- **First / last seen:** 2026-03-02 09:58:41.501 / 2026-03-08 00:41:33.886

**Likely root cause**

Test harness lost connection to the unit. This points to the lab network or host, not the product.

**Evidence**

- 12 of 200 runs affected (24 error lines)
- Matches known issue KI-1003: Lab harness loses SSH to unit during long runs

**Next steps**

1. Re-run the affected tests
2. Check lab switch and host network logs for the failure time

**Example log lines**

```
[RUN-0004] 2026-03-02 09:58:41.115 | WARN | HARNESS | SSH keepalive to PLAT-A0-03 missed (3/3)
[RUN-0004] 2026-03-02 09:58:41.501 | ERROR | HARNESS | SSH connection to PLAT-A0-03 lost during iteration 35
[RUN-0004] 2026-03-02 09:58:41.834 | ERROR | HARNESS | Test aborted: host PLAT-A0-03 unreachable after 3 retries
```

Affected runs: RUN-0004, RUN-0024, RUN-0026, RUN-0043, RUN-0047, RUN-0052, RUN-0077, RUN-0091, RUN-0112, RUN-0129, RUN-0155, RUN-0159
