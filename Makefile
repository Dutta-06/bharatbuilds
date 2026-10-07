# Pravaah developer commands. CI runs `make ci`, so new checks go here.
PYTHON ?= python3
LAYER := build/layer/python
ENDPOINT ?= http://localhost:4566
LOCAL_ENV := AWS_ENDPOINT_URL=$(ENDPOINT) AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=ap-south-1 TABLE_NAME=pravaah-main BUCKET_NAME=pravaah-data-local

.PHONY: ci test validate smoke calibrate layer build local-up local-down local-setup seed api clean

ci: test validate smoke

test:
	$(PYTHON) -m pytest -q

validate:
	$(PYTHON) scripts/validate_data.py --quiet

smoke:
	$(PYTHON) -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --temp 33 --rh 65 --ci 680

calibrate:
	$(PYTHON) scripts/calibrate_wue.py

# --- backend ------------------------------------------------------------------

layer:
	rm -rf build/layer
	mkdir -p $(LAYER)/data
	cp -r model scheduler sources backend $(LAYER)/
	cp data/regions.yaml $(LAYER)/data/
	$(PYTHON) -m pip install --quiet --target $(LAYER) --platform manylinux2014_x86_64 \
		--implementation cp --python-version 3.12 --only-binary=:all: "pyyaml>=6"
	find build/layer -name __pycache__ -prune -exec rm -rf {} +

build: layer
	sam build

local-up:
	docker compose up -d --wait localstack

local-down:
	docker compose down

local-setup:
	$(LOCAL_ENV) $(PYTHON) scripts/local_setup.py

# SEED_ARGS=--offline uses synthetic weather (no internet needed)
seed:
	$(LOCAL_ENV) $(PYTHON) scripts/seed_local.py $(SEED_ARGS)

# SAM_LOCAL_ARGS="--invoke-image amazon/aws-lambda-python:3.12" if public.ecr.aws is blocked
api: build
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=ap-south-1 \
	sam local start-api --env-vars env.local.json --docker-network pravaah $(SAM_LOCAL_ARGS)

clean:
	rm -rf build .aws-sam
