PYTHON ?= python3
PIP ?= pip3

.PHONY: install test run scenarios demo reset export-audit

install:
	$(PIP) install -r requirements.txt

test:
	pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

scenarios:
	$(PYTHON) -m scenarios.run_all

demo:
	$(PYTHON) scripts/run_demo.py

reset:
	$(PYTHON) scripts/reset_lab.py

export-audit:
	$(PYTHON) scripts/export_audit.py
