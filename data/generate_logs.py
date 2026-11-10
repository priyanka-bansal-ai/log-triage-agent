"""
Synthetic platform validation log generator.

Creates realistic test run logs for a fictional hardware platform validation lab:
two platforms (PLAT-A0, PLAT-B1), several units each, seven test suites, BIOS and
kernel versions, background noise, warning precursors and injected failure modes.

Every run log has a header and footer, and a ground truth CSV records which failure
mode (if any) was injected, so the triage agent can be evaluated.

All names, devices and values are made up. No real company data is used.

Usage:
    python data/generate_logs.py --runs 150 --seed 7
"""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent

PLATFORMS = {
    "PLAT-A0": {"units": 6, "bios": ["A0.1.17", "A0.1.18"]},
    "PLAT-B1": {"units": 6, "bios": ["B1.0.41", "B1.0.42"]},
}
KERNELS = ["6.8.12", "6.9.3"]
SUITES = [
    "boot_stress",
    "s3_resume_cycle",
    "s4_hibernate_cycle",
    "pcie_link_training",
    "memory_stress",
    "thermal_soak",
    "usb_enumeration",
]
ITERATIONS = {
    "boot_stress": 40,
    "s3_resume_cycle": 50,
    "s4_hibernate_cycle": 25,
    "pcie_link_training": 30,
    "memory_stress": 20,
    "thermal_soak": 15,
    "usb_enumeration": 35,
}

# ---------------------------------------------------------------------------
# Failure catalog. Each failure mode has: category, suites where it can appear,
# optional condition on platform/bios/unit (to create real correlations),
# warning precursors and the error lines themselves.
# ---------------------------------------------------------------------------

def _hex(n=8):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def _bdf():
    return f"0000:{random.choice(['01', '02', '03', '3b', '5e'])}:00.{random.randint(0, 3)}"


FAILURES = {
    "PCIE_LINK_DOWNTRAIN": {
        "category": "PCIe",
        "suites": ["pcie_link_training", "boot_stress"],
        "condition": lambda r: r["platform"] == "PLAT-B1" and r["bios"] == "B1.0.42",
        "weight": 0.55,
        "precursor": [("WARN", "PCIE", "Root Port {port} BDF {bdf}: link training retry {n}/3")],
        "lines": [
            ("ERROR", "PCIE", "Root Port {port} BDF {bdf}: link width mismatch, expected x{exp} negotiated x{neg}"),
            ("ERROR", "PCIE", "Root Port {port} BDF {bdf}: link speed downgraded from Gen{g1} to Gen{g2}"),
        ],
    },
    "PCIE_AER_FLOOD": {
        "category": "PCIe",
        "suites": ["pcie_link_training", "memory_stress"],
        "condition": None,
        "weight": 0.05,
        "precursor": [("WARN", "PCIE", "AER: Corrected error received: {bdf}")],
        "lines": [
            ("ERROR", "PCIE", "AER: {bdf} PCIe Bus Error: severity=Corrected, type=Physical Layer, (Receiver ID) status=0x{h}"),
            ("ERROR", "PCIE", "AER: corrected error count {n} on {bdf} exceeds threshold 100 within 60s"),
        ],
    },
    "MEM_TRAINING_FAIL": {
        "category": "Memory",
        "suites": ["boot_stress", "memory_stress"],
        "condition": lambda r: r["platform"] == "PLAT-A0" and r["bios"] == "A0.1.18",
        "weight": 0.25,
        "precursor": [("WARN", "MRC", "Channel {ch} DIMM {d}: RxDqs margin {m} ticks close to minimum")],
        "lines": [
            ("ERROR", "MRC", "Memory training failed: Channel {ch} DIMM {d} Rank {r} step=RxDqsDelay margin={m} ticks below minimum 12"),
            ("FATAL", "BIOS", "MRC fatal error code 0x{h4}, halting boot at POST code 0x{p}"),
        ],
    },
    "MEM_ECC_CE": {
        "category": "Memory",
        "suites": ["memory_stress", "thermal_soak"],
        "condition": lambda r: r["unit"] == "PLAT-A0-05",
        "weight": 0.9,
        "precursor": [("WARN", "MEM", "EDAC MC0: {n} CE memory read error on Chan#{ch}_DIMM#{d} (page:0x{h} offset:0x0 grain:32)")],
        "lines": [
            ("ERROR", "MEM", "Correctable ECC error rate {rate}/min on Channel {ch} DIMM {d} exceeds threshold 10/min"),
        ],
    },
    "MCE_UNCORRECTED": {
        "category": "Machine Check",
        "suites": ["memory_stress", "thermal_soak", "boot_stress"],
        "condition": None,
        "weight": 0.02,
        "precursor": [],
        "lines": [
            ("FATAL", "KERNEL", "mce: [Hardware Error]: CPU {cpu}: Machine Check Exception: 5 Bank {bank}: b2000000000{h4}"),
            ("FATAL", "KERNEL", "Kernel panic - not syncing: Fatal machine check"),
        ],
    },
    "S3_RESUME_TIMEOUT": {
        "category": "Power Management",
        "suites": ["s3_resume_cycle"],
        "condition": None,
        "weight": 0.22,
        "precursor": [("WARN", "PM", "Device {dev} slow to resume ({t} ms)")],
        "lines": [
            ("ERROR", "PM", "S3 resume timeout after {t} ms: device {dev} did not respond to D0 transition"),
            ("ERROR", "PMC", "Wake event not acknowledged, PM1_STS=0x{h4} PMC_FW_STATUS=0x{h4}"),
        ],
    },
    "S4_IMAGE_RESTORE": {
        "category": "Power Management",
        "suites": ["s4_hibernate_cycle"],
        "condition": lambda r: r["kernel"] == "6.9.3",
        "weight": 0.3,
        "precursor": [],
        "lines": [
            ("ERROR", "PM", "Hibernation image restore failed: checksum mismatch at block {n}"),
            ("ERROR", "PM", "PM: Image restore failed, falling back to cold boot"),
        ],
    },
    "THERMAL_THROTTLE": {
        "category": "Thermal",
        "suites": ["thermal_soak", "memory_stress"],
        "condition": None,
        "weight": 0.12,
        "precursor": [("WARN", "THERMAL", "Package temperature {temp}C above warning threshold 90C")],
        "lines": [
            ("ERROR", "THERMAL", "PROCHOT# asserted, CPU{cpu} throttled for {ms} ms, frequency capped at {f} MHz"),
        ],
    },
    "THERMAL_CRITICAL": {
        "category": "Thermal",
        "suites": ["thermal_soak"],
        "condition": lambda r: r["platform"] == "PLAT-B1",
        "weight": 0.12,
        "precursor": [("WARN", "THERMAL", "Package temperature {temp}C above warning threshold 90C")],
        "lines": [
            ("FATAL", "THERMAL", "Critical temperature {ctemp}C reached on package 0, initiating emergency shutdown"),
            ("ERROR", "EC", "Fan {fan} tachometer reads 0 RPM while PWM duty {duty}%"),
        ],
    },
    "USB_ENUM_FAIL": {
        "category": "USB",
        "suites": ["usb_enumeration", "s3_resume_cycle"],
        "condition": None,
        "weight": 0.15,
        "precursor": [("WARN", "USB", "usb {bus}-{uport}: new high-speed USB device number {n} using xhci_hcd")],
        "lines": [
            ("ERROR", "USB", "usb {bus}-{uport}: device descriptor read/64, error -71"),
            ("ERROR", "USB", "usb {bus}-{uport}: unable to enumerate USB device"),
        ],
    },
    "EC_FW_ASSERT": {
        "category": "Firmware",
        "suites": ["s3_resume_cycle", "s4_hibernate_cycle", "boot_stress"],
        "condition": None,
        "weight": 0.03,
        "precursor": [],
        "lines": [
            ("FATAL", "EC", "Embedded controller firmware assert at 0x{h} (ec_power_seq.c:{line})"),
            ("ERROR", "EC", "EC watchdog reset, reset_reason=0x{h4}"),
        ],
    },
    "KERNEL_SOFT_LOCKUP": {
        "category": "Kernel/OS",
        "suites": ["memory_stress", "boot_stress", "s3_resume_cycle"],
        "condition": None,
        "weight": 0.03,
        "precursor": [("WARN", "KERNEL", "rcu: INFO: rcu_preempt detected stalls on CPUs/tasks")],
        "lines": [
            ("ERROR", "KERNEL", "watchdog: BUG: soft lockup - CPU#{cpu} stuck for {s}s! [{proc}:{pid}]"),
            ("ERROR", "KERNEL", "INFO: task {proc}:{pid} blocked for more than 120 seconds."),
        ],
    },
    "HARNESS_SSH_LOST": {
        "category": "Test Infrastructure",
        "suites": SUITES,
        "condition": None,
        "weight": 0.05,
        "precursor": [("WARN", "HARNESS", "SSH keepalive to {unit} missed ({n}/3)")],
        "lines": [
            ("ERROR", "HARNESS", "SSH connection to {unit} lost during iteration {iter}"),
            ("ERROR", "HARNESS", "Test aborted: host {unit} unreachable after 3 retries"),
        ],
    },
}

INFO_MESSAGES = {
    "boot_stress": [
        ("BIOS", "POST complete in {ms} ms"),
        ("BIOS", "Boot device selected: NVMe0"),
        ("KERNEL", "Linux version {kernel} booted, cmdline OK"),
        ("HARNESS", "Iteration {iter} boot check passed"),
    ],
    "s3_resume_cycle": [
        ("PM", "Entering S3 (suspend to RAM)"),
        ("PM", "Resumed from S3 in {ms} ms"),
        ("HARNESS", "Iteration {iter} resume check passed"),
    ],
    "s4_hibernate_cycle": [
        ("PM", "Writing hibernation image ({mb} MB)"),
        ("PM", "Image restored, resume took {ms} ms"),
        ("HARNESS", "Iteration {iter} hibernate check passed"),
    ],
    "pcie_link_training": [
        ("PCIE", "Root Port {port}: link up x{exp} Gen{g1}"),
        ("PCIE", "Endpoint {bdf} enumerated, vendor=0x{h4} device=0x{h4}"),
        ("HARNESS", "Iteration {iter} link check passed"),
    ],
    "memory_stress": [
        ("MEM", "Stress pattern {pattern} pass {n} completed, 0 errors"),
        ("MEM", "Bandwidth {bw} GB/s on all channels"),
        ("HARNESS", "Iteration {iter} memory check passed"),
    ],
    "thermal_soak": [
        ("THERMAL", "Package temperature {ok_temp}C, fan {fan} at {rpm} RPM"),
        ("THERMAL", "Load level 100%, power {w} W"),
        ("HARNESS", "Iteration {iter} thermal check passed"),
    ],
    "usb_enumeration": [
        ("USB", "usb {bus}-{uport}: new SuperSpeed USB device number {n} using xhci_hcd"),
        ("USB", "usb {bus}-{uport}: Product: Test Storage Device"),
        ("HARNESS", "Iteration {iter} enumeration check passed"),
    ],
}

# Benign warnings that a naive tool would flag. The agent should ignore them.
BENIGN_WARNINGS = [
    ("KERNEL", "ACPI: _OSC evaluation for CPUs failed, trying _PDC"),
    ("BIOS", "Setup variable cache rebuilt"),
    ("THERMAL", "Fan {fan} speed adjusted to {rpm} RPM"),
    ("HARNESS", "Log rotation triggered, size {mb} MB"),
]


def _values(run, iteration):
    """Random values used to fill the message templates."""
    return {
        "port": random.randint(1, 4),
        "bdf": _bdf(),
        "n": random.randint(2, 400),
        "exp": 16,
        "neg": random.choice([4, 8]),
        "g1": 5,
        "g2": random.choice([3, 4]),
        "h": _hex(8),
        "h4": _hex(4),
        "p": _hex(2),
        "ch": random.randint(0, 3),
        "d": random.randint(0, 1),
        "r": random.randint(0, 1),
        "m": random.randint(6, 11),
        "rate": random.randint(14, 90),
        "cpu": random.randint(0, 15),
        "bank": random.randint(0, 9),
        "dev": random.choice(["NVMe0", "WLAN0", "XHCI0", "GFX0"]),
        "t": random.randint(5000, 15000),
        "temp": random.randint(91, 99),
        "ctemp": random.randint(105, 110),
        "ok_temp": random.randint(55, 82),
        "ms": random.randint(120, 2400),
        "f": random.choice([800, 1200, 1600]),
        "fan": random.randint(0, 1),
        "duty": random.randint(60, 100),
        "rpm": random.randint(1800, 4200),
        "bus": random.randint(1, 3),
        "uport": random.randint(1, 4),
        "line": random.randint(100, 900),
        "s": random.randint(22, 60),
        "proc": random.choice(["kworker/3:1", "stressapptest", "systemd-udevd"]),
        "pid": random.randint(200, 9000),
        "mb": random.randint(300, 2000),
        "bw": round(random.uniform(38, 52), 1),
        "pattern": random.choice(["walking_ones", "random", "march_c"]),
        "w": random.randint(90, 150),
        "kernel": run["kernel"],
        "unit": run["unit"],
        "iter": iteration,
    }


def _line(ts, level, comp, run, iteration, msg):
    return (
        f"{ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | {level:<5} | {comp:<7} | "
        f"{run['unit']} | {run['suite']} | iter={iteration:04d} | {msg}"
    )


def pick_failure(run):
    """Choose a failure mode for this run, or None for a passing run."""
    candidates = []
    for fid, f in FAILURES.items():
        if run["suite"] not in f["suites"]:
            continue
        if f["condition"] is not None and not f["condition"](run):
            continue
        candidates.append((fid, f["weight"]))
    random.shuffle(candidates)
    for fid, w in candidates:
        if random.random() < w:
            return fid
    return None


def make_run(run_idx, start_time):
    platform = random.choice(list(PLATFORMS))
    unit = f"{platform}-{random.randint(1, PLATFORMS[platform]['units']):02d}"
    run = {
        "run_id": f"RUN-{run_idx:04d}",
        "platform": platform,
        "unit": unit,
        "suite": random.choice(SUITES),
        "bios": random.choice(PLATFORMS[platform]["bios"]),
        "kernel": random.choice(KERNELS),
    }
    failure_id = pick_failure(run)
    total_iters = ITERATIONS[run["suite"]]
    fail_iter = random.randint(3, total_iters) if failure_id else None

    lines = [
        f"=== RUN START run_id={run['run_id']} platform={platform} unit={unit} "
        f"suite={run['suite']} bios={run['bios']} kernel={run['kernel']} "
        f"os=Ubuntu-24.04 start={start_time.isoformat(timespec='seconds')} ==="
    ]
    ts = start_time
    last_iter = total_iters
    for it in range(1, total_iters + 1):
        vals = _values(run, it)
        for comp, msg in INFO_MESSAGES[run["suite"]]:
            ts += timedelta(milliseconds=random.randint(200, 4000))
            lines.append(_line(ts, "INFO", comp, run, it, msg.format(**vals)))
        if random.random() < 0.06:
            comp, msg = random.choice(BENIGN_WARNINGS)
            ts += timedelta(milliseconds=random.randint(50, 500))
            lines.append(_line(ts, "WARN", comp, run, it, msg.format(**vals)))
        if failure_id and it == fail_iter:
            f = FAILURES[failure_id]
            for level, comp, msg in f["precursor"]:
                ts += timedelta(milliseconds=random.randint(100, 900))
                lines.append(_line(ts, level, comp, run, it, msg.format(**vals)))
            for level, comp, msg in f["lines"]:
                ts += timedelta(milliseconds=random.randint(20, 600))
                lines.append(_line(ts, level, comp, run, it, msg.format(**vals)))
            last_iter = it
            break

    result = "FAIL" if failure_id else "PASS"
    duration = int((ts - start_time).total_seconds())
    lines.append(f"=== RUN END run_id={run['run_id']} result={result} iterations={last_iter}/{total_iters} duration_s={duration} ===")
    run.update(
        result=result,
        failure_id=failure_id or "",
        category=FAILURES[failure_id]["category"] if failure_id else "",
    )
    return run, lines, ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=HERE / "logs")
    args = ap.parse_args()

    random.seed(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.log"):
        old.unlink()

    t = datetime(2026, 3, 2, 8, 0, 0)
    rows = []
    for i in range(1, args.runs + 1):
        run, lines, t_end = make_run(i, t)
        fname = f"{run['run_id']}_{run['unit']}_{run['suite']}.log"
        (args.out / fname).write_text("\n".join(lines) + "\n")
        run["file"] = fname
        rows.append(run)
        t = t_end + timedelta(minutes=random.randint(5, 90))

    fields = ["run_id", "file", "platform", "unit", "suite", "bios", "kernel", "result", "failure_id", "category"]
    with open(HERE / "ground_truth.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    fails = [r for r in rows if r["result"] == "FAIL"]
    by_mode = {}
    for r in fails:
        by_mode[r["failure_id"]] = by_mode.get(r["failure_id"], 0) + 1
    print(f"Wrote {len(rows)} runs to {args.out} ({len(fails)} failed)")
    print(json.dumps(dict(sorted(by_mode.items(), key=lambda x: -x[1])), indent=2))


if __name__ == "__main__":
    main()
