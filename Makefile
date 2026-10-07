# Pravaah developer commands. CI runs `make ci`, so new checks go here.
PYTHON ?= python3

.PHONY: ci test validate smoke calibrate

ci: test validate smoke

test:
	$(PYTHON) -m pytest -q

validate:
	$(PYTHON) scripts/validate_data.py --quiet

smoke:
	$(PYTHON) -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --temp 33 --rh 65 --ci 680

calibrate:
	$(PYTHON) scripts/calibrate_wue.py
