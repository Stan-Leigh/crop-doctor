.PHONY: install playground custom-playground run test

install:
	uv sync

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

custom-playground: run

run:
	uv run python3 app/fast_api_app.py

test:
	uv run pytest tests/

