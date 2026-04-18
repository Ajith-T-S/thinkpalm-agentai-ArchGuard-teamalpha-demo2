from __future__ import annotations

import pytest

from src.utils.helpers import parse_github_input


def test_parse_github_input_from_owner_repo() -> None:
    owner, repo = parse_github_input("langchain-ai/langchain")
    assert owner == "langchain-ai"
    assert repo == "langchain"


def test_parse_github_input_from_url() -> None:
    owner, repo = parse_github_input("https://github.com/streamlit/streamlit")
    assert owner == "streamlit"
    assert repo == "streamlit"


def test_parse_github_input_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_github_input("not-a-valid-repo")
