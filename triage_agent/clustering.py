"""
Turn raw error lines into failure clusters.

1. Normalise each error message into a signature (numbers, addresses, BDFs removed).
2. Group lines by signature.
3. Merge signatures that describe the same failure:
   a. they appear together in the same runs (run set Jaccard), or
   b. their text is almost identical (TF-IDF cosine).
4. Compute statistics and cross-run correlations for each cluster
   (for example "all affected runs used BIOS B1.0.42").
5. Match each cluster against the known issue database.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .schemas import FailureCluster, LogEvent, RunMeta

FAIL_LEVELS = {"ERROR", "FATAL", "CRITICAL"}
LEVEL_RANK = {"WARN": 1, "ERROR": 2, "FATAL": 3, "CRITICAL": 3}

_NORMALISERS = [
    (re.compile(r"\b[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]\b", re.I), "<bdf>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<hex>"),
    (re.compile(r"\b[0-9a-f]{12,}\b", re.I), "<hex>"),
    (re.compile(r"\bPLAT-[A-Z0-9]+-\d+\b"), "<unit>"),
    (re.compile(r"\busb \d+-\d+(\.\d+)*"), "usb <port>"),
    (re.compile(r"\[[\w/:.-]+:\d+\]"), "[<task>]"),
    (re.compile(r"\b[\w/.-]+:\d+\b"), "<task>"),
    (re.compile(r"\d+(\.\d+)?"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def normalise(message: str) -> str:
    sig = message
    for pattern, repl in _NORMALISERS:
        sig = pattern.sub(repl, sig)
    return sig.strip().lower()


class _UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def extract_failure_events(events: List[LogEvent]) -> List[LogEvent]:
    out = []
    for e in events:
        if e.level in FAIL_LEVELS:
            e.signature = f"[{e.component.lower()}] {normalise(e.message)}"
            out.append(e)
    return out


def _correlations(affected: List[RunMeta], all_runs: List[RunMeta]) -> List[str]:
    """Find attributes that are strongly concentrated in the affected runs."""
    notes = []
    if len(affected) < 3:
        return notes
    for attr in ["bios", "platform", "unit", "kernel", "suite"]:
        counts = Counter(getattr(r, attr) for r in affected)
        value, n = counts.most_common(1)[0]
        share = n / len(affected)
        total_with_value = sum(1 for r in all_runs if getattr(r, attr) == value)
        baseline = total_with_value / max(len(all_runs), 1)
        if share >= 0.8 and baseline <= 0.6:
            fail_rate = n / max(total_with_value, 1)
            notes.append(
                f"{share:.0%} of affected runs have {attr}={value} "
                f"(only {baseline:.0%} of all runs); failure rate with {attr}={value} is {fail_rate:.0%}"
            )
    return notes


def build_clusters(
    failure_events: List[LogEvent],
    all_events: List[LogEvent],
    runs: List[RunMeta],
    jaccard_threshold: float = 0.6,
    text_threshold: float = 0.85,
) -> List[FailureCluster]:
    if not failure_events:
        return []

    by_sig: Dict[str, List[LogEvent]] = defaultdict(list)
    for e in failure_events:
        by_sig[e.signature].append(e)
    sigs = sorted(by_sig)
    uf = _UnionFind(len(sigs))

    # a. near-identical text (same message with a different device name, port, etc.)
    if len(sigs) > 1:
        tfidf = TfidfVectorizer(token_pattern=r"[a-z<>#/_-]+").fit_transform(sigs)
        sim = cosine_similarity(tfidf)
        for i in range(len(sigs)):
            for j in range(i + 1, len(sigs)):
                if sim[i, j] >= text_threshold:
                    uf.union(i, j)

    # b. co-occurrence: groups whose lines show up in the same runs are one failure
    def _group_run_sets():
        sets: Dict[int, set] = defaultdict(set)
        for i, s in enumerate(sigs):
            sets[uf.find(i)].update(e.run_id for e in by_sig[s])
        return sets

    changed = True
    while changed:
        changed = False
        sets = _group_run_sets()
        roots = sorted(sets)
        for a_i in range(len(roots)):
            for b_i in range(a_i + 1, len(roots)):
                a, b = roots[a_i], roots[b_i]
                inter = len(sets[a] & sets[b])
                union = len(sets[a] | sets[b])
                if union and inter / union >= jaccard_threshold:
                    uf.union(a, b)
                    changed = True
                    break
            if changed:
                break

    groups: Dict[int, List[str]] = defaultdict(list)
    for i, s in enumerate(sigs):
        groups[uf.find(i)].append(s)

    run_meta = {r.run_id: r for r in runs}
    warn_by_run = defaultdict(list)
    for e in all_events:
        if e.level == "WARN":
            warn_by_run[e.run_id].append(e)

    clusters = []
    for members in groups.values():
        evs = sorted((e for s in members for e in by_sig[s]), key=lambda e: e.timestamp)
        run_ids = sorted(set(e.run_id for e in evs))
        affected = [run_meta[r] for r in run_ids if r in run_meta]
        max_level = max((e.level for e in evs), key=lambda lv: LEVEL_RANK.get(lv, 0))

        # one example line per signature
        samples, seen = [], set()
        for e in evs:
            if e.signature not in seen:
                seen.add(e.signature)
                samples.append(f"[{e.run_id}] {e.raw()}")

        # warnings logged just before the error, in the same iteration
        context, cseen = [], set()
        for e in evs:
            for w in warn_by_run.get(e.run_id, []):
                if w.iteration == e.iteration and w.timestamp <= e.timestamp:
                    key = normalise(w.message)
                    if key not in cseen:
                        cseen.add(key)
                        context.append(f"[{w.run_id}] {w.raw()}")
        clusters.append(
            FailureCluster(
                cluster_id="",
                signatures=sorted(members),
                components=sorted(set(e.component for e in evs)),
                max_level=max_level,
                occurrences=len(evs),
                runs=run_ids,
                units=sorted(set(r.unit for r in affected)),
                platforms=sorted(set(r.platform for r in affected)),
                suites=sorted(set(r.suite for r in affected)),
                bios_versions=sorted(set(r.bios for r in affected)),
                kernels=sorted(set(r.kernel for r in affected)),
                first_seen=evs[0].timestamp,
                last_seen=evs[-1].timestamp,
                sample_lines=samples[:6],
                context_lines=context[:4],
                correlations=_correlations(affected, runs),
            )
        )

    clusters.sort(key=lambda c: (-len(c.runs), -LEVEL_RANK.get(c.max_level, 0)))
    for i, c in enumerate(clusters, start=1):
        c.cluster_id = f"C{i:02d}"
    return clusters


def load_known_issues(path: Path) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def match_known_issues(clusters: List[FailureCluster], known: List[dict]) -> None:
    """Attach a known issue id when any of its patterns matches a cluster signature or sample."""
    for c in clusters:
        text = " ".join(c.signatures + c.sample_lines).lower()
        for ki in known:
            if any(re.search(p.lower(), text) for p in ki.get("patterns", [])):
                c.known_issue_id = ki["id"]
                c.known_issue_title = ki["title"]
                break
