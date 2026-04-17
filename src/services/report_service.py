"""Report generation and pipeline orchestration service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from src.agents.architecture_review_agent import ArchitectureReviewAgent
from src.agents.repo_analysis_agent import RepositoryAnalysisAgent
from src.agents.report_writer_agent import ReportWriterAgent
from src.memory.memory_store import MemoryStore
from src.models.schemas import ArchitectureReport, MemoryRecord, RepoAnalysisResult, ReportFocus
from src.tools.memory_tools import compare_with_previous


def build_markdown_report(
    analysis: RepoAnalysisResult,
    project_overview: str,
    observations: list[str],
    risks: list[str],
    recommendations: list[str],
    next_steps: list[str],
    action_plan: list[dict],
) -> str:
    lines = [
        f"# Architecture Review Report: {analysis.repo.full_name}",
        "",
        f"- Generated at: {datetime.utcnow().isoformat()}Z",
        f"- Focus: {analysis.focus}",
        f"- Default branch: {analysis.repo.branch}",
        "",
        "## Project Overview",
        project_overview,
        "",
        "## Detected Stack",
    ]
    lines.extend([f"- {item}" for item in analysis.tech_stack] or ["- No stack markers detected"])

    lines.append("")
    lines.append("## Module Breakdown")
    lines.extend([f"- {item}" for item in analysis.structure.modules] or ["- No modules inferred"])

    lines.append("")
    lines.append("## Architecture Observations")
    lines.extend([f"- {item}" for item in observations] or ["- No observations generated"])

    lines.append("")
    lines.append("## Risks / Anti-patterns")
    lines.extend([f"- {item}" for item in risks] or ["- No major risks detected"])

    lines.append("")
    lines.append("## Recommendations")
    lines.extend([f"- {item}" for item in recommendations] or ["- No recommendations generated"])

    lines.append("")
    lines.append("## Suggested Next Steps")
    lines.extend([f"- {item}" for item in next_steps] or ["- No next steps generated"])

    lines.append("")
    lines.append("## Prioritized Action Plan")
    if action_plan:
        for item in action_plan:
            lines.append(
                f"- [{item['priority']}] {item['action']} | owner={item['owner_role']} | "
                f"effort={item['effort']} | impact={item['impact']} | due={item['due_window']}"
            )
    else:
        lines.append("- No action plan generated")

    lines.append("")
    lines.append("## Raw Evidence")
    lines.append("- Sampled files:")
    for p in analysis.evidence.get("sampled_files", [])[:20]:
        lines.append(f"  - {p}")
    lines.append("- Key config files:")
    for p in analysis.structure.config_files[:20]:
        lines.append(f"  - {p}")

    lines.append("")
    lines.append("## Reasoning Trace (ReAct)")
    lines.append(
        f"- Stop condition: {analysis.react_summary.stop_condition} "
        f"(iterations: {analysis.react_summary.iterations_used}/{analysis.react_summary.max_iterations})"
    )
    lines.append(f"- Fallback used: {analysis.react_summary.fallback_used}")
    for step in analysis.reasoning_trace[:8]:
        lines.append(
            f"- Step {step.step_index}: thought='{step.thought}' | action={step.action} "
            f"| status={step.status} | observation={step.observation}"
        )

    return "\n".join(lines)


def _infer_owner_role(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["ci", "pipeline", "docker", "deploy", "infra", "devops"]):
        return "DevOps Engineer"
    if any(k in lower for k in ["security", "secret", "auth", "vulnerability"]):
        return "Security Engineer"
    if any(k in lower for k in ["test", "quality", "lint"]):
        return "QA Engineer"
    if any(k in lower for k in ["architecture", "module", "design", "boundary"]):
        return "Tech Lead"
    return "Backend Developer"


def _build_action_plan(recommendations: list[str], risks: list[str]) -> list[dict]:
    actions = recommendations if recommendations else risks
    plan: list[dict] = []
    for idx, action in enumerate(actions[:6]):
        if idx < 2:
            priority = "P0"
            due = "1 week"
            effort = "M"
            impact = "High"
        elif idx < 4:
            priority = "P1"
            due = "2-3 weeks"
            effort = "M"
            impact = "Medium"
        else:
            priority = "P2"
            due = "1 month"
            effort = "S"
            impact = "Medium"
        plan.append(
            {
                "priority": priority,
                "action": action,
                "owner_role": _infer_owner_role(action),
                "effort": effort,
                "impact": impact,
                "due_window": due,
            }
        )
    return plan


def save_markdown_report(markdown: str, repo_key: str, reports_dir: str = "reports") -> str:
    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_repo = repo_key.replace("/", "_")
    path = Path(reports_dir) / f"{safe_repo}_{timestamp}.md"
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def generate_architecture_report(
    analysis: RepoAnalysisResult,
    review_agent: ArchitectureReviewAgent,
    writer_agent: Optional[ReportWriterAgent] = None,
    progress_callback: Callable[[str, str, str], None] | None = None,
) -> ArchitectureReport:
    if progress_callback:
        progress_callback("Agent 2", "in_progress", "Architecture Review Agent is evaluating findings.")
    review = review_agent.run(analysis=analysis)
    action_plan = _build_action_plan(review.recommendations, review.risks_and_antipatterns)
    if progress_callback:
        progress_callback("Agent 2", "completed", "Architecture review completed.")

    if progress_callback:
        progress_callback("Report generation", "in_progress", "Compiling final markdown report.")
    if writer_agent:
        markdown = writer_agent.run(analysis=analysis, review=review)
        markdown += "\n\n## Prioritized Action Plan\n"
        if action_plan:
            for item in action_plan:
                markdown += (
                    f"- [{item['priority']}] {item['action']} | owner={item['owner_role']} | "
                    f"effort={item['effort']} | impact={item['impact']} | due={item['due_window']}\n"
                )
        else:
            markdown += "- No action plan generated\n"
    else:
        markdown = build_markdown_report(
            analysis=analysis,
            project_overview=review.project_overview,
            observations=review.architecture_observations,
            risks=review.risks_and_antipatterns,
            recommendations=review.recommendations,
            next_steps=review.next_steps,
            action_plan=action_plan,
        )

    report_path = save_markdown_report(markdown=markdown, repo_key=analysis.repo.full_name)
    if progress_callback:
        progress_callback("Report generation", "completed", f"Report saved to {report_path}.")
    return ArchitectureReport(
        title=f"Architecture Review: {analysis.repo.full_name}",
        repo_full_name=analysis.repo.full_name,
        focus=analysis.focus,  # type: ignore[arg-type]
        summary=review.project_overview,
        detected_stack=analysis.tech_stack,
        module_breakdown=analysis.structure.modules,
        architecture_observations=review.architecture_observations,
        risks_and_antipatterns=review.risks_and_antipatterns,
        recommendations=review.recommendations,
        next_steps=review.next_steps,
        action_plan=action_plan,
        raw_evidence=analysis.evidence,
        markdown_report=markdown,
        report_path=report_path,
    )


class ReviewPipeline:
    """Coordinates agents, tools, and memory."""

    def __init__(
        self,
        repo_agent: RepositoryAnalysisAgent,
        review_agent: ArchitectureReviewAgent,
        memory_store: MemoryStore,
        writer_agent: Optional[ReportWriterAgent] = None,
    ) -> None:
        self.repo_agent = repo_agent
        self.review_agent = review_agent
        self.writer_agent = writer_agent
        self.memory_store = memory_store

    def run(
        self,
        owner: str,
        repo: str,
        focus: ReportFocus = "general",
        report_depth: str = "deep",
        user_key: str = "default_user",
        progress_callback: Callable[[str, str, str], None] | None = None,
    ) -> Dict:
        if progress_callback:
            progress_callback("Fetching repo", "in_progress", "Connecting to GitHub repository.")
            progress_callback("Sampling files", "in_progress", "Preparing repository file sample.")
        analysis = self.repo_agent.run(
            owner=owner,
            repo=repo,
            focus=focus,
            report_depth=report_depth,
            progress_callback=progress_callback,
        )
        report = generate_architecture_report(
            analysis=analysis,
            review_agent=self.review_agent,
            writer_agent=self.writer_agent,
            progress_callback=progress_callback,
        )

        memory_record = MemoryRecord(
            repo_key=f"{owner}/{repo}",
            summary=report.summary,
            tech_stack=report.detected_stack,
            risks=report.risks_and_antipatterns,
            recommendations=report.recommendations,
            focus=focus,
            report_depth=report_depth,  # type: ignore[arg-type]
            risk_count=len(report.risks_and_antipatterns),
            module_count=len(analysis.structure.modules),
            dependency_count=sum(len(dep.dependencies) for dep in analysis.dependencies),
            stack_signature="|".join(sorted([s.lower() for s in report.detected_stack])),
            architecture_patterns=analysis.evidence.get(
                "heuristic_architecture_patterns",
                analysis.architectural_patterns,
            ),
            entry_points_count=len(analysis.structure.entry_points),
            config_files_count=len(analysis.structure.config_files),
            sampled_file_paths=analysis.evidence.get("sampled_files", [])[:300],
            config_file_paths=analysis.structure.config_files[:120],
            entry_point_paths=analysis.structure.entry_points[:120],
            key_directories=analysis.structure.key_directories[:60],
        )
        comparison = compare_with_previous(
            memory_store=self.memory_store,
            repo_key=memory_record.repo_key,
            summary=memory_record.summary,
            tech_stack=memory_record.tech_stack,
            risks=memory_record.risks,
            recommendations=memory_record.recommendations,
            focus=memory_record.focus,
            report_depth=memory_record.report_depth,
            risk_count=memory_record.risk_count,
            module_count=memory_record.module_count,
            dependency_count=memory_record.dependency_count,
            stack_signature=memory_record.stack_signature,
            architecture_patterns=memory_record.architecture_patterns,
            entry_points_count=memory_record.entry_points_count,
            config_files_count=memory_record.config_files_count,
        )

        self.memory_store.store_analysis_memory(memory_record)
        self.memory_store.save_preferences(
            user_key=user_key,
            preferences={"focus": focus, "report_depth": report_depth},
        )
        repo_history = self.memory_store.get_run_history(limit=20, repo_key=memory_record.repo_key)

        return {
            "analysis": analysis.model_dump(),
            "report": report.model_dump(),
            "comparison": comparison,
            "history": repo_history,
        }
