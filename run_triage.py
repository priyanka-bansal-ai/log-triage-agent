"""
Command line entry point.

    python run_triage.py --logs data/logs --out reports
    python run_triage.py --logs data/logs --offline      # no LLM, rule based analysis
"""

import argparse
import time

from dotenv import load_dotenv

from triage_agent.graph import run_triage
from triage_agent.report import save_report


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Triage validation test logs")
    ap.add_argument("--logs", default="data/logs", help="Folder with .log files")
    ap.add_argument("--known-issues", default="data/known_issues.json")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--model", default=None, help="Groq model name (default from GROQ_MODEL or llama-3.3-70b-versatile)")
    ap.add_argument("--offline", action="store_true", help="Skip the LLM and use rule based analysis")
    args = ap.parse_args()

    t0 = time.time()
    state = run_triage(args.logs, args.known_issues, use_llm=not args.offline, model=args.model)
    report = state["report"]
    paths = save_report(report, args.out)

    for w in state.get("warnings", []):
        print(f"[warn] {w}")
    print(
        f"\nRuns: {report.total_runs} | Failed: {report.failed_runs} | "
        f"Pass rate: {report.pass_rate:.1%} | Clusters: {len(report.items)} | Mode: {report.mode}"
    )
    print(f"\n{'#':<3}{'Prio':>6}  {'Severity':<9}{'Category':<20}{'Runs':>5}  {'Known':<8} Title")
    for n, it in enumerate(report.items, 1):
        a, c = it.analysis, it.cluster
        print(
            f"{n:<3}{it.priority_score:>6}  {a.severity:<9}{a.category:<20}{len(c.runs):>5}  "
            f"{(c.known_issue_id or 'NEW'):<8} {a.title[:60]}"
        )
    print(f"\nReport: {paths['markdown']}  |  JSON: {paths['json']}  |  {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
