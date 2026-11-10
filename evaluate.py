"""
Evaluate the triage agent against the ground truth of the synthetic dataset.

Metrics:
- Cluster purity: share of runs in each cluster that belong to the cluster's main failure mode.
- Failure mode recall: share of injected failure modes that got their own cluster.
- Category accuracy: per failed run, predicted category (from its highest priority cluster)
  vs the true category.
- Known issue precision: clusters linked to a known issue that truly are that issue.

    python evaluate.py --offline
    python evaluate.py              # uses Groq if GROQ_API_KEY is set
"""

import argparse
import csv
from collections import Counter

from dotenv import load_dotenv

from triage_agent.graph import run_triage

KNOWN_TRUTH = {
    "KI-1001": "PCIE_LINK_DOWNTRAIN",
    "KI-1002": "USB_ENUM_FAIL",
    "KI-1003": "HARNESS_SSH_LOST",
    "KI-1004": "MEM_ECC_CE",
    "KI-1005": "S3_RESUME_TIMEOUT",
}


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="data/logs")
    ap.add_argument("--truth", default="data/ground_truth.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    truth = {r["run_id"]: r for r in csv.DictReader(open(args.truth))}
    report = run_triage(args.logs, use_llm=not args.offline)["report"]
    items = report.items

    # cluster purity
    total, pure = 0, 0
    cluster_mode = {}
    print(f"{'Cluster':<8}{'Runs':>5}  {'Main true failure mode':<24}{'Purity':>7}  Predicted category")
    for it in items:
        modes = Counter(truth[r]["failure_id"] for r in it.cluster.runs if r in truth)
        mode, n = modes.most_common(1)[0]
        cluster_mode[it.cluster.cluster_id] = mode
        total += sum(modes.values())
        pure += n
        print(f"{it.cluster.cluster_id:<8}{len(it.cluster.runs):>5}  {mode:<24}{n / sum(modes.values()):>7.0%}  {it.analysis.category}")

    true_modes = {r["failure_id"] for r in truth.values() if r["failure_id"]}
    found = set(cluster_mode.values())

    # category accuracy per failed run
    by_id = {it.cluster.cluster_id: it for it in items}
    correct, failed = 0, 0
    for run_id, row in truth.items():
        if row["result"] != "FAIL":
            continue
        failed += 1
        cids = report.run_to_clusters.get(run_id, [])
        if not cids:
            continue
        best = max((by_id[c] for c in cids), key=lambda i: i.priority_score)
        correct += best.analysis.category == row["category"]

    linked = [it for it in items if it.cluster.known_issue_id]
    ki_ok = sum(1 for it in linked if KNOWN_TRUTH.get(it.cluster.known_issue_id) == cluster_mode[it.cluster.cluster_id])

    print("\n=== Evaluation ===")
    print(f"Analysis mode            : {report.mode}")
    print(f"Cluster purity           : {pure / max(total, 1):.1%}")
    print(f"Failure modes recovered  : {len(found & true_modes)}/{len(true_modes)}")
    print(f"Category accuracy (runs) : {correct}/{failed} = {correct / max(failed, 1):.1%}")
    print(f"Known issue precision    : {ki_ok}/{len(linked)}")
    print(f"New failure modes flagged: {sum(1 for it in items if not it.cluster.known_issue_id)}")


if __name__ == "__main__":
    main()
