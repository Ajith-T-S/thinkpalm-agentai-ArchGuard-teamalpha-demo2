"""Persistent and in-session memory storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.schemas import MemoryComparison, MemoryRecord
from src.utils.helpers import load_json_file, save_json_file


class MemoryStore:
    def __init__(self, store_path: str = "data/memory_store.json") -> None:
        self.store_path = Path(store_path)
        self._session_cache: Dict[str, Any] = {}
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        default = {"analyses": {}, "history": [], "preferences": {}}
        payload = load_json_file(self.store_path, default=default)
        payload.setdefault("analyses", {})
        payload.setdefault("history", [])
        payload.setdefault("preferences", {})
        return payload

    def _save(self) -> None:
        save_json_file(self.store_path, self._data)

    def store_analysis_memory(self, record: MemoryRecord) -> None:
        dump = record.model_dump()
        self._data["analyses"][record.repo_key] = dump
        self._data["history"].append(dump)
        self._session_cache[record.repo_key] = dump
        self._save()

    def retrieve_analysis_memory(self, repo_key: str) -> Optional[Dict[str, Any]]:
        if repo_key in self._session_cache:
            return self._session_cache[repo_key]
        return self._data["analyses"].get(repo_key)

    def save_preferences(self, user_key: str, preferences: Dict[str, Any]) -> None:
        self._data["preferences"][user_key] = preferences
        self._session_cache[f"pref::{user_key}"] = preferences
        self._save()

    def get_preferences(self, user_key: str) -> Dict[str, Any]:
        return self._session_cache.get(
            f"pref::{user_key}",
            self._data["preferences"].get(user_key, {}),
        )

    def get_run_history(self, limit: int = 20, repo_key: Optional[str] = None) -> List[Dict[str, Any]]:
        records = []
        history = self._data.get("history", [])
        if history:
            for value in history:
                key = value.get("repo_key", "")
                if repo_key and key != repo_key:
                    continue
                row = {
                    "repo_key": key,
                    "analyzed_at": value.get("analyzed_at"),
                    "focus": value.get("focus", "general"),
                    "report_depth": value.get("report_depth", "deep"),
                    "risk_count": value.get("risk_count", len(value.get("risks", []))),
                    "module_count": value.get("module_count", 0),
                    "dependency_count": value.get("dependency_count", 0),
                }
                records.append(row)
        else:
            analyses = self._data.get("analyses", {})
            for key, value in analyses.items():
                if repo_key and key != repo_key:
                    continue
                row = {
                    "repo_key": key,
                    "analyzed_at": value.get("analyzed_at"),
                    "focus": value.get("focus", "general"),
                    "report_depth": value.get("report_depth", "deep"),
                    "risk_count": value.get("risk_count", len(value.get("risks", []))),
                    "module_count": value.get("module_count", 0),
                    "dependency_count": value.get("dependency_count", 0),
                }
                records.append(row)
        records.sort(key=lambda x: x.get("analyzed_at") or "", reverse=True)
        return records[:limit]

    def compare_with_previous(self, record: MemoryRecord) -> MemoryComparison:
        previous = self.retrieve_analysis_memory(record.repo_key)
        if not previous:
            return MemoryComparison(repo_key=record.repo_key, previous_exists=False)

        previous_risks = set(previous.get("risks", []))
        current_risks = set(record.risks)
        new_risks = sorted(current_risks - previous_risks)
        resolved_risks = sorted(previous_risks - current_risks)

        previous_risk_count = int(previous.get("risk_count", len(previous_risks)))
        previous_module_count = int(previous.get("module_count", 0))
        previous_dependency_count = int(previous.get("dependency_count", 0))
        previous_stack_signature = previous.get(
            "stack_signature",
            "|".join(sorted([s.lower() for s in previous.get("tech_stack", [])])),
        )
        previous_patterns = set(previous.get("architecture_patterns", []))
        current_patterns = set(record.architecture_patterns)

        previous_sampled_files = set(previous.get("sampled_file_paths", []))
        current_sampled_files = set(record.sampled_file_paths)
        added_files = sorted(current_sampled_files - previous_sampled_files)
        removed_files = sorted(previous_sampled_files - current_sampled_files)

        previous_config_files = set(previous.get("config_file_paths", []))
        current_config_files = set(record.config_file_paths)
        previous_entry_points = set(previous.get("entry_point_paths", []))
        current_entry_points = set(record.entry_point_paths)
        previous_key_dirs = set(previous.get("key_directories", []))
        current_key_dirs = set(record.key_directories)

        risk_delta = record.risk_count - previous_risk_count
        module_delta = record.module_count - previous_module_count
        dependency_delta = record.dependency_count - previous_dependency_count
        stack_changed = previous_stack_signature != record.stack_signature
        pattern_changes = {
            "added": sorted(current_patterns - previous_patterns),
            "removed": sorted(previous_patterns - current_patterns),
        }
        file_changes = {
            "added_count": len(added_files),
            "removed_count": len(removed_files),
            "added_samples": added_files[:20],
            "removed_samples": removed_files[:20],
        }
        architecture_changes = {
            "added_config_files": sorted(current_config_files - previous_config_files),
            "removed_config_files": sorted(previous_config_files - current_config_files),
            "added_entry_points": sorted(current_entry_points - previous_entry_points),
            "removed_entry_points": sorted(previous_entry_points - current_entry_points),
            "added_key_directories": sorted(current_key_dirs - previous_key_dirs),
            "removed_key_directories": sorted(previous_key_dirs - current_key_dirs),
        }

        score = 50
        score += 10 * len(resolved_risks)
        score -= 12 * len(new_risks)
        if risk_delta < 0:
            score += 8
        elif risk_delta > 0:
            score -= 8
        if not stack_changed:
            score += 2
        if module_delta < 0:
            score -= 3
        if dependency_delta < 0:
            score -= 2
        arch_change_count = (
            len(architecture_changes["added_config_files"])
            + len(architecture_changes["removed_config_files"])
            + len(architecture_changes["added_entry_points"])
            + len(architecture_changes["removed_entry_points"])
            + len(architecture_changes["added_key_directories"])
            + len(architecture_changes["removed_key_directories"])
        )
        if arch_change_count > 0:
            score -= min(10, arch_change_count)
        file_change_count = len(added_files) + len(removed_files)
        if file_change_count > 0:
            score -= min(8, file_change_count // 10)
        score = max(0, min(100, score))

        if score >= 65:
            drift_status = "improved"
        elif score < 45:
            drift_status = "regressed"
        else:
            drift_status = "stable"

        return MemoryComparison(
            repo_key=record.repo_key,
            previous_exists=True,
            previous_analyzed_at=previous.get("analyzed_at"),
            new_risks=new_risks,
            resolved_risks=resolved_risks,
            focus_changed=previous.get("focus") != record.focus,
            risk_delta=risk_delta,
            module_delta=module_delta,
            dependency_delta=dependency_delta,
            stack_changed=stack_changed,
            pattern_changes=pattern_changes,
            file_changes=file_changes,
            architecture_changes=architecture_changes,
            drift_status=drift_status,  # type: ignore[arg-type]
            improvement_score=score,
        )
