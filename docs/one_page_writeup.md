# AI Architecture Review Assistant

## Problem
Architecture reviews are often manual, inconsistent, and hard to repeat over time. Teams need a practical assistant that can inspect a GitHub repo, summarize architecture, and highlight changes between runs.

## Solution
This project provides an end-to-end agentic architecture review assistant with Streamlit UI and CLI support. It ingests a repository, analyzes structure and dependencies, generates a report, and tracks architecture drift using persisted history.

## How it works
1. User provides GitHub URL or `owner/repo`.
2. Pipeline runs staged flow:
   - Fetching repo
   - Sampling files
   - Agent 1 (Repository Analysis)
   - Agent 2 (Architecture Review)
   - Report generation
3. Outputs are rendered in tabs and exportable as markdown/JSON.

## Multi-agent design
- **RepositoryAnalysisAgent**: gathers metadata, files, dependencies, structure, and evidence snippets.
- **ArchitectureReviewAgent**: interprets findings into observations, risks, and recommendations.
- **ReportWriterAgent**: formats final report markdown.

## Tool-calling and ReAct
The analysis stage uses explicit Thought-Action-Observation loops and tool-calling for:
- repo metadata fetch
- repo file listing
- file reading
- stack and dependency analysis
- memory store/retrieve/compare

## Memory and drift
Persistent memory is stored in `data/memory_store.json`:
- `analyses`: latest repo snapshots
- `history`: run-by-run timeline records
- `preferences`: user selections

Drift compares previous and current runs and reports:
- file additions/removals
- architecture-level changes (config files, entry points, key directories)
- score and drift status (`improved`, `stable`, `regressed`)

## Standout features
- **Drift Timeline**: run trend for risk/module/dependency metrics.
- **Prioritized Action Plan**: recommendations converted to execution items with priority, owner role, effort, impact, and due window.
- **Evidence-backed findings**: file snippets linked to findings.
- **Progress + confidence UX**: stage tracker and confidence/coverage-style metrics.

## Deliverable value
The assistant is demo-ready, end-to-end runnable, and submission-friendly with modular code, clear docs, persistent memory, and explainable multi-agent behavior.
