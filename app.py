"""Streamlit UI for AI Architecture Review Assistant."""

from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.agents.architecture_review_agent import ArchitectureReviewAgent
from src.agents.repo_analysis_agent import RepositoryAnalysisAgent
from src.agents.report_writer_agent import ReportWriterAgent
from src.memory.memory_store import MemoryStore
from src.services.github_service import GitHubService, GitHubServiceError
from src.services.llm_service import LLMService
from src.services.report_service import ReviewPipeline
from src.utils.helpers import parse_github_input


def render_bullets(title: str, items: list, empty_text: str = "No data available.") -> None:
    st.markdown(f"**{title}**")
    if not items:
        st.caption(empty_text)
        return
    for item in items:
        st.markdown(f"- {item}")


def to_yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def compute_confidence(analysis: dict, report: dict) -> int:
    evidence = analysis.get("evidence", {})
    react_summary = analysis.get("react_summary", {})
    sampled_files = len(evidence.get("sampled_files", []))
    dependencies = analysis.get("dependencies", [])
    dependency_count = sum(len(dep.get("dependencies", [])) for dep in dependencies)
    warnings = evidence.get("analysis_warnings", [])

    score = 88
    if react_summary.get("fallback_used"):
        score -= 25
    if sampled_files < 20:
        score -= 10
    if dependency_count == 0:
        score -= 5
    score -= min(15, len(warnings) * 5)
    if len(report.get("architecture_observations", [])) < 3:
        score -= 5
    return max(0, min(99, score))


st.set_page_config(page_title="AI Architecture Review Assistant", layout="wide")
st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(135deg, #fdf2f8 0%, #eef2ff 45%, #ecfeff 100%);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f472b6 0%, #8b5cf6 55%, #3b82f6 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.25);
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 0.5rem;
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: #ffffff !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="input"] {
            background-color: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="input"] input {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            caret-color: #0f172a !important;
            background-color: transparent !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="input"] input::placeholder {
            color: #64748b !important;
            -webkit-text-fill-color: #64748b !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="input"] button {
            background: #e2e8f0 !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #334155 !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="input"] button svg {
            fill: #334155 !important;
            color: #334155 !important;
            stroke: #334155 !important;
            opacity: 1 !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background-color: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] span,
        section[data-testid="stSidebar"] div[data-baseweb="select"] div[role="combobox"] {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }

        .block-container {
            padding-top: 1.3rem;
            padding-bottom: 2.5rem;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 0.6rem 0.8rem;
            box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
        }

        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 0.08rem;
            border-bottom: 1px solid #cbd5e1;
            padding-left: 0.1rem;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            margin-right: 0.02rem;
            padding: 0.4rem 0.75rem;
            min-height: 2.1rem;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: #ffffff;
            border-color: #94a3b8;
            color: #1e3a8a;
            font-weight: 600;
            position: relative;
            top: 1px;
        }

        div.stButton > button {
            background: linear-gradient(90deg, #2563eb 0%, #7c3aed 100%);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }
        div.stButton > button:hover {
            filter: brightness(1.05);
        }

        div[data-testid="stStatusWidget"] {
            border: 1px solid #c7d2fe;
            border-radius: 12px;
            background: #eef2ff;
        }

        .stAlert {
            border-radius: 10px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("AI Architecture Review Assistant")
st.caption("Agentic repository architecture analysis with memory, tool-calling, and report export.")

load_dotenv()
memory_store = MemoryStore()

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

with st.sidebar:
    st.subheader("Inputs")
    repo_input = st.text_input("GitHub repo URL or owner/repo", value="langchain-ai/langchain")
    github_token = st.text_input("GitHub token (optional)", type="password")
    focus = st.selectbox("Report focus", options=["general", "security", "scalability", "maintainability"])
    report_depth = "deep"
    analyze_clicked = st.button("Analyze repository", type="primary")

if analyze_clicked:
    stage_names = ["Fetching repo", "Sampling files", "Agent 1", "Agent 2", "Report generation"]
    stage_state = {name: "pending" for name in stage_names}
    progress = st.progress(0.0, text="Starting analysis pipeline...")
    status_box = st.status("Running architecture review pipeline...", expanded=True)

    def on_progress(stage: str, state: str, details: str) -> None:
        if stage in stage_state:
            stage_state[stage] = state
        completed = len([s for s in stage_state.values() if s == "completed"])
        progress.progress(completed / len(stage_names), text=f"{completed}/{len(stage_names)} stages completed")
        icon = "✅" if state == "completed" else "🔄" if state == "in_progress" else "ℹ️"
        status_box.write(f"{icon} **{stage}** ({state}) - {details}")

    try:
        owner, repo = parse_github_input(repo_input)
        token = github_token or os.getenv("GITHUB_TOKEN")
        llm = LLMService().create_chat_model()
        pipeline = ReviewPipeline(
            repo_agent=RepositoryAnalysisAgent(github_service=GitHubService(token=token), llm=llm),
            review_agent=ArchitectureReviewAgent(llm=llm),
            writer_agent=ReportWriterAgent(llm=llm),
            memory_store=memory_store,
        )
        with st.spinner("Analyzing repository..."):
            result = pipeline.run(
                owner=owner,
                repo=repo,
                focus=focus,
                report_depth=report_depth,
                progress_callback=on_progress,
            )
        st.session_state["last_result"] = result
        progress.progress(1.0, text="All stages completed")
        status_box.update(label="Architecture review completed", state="complete", expanded=False)
    except (ValueError, GitHubServiceError, Exception) as exc:
        st.error(f"Analysis failed: {exc}")
        status_box.update(label="Architecture review failed", state="error", expanded=True)
        err_text = str(exc).lower()
        if "unauthorized" in err_text or "private repos" in err_text or "not found" in err_text:
            st.info("Tip: verify owner/repo is correct and provide a GitHub token for private repositories.")
        if "rate" in err_text and "limit" in err_text:
            st.info("Tip: GitHub API rate limit may be hit. Add a GitHub token and try again.")

result = st.session_state.get("last_result")
if result:
    report = result["report"]
    analysis = result["analysis"]
    comparison = result["comparison"]
    history = result.get("history", [])

    st.success(f"Analysis complete for `{report['repo_full_name']}`")
    st.markdown(f"**Saved report:** `{report.get('report_path')}`")

    tabs = st.tabs(
        [
            "Summary",
            "Repo Structure",
            "Findings",
            "Recommendations",
            "Action Plan",
            "Raw Evidence",
            "Reasoning Trace",
            "Architecture Drift",
            "Reports",
        ]
    )
    with tabs[0]:
        st.subheader("Project Overview")
        st.write(report["summary"])
        sampled_files = len(analysis.get("evidence", {}).get("sampled_files", []))
        dependency_count = sum(len(dep.get("dependencies", [])) for dep in analysis.get("dependencies", []))
        confidence = compute_confidence(analysis, report)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Files scanned", sampled_files)
        c2.metric("Dependencies found", dependency_count)
        c3.metric("Risks flagged", len(report.get("risks_and_antipatterns", [])))
        c4.metric("Confidence", f"{confidence}%")
        render_bullets("Detected Stack", report.get("detected_stack", []), "No clear stack markers found.")
    with tabs[1]:
        st.subheader("Structure")
        structure = analysis.get("structure", {})
        render_bullets("Modules", report.get("module_breakdown", []), "No module boundaries inferred.")
        render_bullets("Entry Points", structure.get("entry_points", []), "No entry points detected.")
        render_bullets("Configuration Files", structure.get("config_files", []), "No config files identified.")
    with tabs[2]:
        st.subheader("Architecture Observations")
        observations = report.get("architecture_observations", [])
        render_bullets("Observations", observations, "No architecture observations were generated.")
        st.subheader("Risks / Anti-patterns")
        risks = report.get("risks_and_antipatterns", [])
        render_bullets("Risk Findings", risks, "No significant risks detected.")

        evidence_snippets = analysis.get("evidence", {}).get("evidence_snippets", [])
        if observations or risks:
            st.markdown("**Per-finding supporting evidence**")
            findings_for_evidence = (observations + risks)[:8]
            for finding in findings_for_evidence:
                with st.expander(finding):
                    if evidence_snippets:
                        for item in evidence_snippets[:4]:
                            st.markdown(f"- `{item.get('path', 'unknown')}`")
                            st.code(item.get("snippet", "No snippet available."))
                    else:
                        st.caption("No evidence snippets available for this run.")
    with tabs[3]:
        st.subheader("Recommendations")
        render_bullets("Recommended Actions", report.get("recommendations", []), "No recommendations available.")
        st.subheader("Suggested Next Steps")
        render_bullets("Execution Plan", report.get("next_steps", []), "No next steps available.")
    with tabs[4]:
        st.subheader("Prioritized Action Plan")
        action_plan = report.get("action_plan", [])
        if action_plan:
            st.dataframe(action_plan, width="stretch")
        else:
            st.caption("No action plan generated for this run.")

    with tabs[5]:
        st.subheader("Raw Evidence")
        evidence = report.get("raw_evidence", {})
        warnings = analysis.get("evidence", {}).get("analysis_warnings", [])
        sampled = evidence.get("sampled_files", [])
        read_files = evidence.get("read_files", [])
        st.markdown(
            f"- Sampled files: **{len(sampled)}**\n"
            f"- Files read in detail: **{len(read_files)}**\n"
            f"- Metadata captured: **{to_yes_no(bool(evidence.get('metadata')))}**"
        )
        render_bullets("Analysis Warnings", warnings, "No warnings reported.")
        with st.expander("Show raw evidence payload (JSON)"):
            st.json(evidence)
    with tabs[6]:
        st.subheader("Reasoning Trace (ReAct)")
        react_summary = analysis.get("react_summary", {})
        st.markdown(
            f"**Stop condition:** `{react_summary.get('stop_condition', 'n/a')}` | "
            f"**Iterations:** `{react_summary.get('iterations_used', 0)}/"
            f"{react_summary.get('max_iterations', 0)}` | "
            f"**Fallback used:** `{react_summary.get('fallback_used', False)}`"
        )
        trace_rows = analysis.get("reasoning_trace", [])
        if trace_rows:
            for step in trace_rows:
                st.markdown(
                    f"**Step {step.get('step_index')}** - {step.get('status', 'unknown').upper()}  \n"
                    f"- Thought: {step.get('thought', 'n/a')}  \n"
                    f"- Action: `{step.get('action', 'n/a')}`  \n"
                    f"- Observation: {step.get('observation', 'n/a')}"
                )
        else:
            st.info("No reasoning trace captured.")
    with tabs[7]:
        st.subheader("Architecture Drift Detection")
        file_changes = comparison.get(
            "file_changes",
            {"added_count": 0, "removed_count": 0, "added_samples": [], "removed_samples": []},
        )
        architecture_changes = comparison.get(
            "architecture_changes",
            {
                "added_config_files": [],
                "removed_config_files": [],
                "added_entry_points": [],
                "removed_entry_points": [],
                "added_key_directories": [],
                "removed_key_directories": [],
            },
        )
        architecture_change_count = (
            len(architecture_changes.get("added_config_files", []))
            + len(architecture_changes.get("removed_config_files", []))
            + len(architecture_changes.get("added_entry_points", []))
            + len(architecture_changes.get("removed_entry_points", []))
            + len(architecture_changes.get("added_key_directories", []))
            + len(architecture_changes.get("removed_key_directories", []))
        )
        st.markdown(
            f"**Current drift assessment:** `{comparison.get('drift_status', 'n/a')}` "
            f"with score `{comparison.get('improvement_score', 'n/a')}/100`."
        )

        summary_rows = [
            {
                "Previous Run": comparison.get("previous_analyzed_at", "n/a"),
                "Drift Status": comparison.get("drift_status", "n/a"),
                "Improvement Score": comparison.get("improvement_score", "n/a"),
                "Focus Changed": to_yes_no(comparison.get("focus_changed", False)),
                "Stack Changed": to_yes_no(comparison.get("stack_changed", False)),
                "Files Added": file_changes.get("added_count", 0),
                "Files Removed": file_changes.get("removed_count", 0),
                "Architecture Changes": architecture_change_count,
                "Module Delta": comparison.get("module_delta", 0),
                "Dependency Delta": comparison.get("dependency_delta", 0),
            }
        ]
        st.markdown("**Drift Summary**")
        st.dataframe(summary_rows, width="stretch")

        st.markdown("**Drift Timeline (Run History)**")
        if history and len(history) > 1:
            timeline_df = pd.DataFrame(history)
            timeline_df = timeline_df.sort_values("analyzed_at")
            timeline_chart = timeline_df.set_index("analyzed_at")[["risk_count", "module_count", "dependency_count"]]
            st.line_chart(timeline_chart, height=220)
            st.caption("Trend across recent runs for this repository.")
        elif history:
            st.caption("Only one run available so far. Re-run analysis to view timeline trends.")
        else:
            st.caption("No run history available for timeline.")

        st.markdown("**Architecture-Level Changes**")
        architecture_rows = []
        for item in architecture_changes.get("added_config_files", []):
            architecture_rows.append({"Change Type": "Added Config File", "Path": item})
        for item in architecture_changes.get("removed_config_files", []):
            architecture_rows.append({"Change Type": "Removed Config File", "Path": item})
        for item in architecture_changes.get("added_entry_points", []):
            architecture_rows.append({"Change Type": "Added Entry Point", "Path": item})
        for item in architecture_changes.get("removed_entry_points", []):
            architecture_rows.append({"Change Type": "Removed Entry Point", "Path": item})
        for item in architecture_changes.get("added_key_directories", []):
            architecture_rows.append({"Change Type": "Added Key Directory", "Path": item})
        for item in architecture_changes.get("removed_key_directories", []):
            architecture_rows.append({"Change Type": "Removed Key Directory", "Path": item})
        if architecture_rows:
            st.dataframe(architecture_rows, width="stretch")
        else:
            st.caption("No architecture-level structural changes between runs.")

        st.markdown("**Sampled File Changes**")
        file_rows = []
        for item in file_changes.get("added_samples", []):
            file_rows.append({"Change Type": "Added File", "Path": item})
        for item in file_changes.get("removed_samples", []):
            file_rows.append({"Change Type": "Removed File", "Path": item})
        if file_rows:
            st.dataframe(file_rows, width="stretch")
        else:
            st.caption("No sampled file changes available between runs.")

        with st.expander("Risk-level and pattern deltas (secondary context)"):
            risk_rows = []
            for item in comparison.get("new_risks", []):
                risk_rows.append({"Change Type": "New Risk", "Description": item})
            for item in comparison.get("resolved_risks", []):
                risk_rows.append({"Change Type": "Resolved Risk", "Description": item})
            if risk_rows:
                st.dataframe(risk_rows, width="stretch")
            else:
                st.caption("No risk-level changes between runs.")

            pattern_changes = comparison.get("pattern_changes", {"added": [], "removed": []})
            pattern_rows = []
            for item in pattern_changes.get("added", []):
                pattern_rows.append({"Change Type": "Added Pattern", "Pattern": item})
            for item in pattern_changes.get("removed", []):
                pattern_rows.append({"Change Type": "Removed Pattern", "Pattern": item})
            if pattern_rows:
                st.dataframe(pattern_rows, width="stretch")
            else:
                st.caption("No pattern changes between runs.")
    with tabs[8]:
        st.subheader("Reports")
        st.markdown(f"**Saved report path:** `{report.get('report_path')}`")
        st.download_button(
            label="Download markdown report",
            data=report["markdown_report"],
            file_name=f"{report['repo_full_name'].replace('/', '_')}_architecture_report.md",
            mime="text/markdown",
        )
        st.download_button(
            label="Export analysis JSON",
            data=json.dumps(result, indent=2),
            file_name=f"{report['repo_full_name'].replace('/', '_')}_analysis_result.json",
            mime="application/json",
        )

        with st.expander("Preview full markdown report"):
            st.markdown(report["markdown_report"])

        st.markdown("**Run history (from memory store)**")
        current_repo_key = report.get("repo_full_name")
        repo_history = memory_store.get_run_history(limit=10, repo_key=current_repo_key)
        all_history = memory_store.get_run_history(limit=20)

        st.markdown("Current repository history")
        if repo_history:
            st.dataframe(repo_history, width="stretch")
        else:
            st.caption("No previous runs found for this repository.")

        with st.expander("Recent runs across repositories"):
            if all_history:
                st.dataframe(all_history, width="stretch")
            else:
                st.caption("No run history available yet.")
else:
    st.info("Enter a repository and click Analyze repository to generate a report.")
