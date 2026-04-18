.PHONY: test lint format run-ui run-cli

test:
	pytest -q

lint:
	ruff check src tests app.py main.py

format:
	black src tests app.py main.py

run-ui:
	streamlit run app.py

run-cli:
	python main.py analyze langchain-ai/langchain --focus general
