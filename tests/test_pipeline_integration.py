from __future__ import annotations

from types import SimpleNamespace

from src.agents.architecture_review_agent import ArchitectureReviewAgent
from src.agents.repo_analysis_agent import RepositoryAnalysisAgent
from src.memory.memory_store import MemoryStore
from src.models.schemas import RepoFileInfo, RepoMetadata
from src.services.report_service import ReviewPipeline


class FakeLLM:
    def invoke(self, messages):
        prompt = messages[-1].content if messages else ""
        if "Return a JSON object with keys" in prompt:
            return SimpleNamespace(
                content=(
                    '{"project_overview":"Mocked overview",'
                    '"architecture_observations":["Layered structure found"],'
                    '"risks_and_antipatterns":["Missing Dockerfile"],'
                    '"recommendations":["Add CI quality gates"],'
                    '"next_steps":["Assign owners for top risks"]}'
                )
            )
        return SimpleNamespace(content="- Architecture has clear entry points\n- Config files are present")


class FakeGitHubService:
    def fetch_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        return RepoMetadata(
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Mock repository",
            default_branch="main",
            language="Python",
            stars=10,
            forks=2,
            open_issues=1,
            topics=["architecture", "agent"],
            private=False,
            archived=False,
            pushed_at="2026-04-17T00:00:00Z",
            html_url=f"https://github.com/{owner}/{repo}",
        )

    def list_repo_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        max_files: int = 300,
        max_file_bytes: int = 120000,
    ):
        return [
            RepoFileInfo(path="README.md", type="blob", size=100),
            RepoFileInfo(path="requirements.txt", type="blob", size=80),
            RepoFileInfo(path="src/app.py", type="blob", size=150),
            RepoFileInfo(path="tests/test_smoke.py", type="blob", size=120),
        ]

    def read_repo_file(self, owner: str, repo: str, path: str, branch: str) -> str:
        contents = {
            "README.md": "# Mock Repo\n",
            "requirements.txt": "streamlit\nrequests\n",
            "src/app.py": "def main():\n    return 'ok'\n",
            "tests/test_smoke.py": "def test_smoke():\n    assert True\n",
        }
        return contents.get(path, "")


def test_pipeline_smoke_with_mocked_github(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    memory_store = MemoryStore(store_path=str(tmp_path / "memory_store.json"))
    repo_agent = RepositoryAnalysisAgent(github_service=FakeGitHubService(), llm=FakeLLM())  # type: ignore[arg-type]
    review_agent = ArchitectureReviewAgent(llm=FakeLLM())  # type: ignore[arg-type]
    pipeline = ReviewPipeline(repo_agent=repo_agent, review_agent=review_agent, memory_store=memory_store)

    result = pipeline.run(owner="demo", repo="sample", focus="general", report_depth="deep")

    assert "analysis" in result
    assert "report" in result
    assert result["analysis"]["repo"]["full_name"] == "demo/sample"
    assert "reports/" in result["report"]["report_path"].replace("\\", "/")
    assert isinstance(result["history"], list)
