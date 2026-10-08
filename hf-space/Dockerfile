# Free CPU Space: llama.cpp's OpenAI-compatible server with a small quantised instruct model.
# --jinja turns on the model's chat template, which is what makes tool calling work.
# Change MODEL to try another GGUF (repo:quant). Smaller = faster; bigger = better at tools.
FROM ghcr.io/ggml-org/llama.cpp:server

ENV LLAMA_CACHE=/tmp/llama-cache \
    MODEL=bartowski/Qwen2.5-3B-Instruct-GGUF:Q4_K_M

EXPOSE 7860
# LLAMA_API_KEY (Space secret) makes the server require "Authorization: Bearer <key>".
ENTRYPOINT ["/bin/sh", "-c", "exec /app/llama-server -hf $MODEL --jinja --host 0.0.0.0 --port 7860 -c 8192 -t 2 --parallel 1"]
