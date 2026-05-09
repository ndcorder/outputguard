#!/usr/bin/env python3
"""Fetch all instruct models from OpenRouter and generate the model list."""
import json
import os
import urllib.request

api_key = os.environ.get("OPENROUTER_API_KEY", "")
req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
)

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())

models = data.get("data", [])

SKIP_PATTERNS = [
    ":free", ":extended", "embed", "tts", "whisper", "transcribe",
    "guard", "image", "audio", "lyria", "chirp", "video",
    "search-preview", "deep-research", "multi-agent",
    "router", "openrouter/", "switchpoint", "relace",
    "safeguard", "ui-tars", "customtools",
]

text_models = []
for m in models:
    arch = m.get("architecture", {})
    input_mods = arch.get("input_modalities", [])
    output_mods = arch.get("output_modalities", [])
    if "text" not in input_mods or "text" not in output_mods:
        continue
    mid = m["id"]
    if any(p in mid.lower() for p in SKIP_PATTERNS):
        continue
    # Skip aliases starting with ~
    if mid.startswith("~"):
        continue
    text_models.append(mid)

text_models.sort()
print(f"Found {len(text_models)} text instruct models\n")
for m in text_models:
    print(f"  {m}")

with open("tests/all_model_ids.json", "w") as f:
    json.dump(text_models, f, indent=2)
print(f"\nSaved {len(text_models)} models to tests/all_model_ids.json")
