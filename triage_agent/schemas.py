"""Pydantic data models used across the pipeline."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "PCIe",
    "Memory",
    "Machine Check",
    "Power Management",
    "Thermal",
    "USB",
    "Firmware",
    "Kernel/OS",
    "Test Infrastructure",
    "Other",
]
Severity = Literal["critical", "high", "medium", "low"]


class RunMeta(BaseModel):
    """Header and footer information of one test run log."""

    run_id: str
    file: str
    platform: str = ""
    unit: str = ""
    suite: str = ""
    bios: str = ""
    kernel: str = ""
    result: str = "UNKNOWN"
    iterations: str = ""
    duration_s: int = 0


class LogEvent(BaseModel):
    """One parsed log line."""

    run_id: str
    line_no: int
    timestamp: str
    level: str
    component: str
    unit: str
    suite: str
    iteration: int
    message: str
    signature: str = ""

    def raw(self) -> str:
        return f"{self.timestamp} | {self.level} | {self.component} | {self.message}"


class FailureCluster(BaseModel):
    """A group of error lines that represent one failure mode across runs."""

    cluster_id: str
    signatures: List[str]
    components: List[str]
    max_level: str
    occurrences: int
    runs: List[str]
    units: List[str]
    platforms: List[str]
    suites: List[str]
    bios_versions: List[str]
    kernels: List[str]
    first_seen: str
    last_seen: str
    sample_lines: List[str]
    context_lines: List[str] = Field(default_factory=list)
    correlations: List[str] = Field(default_factory=list)
    known_issue_id: Optional[str] = None
    known_issue_title: Optional[str] = None


class TriageAnalysis(BaseModel):
    """Structured triage output. The LLM must fill exactly these fields."""

    title: str = Field(description="Short bug title, under 15 words, specific to this failure")
    category: Category = Field(description="Failure category")
    severity: Severity = Field(description="critical: data loss, hang, panic or boot blocked; high: functional failure; medium: degraded behaviour; low: cosmetic or infra")
    is_product_bug: bool = Field(description="False if the failure is caused by the test lab or harness, not the product")
    likely_root_cause: str = Field(description="Most likely root cause in 1 to 3 sentences, grounded in the evidence")
    evidence: List[str] = Field(description="2 to 4 short points from the logs and correlations that support the root cause")
    next_steps: List[str] = Field(description="2 to 4 concrete debug or triage actions")
    owner_team: str = Field(description="Team that should own the bug, e.g. BIOS, PCIe, Memory, Power Management, Lab Infrastructure")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the root cause, 0 to 1")


class TriageItem(BaseModel):
    cluster: FailureCluster
    analysis: TriageAnalysis
    priority_score: float
    analysis_source: Literal["llm", "heuristic"]


class TriageReport(BaseModel):
    generated_at: str
    log_dir: str
    total_runs: int
    failed_runs: int
    pass_rate: float
    mode: str
    model: Optional[str] = None
    items: List[TriageItem]
    unexplained_failed_runs: List[str] = Field(default_factory=list)
    run_to_clusters: dict = Field(default_factory=dict)
