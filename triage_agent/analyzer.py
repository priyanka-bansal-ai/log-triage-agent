"""
Root cause analysis for one failure cluster.

LLM mode uses Groq through LangChain with Pydantic structured output.
Heuristic mode is a rule based fallback, used when no API key is set or the LLM call fails,
so the pipeline always produces a report.
"""

import json
import os
from typing import Optional

from .schemas import FailureCluster, TriageAnalysis

DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a senior platform validation engineer triaging failures from a hardware
validation lab (BIOS, PCIe, memory, power management, thermal, USB, embedded controller firmware, kernel).

You receive one failure cluster: error lines grouped across many test runs, with statistics,
warnings seen just before the errors, cross-run correlations and an optional matching known issue.

Rules:
- Base every claim on the given evidence. Do not invent register meanings or part numbers.
- Correlations (BIOS version, unit, platform, kernel) are strong evidence; use them.
- If one unit is the only one affected, suspect that unit's hardware first.
- If the failure is from the test harness or lab network, set is_product_bug=false and severity=low.
- Kernel panics, machine checks, boot blocking errors and emergency shutdowns are critical.
- Next steps must be concrete actions a validation engineer can do today."""


def build_prompt(c: FailureCluster, total_runs: int) -> str:
    payload = {
        "cluster_id": c.cluster_id,
        "highest_level": c.max_level,
        "components": c.components,
        "occurrences": c.occurrences,
        "affected_runs": len(c.runs),
        "total_runs_in_batch": total_runs,
        "platforms": c.platforms,
        "units": c.units,
        "test_suites": c.suites,
        "bios_versions": c.bios_versions,
        "kernels": c.kernels,
        "first_seen": c.first_seen,
        "last_seen": c.last_seen,
        "error_signatures": c.signatures,
        "example_error_lines": c.sample_lines,
        "warnings_before_error": c.context_lines,
        "correlations": c.correlations or ["none found"],
        "matching_known_issue": (
            {"id": c.known_issue_id, "title": c.known_issue_title} if c.known_issue_id else None
        ),
    }
    return "Triage this failure cluster:\n" + json.dumps(payload, indent=2)


class LLMAnalyzer:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        from langchain_groq import ChatGroq

        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        llm = ChatGroq(
            model=self.model,
            temperature=0,
            max_retries=3,
            api_key=api_key or os.getenv("GROQ_API_KEY"),
        )
        self.chain = llm.with_structured_output(TriageAnalysis)

    def analyze(self, c: FailureCluster, total_runs: int) -> TriageAnalysis:
        return self.chain.invoke(
            [("system", SYSTEM_PROMPT), ("human", build_prompt(c, total_runs))]
        )


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

_RULES = [
    # (keywords in signatures, category, severity, owner, root cause, next steps)
    (["ssh", "unreachable", "harness"], "Test Infrastructure", "low", "Lab Infrastructure",
     "Test harness lost connection to the unit. This points to the lab network or host, not the product.",
     ["Re-run the affected tests", "Check lab switch and host network logs for the failure time"]),
    (["machine check", "fatal machine check"], "Machine Check", "critical", "CPU / RAS",
     "Uncorrected machine check caused a kernel panic.",
     ["Decode the MCA bank status with the platform RAS tool", "Check if the same CPU or bank repeats", "Collect a crash dump on reproduction"]),
    (["mrc", "memory training"], "Memory", "critical", "BIOS / Memory",
     "Memory reference code failed DDR training, which blocks boot.",
     ["Compare training margins between BIOS versions", "Swap DIMMs between channels to see if the failure follows the DIMM", "Collect full MRC debug log"]),
    (["ecc"], "Memory", "high", "Memory Validation",
     "Correctable ECC errors above threshold suggest a marginal DIMM or memory channel.",
     ["Swap the DIMM and re-run memory_stress", "Check if errors stay on the same channel and DIMM"]),
    (["aer"], "PCIe", "medium", "PCIe",
     "Burst of corrected PCIe physical layer errors, often signal integrity.",
     ["Check the slot and riser", "Run a PCIe margining test on the port"]),
    (["link width", "link speed", "pcie"], "PCIe", "high", "BIOS / PCIe",
     "PCIe link does not train to full width or speed.",
     ["Compare PCIe equalization settings between BIOS versions", "Re-seat the add-in card and re-run", "Capture LTSSM trace on the failing port"]),
    (["resume timeout", "wake event"], "Power Management", "high", "Power Management",
     "A device does not return to D0 on S3 resume, so resume times out.",
     ["Identify the device from the logs and check its firmware version", "Enable PM debug tracing and reproduce"]),
    (["hibernation", "image restore"], "Power Management", "high", "Kernel / Power Management",
     "Hibernation image restore fails with checksum mismatch.",
     ["Check if failures follow a kernel version", "Bisect the kernel change between versions"]),
    (["critical temperature", "emergency shutdown", "rpm"], "Thermal", "critical", "Thermal / EC",
     "Package reached critical temperature, likely due to a fan failure.",
     ["Inspect fan and fan connector on affected units", "Check EC fan control logs"]),
    (["prochot", "throttl"], "Thermal", "medium", "Thermal",
     "CPU throttling under load due to high package temperature.",
     ["Check thermal solution and paste on affected units", "Compare lab ambient temperature at failure time"]),
    (["usb", "enumerate", "descriptor"], "USB", "medium", "USB",
     "USB device fails to enumerate (protocol error -71).",
     ["Re-run on a direct port without the shared hub", "Try a different cable and device"]),
    (["firmware assert", "ec watchdog", "ec_"], "Firmware", "critical", "EC Firmware",
     "Embedded controller firmware asserted and was reset by its watchdog.",
     ["Get the EC crash log and map the address to the firmware build", "Check if it happens during power transitions only"]),
    (["soft lockup", "blocked for more than"], "Kernel/OS", "high", "Kernel",
     "Kernel soft lockup or hung task during the test.",
     ["Collect sysrq task dump on reproduction", "Check if a specific driver thread is involved"]),
]


def _short_title(category: str, c: FailureCluster) -> str:
    """Use the most severe example line as the title."""
    rank = {"FATAL": 3, "CRITICAL": 3, "ERROR": 2}
    best = max(c.sample_lines, key=lambda l: rank.get(l.split(" | ")[1].strip(), 0))
    msg = best.split(" | ")[-1]
    return f"{category}: {msg[:70]}"


def heuristic_analyze(c: FailureCluster, total_runs: int) -> TriageAnalysis:
    text = " ".join(c.signatures).lower()
    rule = next((r for r in _RULES if any(k in text for k in r[0])), None)
    if rule is None:
        rule = ([], "Other", "medium", "Platform Validation",
                "Unclassified failure; needs manual review.", ["Review full logs of affected runs"])
    _, category, severity, owner, cause, steps = rule
    is_bug = category != "Test Infrastructure"
    if c.max_level == "FATAL" and severity in ("medium", "high") and is_bug:
        severity = "critical"
    evidence = [f"{len(c.runs)} of {total_runs} runs affected ({c.occurrences} error lines)"]
    evidence += c.correlations[:2]
    if len(c.units) == 1 and len(c.runs) >= 2:
        evidence.append(f"Only unit {c.units[0]} is affected")
        cause += f" Only unit {c.units[0]} is affected, so a unit-specific hardware issue is likely."
    if c.known_issue_id:
        evidence.append(f"Matches known issue {c.known_issue_id}: {c.known_issue_title}")
    return TriageAnalysis(
        title=_short_title(category, c),
        category=category,
        severity=severity,
        is_product_bug=is_bug,
        likely_root_cause=cause,
        evidence=evidence[:4],
        next_steps=steps,
        owner_team=owner,
        confidence=0.5,
    )
