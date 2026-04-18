from __future__ import annotations

from src.tools.analysis_tools import parse_dependencies


def test_parse_dependencies_from_requirements_and_package_json() -> None:
    file_contents = {
        "requirements.txt": "streamlit==1.51.0\nrequests>=2.0\n# comment\n",
        "package.json": '{"dependencies":{"react":"18.2.0"},"devDependencies":{"vite":"5.0.0"}}',
    }

    deps = parse_dependencies(file_contents)
    ecosystems = {d.ecosystem for d in deps}

    assert "python" in ecosystems
    assert "node" in ecosystems
    assert any("streamlit==1.51.0" in item for d in deps for item in d.dependencies)
    assert any("react@18.2.0" in item for d in deps for item in d.dependencies)


def test_parse_dependencies_handles_invalid_package_json() -> None:
    deps = parse_dependencies({"package.json": "{not json}"})
    assert len(deps) == 1
    assert deps[0].ecosystem == "node"
    assert deps[0].dependencies == ["Could not parse package.json"]
