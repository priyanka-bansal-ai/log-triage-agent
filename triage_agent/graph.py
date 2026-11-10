"""
LangGraph workflow for log triage.

  ingest -> extract_failures --(no failures)--> build_report
                    |
                    v
                 cluster -> match_known_issues -> analyze -> prioritize -> build_report
"""

import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .analyzer import LLMAnalyzer, heuristic_analyze
from .clustering import (
    build_clusters,
    extract_failure_events,
    load_known_issues,
    match_known_issues,
)
from .parser import parse_log_file
from .schemas import FailureCluster, LogEvent, RunMeta, TriageItem, TriageReport

SEVERITY_WEIGHT = {"critical": 10.0, "high": 6.0, "medium": 3.0, "low": 1.0}


class TriageState(TypedDict, total=False):
    log_dir: str
    known_issues_path: str
    use_llm: bool
    model: Optional[str]
    runs: List[RunMeta]
    events: List[LogEvent]
    failure_events: List[LogEvent]
    clusters: List[FailureCluster]
    items: List[TriageItem]
    mode: str
    warnings: List[str]
    model_used: Optional[str]
    report: TriageReport


# ----------------------------------------------------------------------------- nodes

def ingest(state: TriageState) -> dict:
    files = sorted(Path(state["log_dir"]).glob("*.log"))
    runs, events = [], []
    for f in files:
        meta, evs = parse_log_file(f)
        runs.append(meta)
        events.extend(evs)
    return {"runs": runs, "events": events, "warnings": []}


def extract_failures(state: TriageState) -> dict:
    return {"failure_events": extract_failure_events(state["events"])}


def route_after_extract(state: TriageState) -> str:
    return "cluster" if state["failure_events"] else "build_report"


def cluster(state: TriageState) -> dict:
    clusters = build_clusters(state["failure_events"], state["events"], state["runs"])
    return {"clusters": clusters}


def match_known(state: TriageState) -> dict:
    known = load_known_issues(state.get("known_issues_path", ""))
    clusters = state["clusters"]
    match_known_issues(clusters, known)
    return {"clusters": clusters}


def analyze(state: TriageState) -> dict:
    clusters = state["clusters"]
    total = len(state["runs"])
    warnings = list(state.get("warnings", []))
    analyzer = None
    if state.get("use_llm", True) and os.getenv("GROQ_API_KEY"):
        try:
            analyzer = LLMAnalyzer(model=state.get("model"))
        except Exception as e:  # missing package or bad config
            warnings.append(f"LLM init failed, using heuristic mode: {e}")
    elif state.get("use_llm", True):
        warnings.append("GROQ_API_KEY not set, using heuristic mode")

    def run_one(c: FailureCluster):
        if analyzer is not None:
            try:
                return c, analyzer.analyze(c, total), "llm"
            except Exception as e:
                warnings.append(f"{c.cluster_id}: LLM call failed ({type(e).__name__}), used heuristic")
        return c, heuristic_analyze(c, total), "heuristic"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, clusters))

    items = [
        TriageItem(cluster=c, analysis=a, priority_score=0.0, analysis_source=src)
        for c, a, src in results
    ]
    sources = {it.analysis_source for it in items}
    mode = "llm" if sources == {"llm"} else ("mixed" if "llm" in sources else "heuristic")
    return {"items": items, "mode": mode, "warnings": warnings,
            "model_used": analyzer.model if analyzer is not None else None}


def prioritize(state: TriageState) -> dict:
    """Priority = severity x spread x novelty x product relevance."""
    total = max(len(state["runs"]), 1)
    for it in state["items"]:
        a, c = it.analysis, it.cluster
        spread = 1 + math.log2(1 + len(c.runs)) + 2 * len(c.runs) / total
        novelty = 1.5 if c.known_issue_id is None else 1.0
        product = 1.0 if a.is_product_bug else 0.3
        it.priority_score = round(SEVERITY_WEIGHT[a.severity] * spread * novelty * product, 1)
    items = sorted(state["items"], key=lambda i: -i.priority_score)
    return {"items": items}


def build_report(state: TriageState) -> dict:
    runs = state["runs"]
    failed = [r.run_id for r in runs if r.result == "FAIL"]
    items = state.get("items", [])
    run_to_clusters: Dict[str, List[str]] = {}
    for it in items:
        for r in it.cluster.runs:
            run_to_clusters.setdefault(r, []).append(it.cluster.cluster_id)
    unexplained = [r for r in failed if r not in run_to_clusters]
    report = TriageReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        log_dir=str(state["log_dir"]),
        total_runs=len(runs),
        failed_runs=len(failed),
        pass_rate=round(1 - len(failed) / max(len(runs), 1), 3),
        mode=state.get("mode", "none"),
        model=state.get("model_used"),
        items=items,
        unexplained_failed_runs=unexplained,
        run_to_clusters=run_to_clusters,
    )
    return {"report": report}


# ----------------------------------------------------------------------------- graph

def build_graph():
    g = StateGraph(TriageState)
    g.add_node("ingest", ingest)
    g.add_node("extract_failures", extract_failures)
    g.add_node("cluster", cluster)
    g.add_node("match_known_issues", match_known)
    g.add_node("analyze", analyze)
    g.add_node("prioritize", prioritize)
    g.add_node("build_report", build_report)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "extract_failures")
    g.add_conditional_edges("extract_failures", route_after_extract, ["cluster", "build_report"])
    g.add_edge("cluster", "match_known_issues")
    g.add_edge("match_known_issues", "analyze")
    g.add_edge("analyze", "prioritize")
    g.add_edge("prioritize", "build_report")
    g.add_edge("build_report", END)
    return g.compile()


def run_triage(
    log_dir: str,
    known_issues_path: str = "data/known_issues.json",
    use_llm: bool = True,
    model: Optional[str] = None,
) -> TriageState:
    graph = build_graph()
    return graph.invoke(
        {
            "log_dir": str(log_dir),
            "known_issues_path": str(known_issues_path),
            "use_llm": use_llm,
            "model": model,
        }
    )
