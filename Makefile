PYTHON ?= .venv/bin/python
CONFIG ?= configs/config.yaml
.PHONY: all data dataset replicate extend test notebooks
all:
	$(PYTHON) run_all.py --config $(CONFIG)
data:
	$(PYTHON) scripts/01_get_data.py --config $(CONFIG)
dataset:
	$(PYTHON) scripts/02_build_dataset.py --config $(CONFIG)
replicate:
	$(PYTHON) scripts/03_replicate.py --config $(CONFIG)
extend:
	$(PYTHON) scripts/04_extend.py --config $(CONFIG)
test:
	$(PYTHON) -m pytest -p no:cacheprovider tests/ -q
notebooks:
	$(PYTHON) scripts/validate_notebooks.py
