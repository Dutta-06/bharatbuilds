"""Build the Strands agent.

Model, chosen by ASSISTANT_PROVIDER:
- anthropic: Claude Opus 5.5 via the Anthropic API (needs ANTHROPIC_API_KEY).
- bedrock: Claude via Amazon Bedrock (IAM credentials; BEDROCK_MODEL_ID is the model or
  inference-profile id enabled in your account and region).
- openai: any OpenAI-compatible chat endpoint, e.g. an open model such as Qwen or Kimi hosted
  by OpenRouter, Together, Fireworks, DashScope or Moonshot. Needs LLM_BASE_URL, LLM_MODEL_ID
  and LLM_API_KEY. The model must support tool calling. LLM_REASONING_EFFORT (default low; off to omit)
  and LLM_MAX_TOKENS (default 700) keep answers fast.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone

from . import tools as t

MODEL_ID = "claude-opus-5-5"

SYSTEM_PROMPT = """You help ML engineers run flexible AI jobs where and when they use the least water and carbon.

You have three tools: get_surface (what each region and hour would cost), submit_job (place and run a job),
and get_receipt (what a job saved). Turn the user's request into a correctly constrained job:
- GPU-hours, GPU type and parallel GPUs as stated (default 1 A100).
- Deadline: convert relative dates ("by Friday", "tomorrow 6 pm IST") to an ISO 8601 UTC timestamp using
  the current time given with each message. Times without a zone are IST (UTC+05:30).
- Weights: "least water" means water_weight 1, carbon_weight 0; "least carbon" the reverse; otherwise 0.5/0.5.
- Region limits: honour "only in India/EU/US" with allowed_regions or data_residency.
- If the request is missing the amount of work or the deadline, ask one short question instead of guessing.
Submit only when the user asks to run or schedule something; for "when/where would it be best" questions,
use get_surface once and answer from its result without submitting. "Right now" means the `right_now` list;
"best" or "cheapest slot" means the `best` field. A cost is a unitless index (1.0 = running now in the baseline
region, lower is better), never money: do not add a currency, and quote litres of water and kg of CO2 instead.
Reply in the user's language, in at most three sentences, and always end with what happens next
(for example when the job will start, or what you need from them)."""


def llm_keys() -> list[str]:
    """LLM_API_KEY may hold several comma-separated keys (one per account)."""
    return [k.strip() for k in os.environ.get("LLM_API_KEY", "").split(",") if k.strip()]


def build_model(key: str | None = None):
    provider = os.environ.get("ASSISTANT_PROVIDER", "anthropic")
    if provider == "bedrock":
        from strands.models.bedrock import BedrockModel

        return BedrockModel(model_id=os.environ.get("BEDROCK_MODEL_ID", f"anthropic.{MODEL_ID}"),
                            region_name=os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION")))
    if provider == "openai":
        from strands.models.openai import OpenAIModel

        missing = [k for k in ("LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"ASSISTANT_PROVIDER=openai needs {', '.join(missing)}")
        params = {"max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "700"))}     # replies are at most three sentences
        effort = os.environ.get("LLM_REASONING_EFFORT", "low")
        if effort and effort != "off":
            # OpenRouter's unified setting: reasoning models think for fewer tokens (faster); others ignore it.
            params["extra_body"] = {"reasoning": {"effort": effort}}
        return OpenAIModel(client_args={"api_key": key or llm_keys()[0], "base_url": os.environ["LLM_BASE_URL"]},
                           model_id=os.environ["LLM_MODEL_ID"], params=params)
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(model_id=MODEL_ID, max_tokens=16000)


def build_agent(model=None):
    from strands import Agent, tool

    return Agent(
        model=model or build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[tool(t.get_surface), tool(t.submit_job), tool(t.get_receipt)],
        callback_handler=None,
    )


def ask(message: str, agent=None, now: datetime | None = None) -> str:
    """One turn. The current time goes in the user message (not the system prompt) so the
    system prompt stays byte-stable for caching.

    With several LLM_API_KEYs, start from a random one and move to the next when a key is
    rate-limited. Only before any tool has run: after submit_job a retry could submit twice."""
    now = now or datetime.now(timezone.utc)
    prompt = f"[Current time: {now:%Y-%m-%dT%H:%MZ} ({now:%A})]\n{message}"
    keys = llm_keys() if agent is None and os.environ.get("ASSISTANT_PROVIDER") == "openai" else []
    if len(keys) < 2:
        return str((agent or build_agent())(prompt)).strip()

    from strands.types.exceptions import ModelThrottledException

    random.shuffle(keys)
    for i, key in enumerate(keys):
        calls_before = len(t.CALLS)
        try:
            return str(build_agent(build_model(key))(prompt)).strip()
        except ModelThrottledException:
            if i == len(keys) - 1 or len(t.CALLS) != calls_before:
                raise
