.PHONY: setup preflight normalize audit analyze video kol smoke check

setup:
	./setup.sh

preflight:
	.venv/bin/python tools/preflight.py

normalize:
	.venv/bin/python -m pipeline.normalize

audit:
	.venv/bin/python -m pipeline.audit --strict

analyze:
	.venv/bin/python -m pipeline.analyze.metrics
	.venv/bin/python -m pipeline.analyze.themes
	.venv/bin/python -m pipeline.analyze.balanced
	.venv/bin/python -m pipeline.analyze.deep
	.venv/bin/python -m pipeline.analyze.negative

video:
	.venv/bin/python -m pipeline.video.run --offline
	.venv/bin/python -m pipeline.report.build_showcase

kol:
	.venv/bin/python -m pipeline.kol.extract
	.venv/bin/python -m pipeline.kol.aggregate

smoke:
	python3 tools/smoke_test.py

check:
	python3 tools/check_anonymity.py
	python3 tools/check_paths.py
