# Pravaah developer commands. CI runs `make ci`, so new checks go here.
PYTHON ?= python3
LAYER := build/layer/python
ENDPOINT ?= http://localhost:4566
LOCAL_ENV := AWS_ENDPOINT_URL=$(ENDPOINT) AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=ap-south-1 TABLE_NAME=pravaah-main BUCKET_NAME=pravaah-data-local

.PHONY: real-data ci test validate smoke calibrate dashboard-build dashboard-dev assistant-layer assistant-eval layer build local-up local-down local-setup seed api clean deploy deploy-workers forecast-now
STACK ?= pravaah

ci: test validate smoke dashboard-build

test:
	$(PYTHON) -m pytest -q

validate:
	$(PYTHON) scripts/validate_data.py --quiet

smoke:
	$(PYTHON) -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --temp 33 --rh 65 --ci 680

# Needs internet (Open-Meteo, Electricity Maps). Laptop or Colab; ELECTRICITYMAPS_TOKEN for real carbon.
# REPLAY_ARGS="--trace data/trace.alibaba.csv" once you have sampled the real trace (scripts/sample_trace.py).
real-data:
	$(PYTHON) scripts/pull_history.py --days 60
	$(PYTHON) scripts/validate_data.py --history
	$(PYTHON) scripts/replay.py $(REPLAY_ARGS)
	@$(PYTHON) -c "import json; d=json.load(open('dashboard/public/replay.json')); print('\nweather/carbon:', d['assumptions'][0]); print('headline:', d['headline'])"
	@echo "Review dashboard/public/replay.json, then commit it. Quote its numbers only if the line above says history."

calibrate:
	$(PYTHON) scripts/calibrate_wue.py

dashboard-build:
	cd dashboard && npm ci --silent && npm run build --silent

# VITE_API_URL defaults to http://localhost:3000 (make api)
dashboard-dev:
	cd dashboard && npm install --silent && npx vite

# --- backend ------------------------------------------------------------------

layer:
	rm -rf build/layer
	mkdir -p $(LAYER)/data
	cp -r model scheduler sources backend forecasting assistant $(LAYER)/
	cp data/regions.yaml $(LAYER)/data/
	cp functions/worker/app.py $(LAYER)/worker_inline.py
	$(PYTHON) -m pip install --quiet --target $(LAYER) --platform manylinux2014_x86_64 \
		--implementation cp --python-version 3.12 --only-binary=:all: "pyyaml>=6"
	find build/layer -name __pycache__ -prune -exec rm -rf {} +

# Strands + Anthropic SDK for the chat function (kept out of the core layer: size)
assistant-layer:
	rm -rf build/assistant-layer
	mkdir -p build/assistant-layer/python
	$(PYTHON) -m pip install --quiet --target build/assistant-layer/python --platform manylinux2014_x86_64 \
		--implementation cp --python-version 3.12 --only-binary=:all: -r requirements-assistant.txt

build: layer assistant-layer
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

# --- AWS (Step 8) ---------------------------------------------------------------

MAIN_REGION ?= ap-south-1
WORKER_REGIONS ?= ap-south-1 ap-south-2 ap-southeast-1 eu-north-1 eu-west-1 eu-central-1 us-east-1 us-west-2

deploy: build
	sam deploy --guided

# Deploy the worker in every region except the main stack's (which has its own).
deploy-workers:
	for r in $(filter-out $(MAIN_REGION),$(WORKER_REGIONS)); do \
		sam deploy --template-file worker.yaml --stack-name pravaah-worker --region $$r \
			--resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset; \
	done

forecast-now:
	aws stepfunctions start-execution --state-machine-arn $$(aws cloudformation describe-stacks \
		--stack-name $(STACK) --query "Stacks[0].Outputs[?OutputKey=='ForecastStateMachineArn'].OutputValue" --output text)

# Step 13: grade the assistant on evals/assistant.yaml (costs model tokens; needs a key)
assistant-eval:
	$(PYTHON) -m assistant.eval
