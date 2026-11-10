from pathlib import Path

from triage_agent.clustering import normalise
from triage_agent.graph import run_triage
from triage_agent.parser import parse_log_text

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = """=== RUN START run_id=RUN-9001 platform=PLAT-B1 unit=PLAT-B1-02 suite=pcie_link_training bios=B1.0.42 kernel=6.8.12 os=Ubuntu-24.04 start=2026-03-02T08:00:00 ===
2026-03-02 08:00:03.394 | INFO  | PCIE    | PLAT-B1-02 | pcie_link_training | iter=0001 | Root Port 2: link up x16 Gen5
2026-03-02 08:00:04.100 | WARN  | PCIE    | PLAT-B1-02 | pcie_link_training | iter=0001 | Root Port 2 BDF 0000:01:00.0: link training retry 2/3
2026-03-02 08:00:04.593 | ERROR | PCIE    | PLAT-B1-02 | pcie_link_training | iter=0001 | Root Port 2 BDF 0000:01:00.0: link width mismatch, expected x16 negotiated x8
=== RUN END run_id=RUN-9001 result=FAIL iterations=1/30 duration_s=4 ===
"""


def test_parser_reads_header_footer_and_lines():
    meta, events = parse_log_text(SAMPLE, "RUN-9001_x.log")
    assert meta.run_id == "RUN-9001"
    assert meta.bios == "B1.0.42"
    assert meta.result == "FAIL"
    assert len(events) == 3
    assert events[-1].level == "ERROR" and events[-1].component == "PCIE"


def test_normalise_removes_variable_parts():
    a = normalise("Root Port 2 BDF 0000:01:00.0: link width mismatch, expected x16 negotiated x8")
    b = normalise("Root Port 4 BDF 0000:3b:00.1: link width mismatch, expected x16 negotiated x4")
    assert a == b


def test_offline_pipeline_on_sample_dataset():
    state = run_triage(ROOT / "data/logs", ROOT / "data/known_issues.json", use_llm=False)
    report = state["report"]
    assert report.total_runs > 0
    assert report.items, "expected failure clusters"
    assert not report.unexplained_failed_runs
    # infra issues must be ranked last
    assert report.items[-1].analysis.category == "Test Infrastructure"
