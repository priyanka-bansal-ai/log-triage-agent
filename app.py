"""
Streamlit dashboard for the validation log triage agent.

    streamlit run app.py
"""

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from triage_agent.graph import run_triage
from triage_agent.report import to_markdown

load_dotenv()
st.set_page_config(page_title="Validation Log Triage Agent", page_icon="🧪", layout="wide")

SEV_COLOR = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    source = st.radio("Logs", ["Sample dataset (200 runs)", "Upload .log files"])
    uploads = None
    if source == "Upload .log files":
        uploads = st.file_uploader("Run logs", type=["log", "txt"], accept_multiple_files=True)
    key_in_env = bool(os.getenv("GROQ_API_KEY"))
    api_key = st.text_input(
        "Groq API key", type="password",
        placeholder="set in .env" if key_in_env else "gsk_...",
        help="Leave empty to use the key from .env. Without any key the agent uses rule based analysis.",
    )
    model = st.text_input("Model", value=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    use_llm = st.toggle("Use LLM analysis", value=True)
    run_btn = st.button("Run triage", type="primary", use_container_width=True)

st.title("🧪 Validation Log Triage Agent")
st.caption(
    "Reads platform validation test logs, groups errors into failure clusters, finds correlations "
    "(BIOS, unit, kernel), matches known issues and writes prioritised bug reports with LangGraph and an LLM."
)

# ----------------------------------------------------------------------------- run
if run_btn:
    if api_key:
        os.environ["GROQ_API_KEY"] = api_key
    if uploads:
        tmp = Path(tempfile.mkdtemp())
        for f in uploads:
            name = f.name if f.name.endswith(".log") else f.name + ".log"
            (tmp / name).write_bytes(f.getvalue())
        log_dir = tmp
    elif source == "Upload .log files":
        st.warning("Upload at least one .log file.")
        st.stop()
    else:
        log_dir = Path("data/logs")
    with st.spinner("Parsing logs, clustering failures and analysing root causes..."):
        state = run_triage(str(log_dir), "data/known_issues.json", use_llm=use_llm, model=model)
    st.session_state["state"] = state

state = st.session_state.get("state")
if not state:
    st.info("Choose the logs in the sidebar and press **Run triage**.")
    st.stop()

report = state["report"]
for w in state.get("warnings", []):
    st.warning(w)

# ----------------------------------------------------------------------------- summary
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Runs", report.total_runs)
c2.metric("Failed", report.failed_runs)
c3.metric("Pass rate", f"{report.pass_rate:.1%}")
c4.metric("Failure clusters", len(report.items))
c5.metric("New issues", sum(1 for i in report.items if not i.cluster.known_issue_id))
st.caption(f"Analysis mode: **{report.mode}**" + (f" · model `{report.model}`" if report.model else ""))

if not report.items:
    st.success("No failures found.")
    st.stop()

rows = [
    {
        "Priority": it.priority_score,
        "Severity": f"{SEV_COLOR[it.analysis.severity]} {it.analysis.severity}",
        "Category": it.analysis.category,
        "Title": it.analysis.title,
        "Runs": len(it.cluster.runs),
        "Known issue": it.cluster.known_issue_id or "NEW",
        "Owner": it.analysis.owner_team,
        "Product bug": "yes" if it.analysis.is_product_bug else "no",
    }
    for it in report.items
]
df = pd.DataFrame(rows)

tab1, tab2, tab3 = st.tabs(["Prioritised failures", "Charts", "Download"])

with tab1:
    st.dataframe(df, use_container_width=True, hide_index=True)
    for n, it in enumerate(report.items, 1):
        a, c = it.analysis, it.cluster
        label = f"{n}. {SEV_COLOR[a.severity]} [{c.cluster_id}] {a.title}  ·  {len(c.runs)} runs  ·  {c.known_issue_id or 'NEW'}"
        with st.expander(label):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**Likely root cause**\n\n{a.likely_root_cause}")
                st.markdown("**Evidence**\n" + "\n".join(f"- {e}" for e in a.evidence))
                st.markdown("**Next steps**\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(a.next_steps, 1)))
            with right:
                st.markdown(
                    f"**Owner:** {a.owner_team}  \n**Confidence:** {a.confidence:.0%}  \n"
                    f"**Analysis:** {it.analysis_source}  \n"
                    f"**Known issue:** {c.known_issue_id + ' ' + c.known_issue_title if c.known_issue_id else 'none (NEW)'}  \n"
                    f"**Units:** {', '.join(c.units)}  \n**BIOS:** {', '.join(c.bios_versions)}  \n"
                    f"**Kernels:** {', '.join(c.kernels)}  \n**Suites:** {', '.join(c.suites)}"
                )
                if c.correlations:
                    st.markdown("**Correlations**\n" + "\n".join(f"- {x}" for x in c.correlations))
            st.code("\n".join(c.context_lines[:2] + c.sample_lines[:4]), language="log")
            st.caption("Affected runs: " + ", ".join(c.runs))

with tab2:
    a1, a2 = st.columns(2)
    with a1:
        st.subheader("Failed runs by category")
        cat = {}
        for it in report.items:
            cat[it.analysis.category] = cat.get(it.analysis.category, 0) + len(it.cluster.runs)
        st.bar_chart(pd.Series(cat, name="runs").sort_values(ascending=False))
    with a2:
        st.subheader("Clusters by severity")
        sev = df["Severity"].str.split(" ").str[1].value_counts()
        st.bar_chart(sev)
    st.subheader("Failed runs per unit")
    unit_counts = {}
    for it in report.items:
        for u in it.cluster.units:
            unit_counts[u] = unit_counts.get(u, 0) + 1
    st.bar_chart(pd.Series(unit_counts, name="clusters").sort_index())

with tab3:
    st.download_button("Download report (Markdown)", to_markdown(report), "triage_report.md")
    st.download_button(
        "Download report (JSON)", json.dumps(report.model_dump(), indent=2), "triage_report.json"
    )
    st.markdown(to_markdown(report))
