from __future__ import annotations

from src.memory.memory_store import MemoryStore
from src.models.schemas import MemoryRecord


def _record(repo_key: str, risks: list[str], focus: str = "general") -> MemoryRecord:
    return MemoryRecord(
        repo_key=repo_key,
        summary="summary",
        tech_stack=["python"],
        risks=risks,
        recommendations=["add tests"],
        focus=focus,  # type: ignore[arg-type]
        report_depth="deep",
        risk_count=len(risks),
        module_count=3,
        dependency_count=5,
        stack_signature="python",
        architecture_patterns=["Service layer abstraction present"],
        entry_points_count=1,
        config_files_count=2,
        sampled_file_paths=["src/app.py", "src/service.py"],
        config_file_paths=["requirements.txt"],
        entry_point_paths=["src/app.py"],
        key_directories=["src"],
    )


def test_memory_store_read_write_compare(tmp_path) -> None:
    store_path = tmp_path / "memory_store.json"
    memory = MemoryStore(store_path=str(store_path))

    first = _record("org/repo", ["risk-a", "risk-b"])
    memory.store_analysis_memory(first)

    loaded = memory.retrieve_analysis_memory("org/repo")
    assert loaded is not None
    assert loaded["repo_key"] == "org/repo"
    assert loaded["risk_count"] == 2

    second = _record("org/repo", ["risk-b", "risk-c"], focus="security")
    comparison = memory.compare_with_previous(second)
    assert comparison.previous_exists is True
    assert comparison.new_risks == ["risk-c"]
    assert comparison.resolved_risks == ["risk-a"]
    assert comparison.focus_changed is True
