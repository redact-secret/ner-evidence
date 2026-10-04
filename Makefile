PY ?= python3
export PYTHONPATH := src

.PHONY: check test validate
check:
	$(PY) -m ner_evidence check
test:
	$(PY) -m unittest discover -s tests -v
validate:
	$(PY) -m ner_evidence validate
