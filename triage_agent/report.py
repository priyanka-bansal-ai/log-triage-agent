"""Write the triage report as Markdown and JSON."""

import json
from pathlib import Path

from .schemas import TriageReport

SEV_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}


def to_markdown(r: TriageReport) -> str:
    out = [
        "# Validation Failure Triage Report",
        "",
        f"Generated: {r.generated_at}  ",
        f"Logs: `{r.log_dir}`  ",
        f"Analysis mode: **{r.mode}**" + (f" ({r.model})" if r.model else ""),
        "",
        "## Summary",
        "",
        f"| Total runs | Failed runs | Pass rate | Failure clusters | New (not in known issues) |",
        f"|---|---|---|---|---|",
        f"| {r.total_runs} | {r.failed_runs} | {r.pass_rate:.1%} | {len(r.items)} | "
        f"{sum(1 for i in r.items if not i.cluster.known_issue_id)} |",
        "",
        "## Prioritised failures",
        "",
        "| # | Priority | Severity | Category | Title | Runs | Known issue | Owner |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, it in enumerate(r.items, 1):
        a, c = it.analysis, it.cluster
        out.append(
            f"| {n} | {it.priority_score} | {SEV_ICON[a.severity]} {a.severity} | {a.category} | "
            f"{a.title} | {len(c.runs)} | {c.known_issue_id or '**NEW**'} | {a.owner_team} |"
        )
    out.append("")

    for n, it in enumerate(r.items, 1):
        a, c = it.analysis, it.cluster
        out += [
            f"## {n}. [{c.cluster_id}] {a.title}",
            "",
            f"- **Severity:** {a.severity}  |  **Category:** {a.category}  |  **Owner:** {a.owner_team}",
            f"- **Product bug:** {'yes' if a.is_product_bug else 'no (test infrastructure)'}  |  "
            f"**Confidence:** {a.confidence:.0%}  |  **Analysis:** {it.analysis_source}",
            f"- **Known issue:** {c.known_issue_id + ' ' + c.known_issue_title if c.known_issue_id else 'none, this is a NEW failure'}",
            f"- **Affected:** {len(c.runs)} runs, {c.occurrences} error lines, units {', '.join(c.units)}",
            f"- **Platforms / BIOS / kernel:** {', '.join(c.platforms)} / {', '.join(c.bios_versions)} / {', '.join(c.kernels)}",
            f"- **Suites:** {', '.join(c.suites)}",
            f"- **First / last seen:** {c.first_seen} / {c.last_seen}",
            "",
            "**Likely root cause**",
            "",
            a.likely_root_cause,
            "",
            "**Evidence**",
            "",
            *[f"- {e}" for e in a.evidence],
            "",
            "**Next steps**",
            "",
            *[f"{i}. {s}" for i, s in enumerate(a.next_steps, 1)],
            "",
            "**Example log lines**",
            "",
            "```",
            *c.context_lines[:2],
            *c.sample_lines[:4],
            "```",
            "",
            f"Affected runs: {', '.join(c.runs)}",
            "",
        ]
    if r.unexplained_failed_runs:
        out += ["## Failed runs with no error lines", "", ", ".join(r.unexplained_failed_runs), ""]
    return "\n".join(out)


def save_report(r: TriageReport, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "triage_report.md"
    js = out_dir / "triage_report.json"
    md.write_text(to_markdown(r), encoding="utf-8")
    js.write_text(json.dumps(r.model_dump(), indent=2), encoding="utf-8")
    return {"markdown": md, "json": js}
