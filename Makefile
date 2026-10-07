# Chhaanv developer commands. Run `make help`.
PYTHON ?= python3
LAYER := build/layer/python
ENDPOINT ?= http://localhost:4566
LOCAL_ENV := AWS_ENDPOINT_URL=$(ENDPOINT) AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=ap-south-1 TABLE_NAME=chhaanv-main BUCKET_NAME=chhaanv-data-local

.PHONY: help test validate layer build local-up local-down local-setup seed api clean

help:
	@echo "test         unit tests"
	@echo "validate     check data files"
	@echo "build        pack the core layer and run sam build"
	@echo "local-up     start LocalStack (DynamoDB, S3) in Docker"
	@echo "local-setup  create the table and bucket in LocalStack, upload city files"
	@echo "seed         run fetch_forecast + compute_risk for every cell into LocalStack"
	@echo "             (SEED_ARGS=--offline uses the synthetic fixture instead of Open-Meteo)"
	@echo "api          sam local start-api on :3000, wired to LocalStack"
	@echo "local-down   stop LocalStack"

test:
	$(PYTHON) -m pytest -q

validate:
	$(PYTHON) scripts/validate_data.py --quiet

layer:
	rm -rf build/layer
	mkdir -p $(LAYER)
	cp -r engine backend $(LAYER)/
	mkdir -p $(LAYER)/data
	cp -r data/cities data/hotspots data/relief $(LAYER)/data/
	find build/layer -name __pycache__ -prune -exec rm -rf {} +

build: layer
	sam build

local-up:
	docker compose up -d --wait localstack

local-down:
	docker compose down

local-setup:
	$(LOCAL_ENV) $(PYTHON) scripts/local_setup.py

seed:
	$(LOCAL_ENV) $(PYTHON) scripts/seed_local.py $(SEED_ARGS)

# SAM_LOCAL_ARGS lets you add e.g. --invoke-image amazon/aws-lambda-python:3.12
# when public.ecr.aws is unreachable.
api: build
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=ap-south-1 \
	sam local start-api --env-vars env.local.json --docker-network chhaanv $(SAM_LOCAL_ARGS)

clean:
	rm -rf build .aws-sam
