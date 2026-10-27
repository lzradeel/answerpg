PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
QUESTION ?= Which regions can an Enterprise workspace keep its data in?

.PHONY: install db down index serve test lint evaluate compare rebaseline latency demo

install:
	$(PYTHON) -m pip install -e ".[dev]"

db:
	docker compose up -d --wait postgres

down:
	docker compose down

index:
	$(PYTHON) scripts/index_corpus.py

serve:
	$(PYTHON) -m uvicorn answerpg.server:app --reload

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

evaluate:
	$(PYTHON) -m evaluation.gate

compare:
	$(PYTHON) -m evaluation.gate --compare

rebaseline:
	$(PYTHON) -m evaluation.gate --compare --write-baseline

latency:
	$(PYTHON) scripts/latency.py

demo:
	docker compose up -d --build --wait
	docker compose exec app python scripts/index_corpus.py
	curl -s localhost:8000/answer -H "Content-Type: application/json" \
		-d '{"question": "$(QUESTION)"}' | python3 -m json.tool
