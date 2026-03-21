install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	mypy src

test:
	pytest -q

ci:
	ruff check src tests
	mypy src
	pytest -q

run-nofx:
	python -m cats_py.apps.run_nofx_collector

run-gateways:
	python -m cats_py.apps.run_websocket_gateways

run-decision:
	python -m cats_py.apps.run_decision_engine

run-execution:
	python -m cats_py.apps.run_execution_daemon
