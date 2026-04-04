from typing import TypedDict


class ModelEntry(TypedDict):
    id: str
    label: str
    category: str
    vram_gb: int
    description: str


MODELS: list[ModelEntry] = [
    # ── Coding ──────────────────────────────────────────────────────────────
    {
        "id": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "label": "Qwen2.5-Coder-1.5B",
        "category": "Coding",
        "vram_gb": 4,
        "description": "Tiny, runs on any GPU",
    },
    {
        "id": "Qwen/Qwen2.5-Coder-3B-Instruct",
        "label": "Qwen2.5-Coder-3B",
        "category": "Coding",
        "vram_gb": 8,
        "description": "Small but capable coder",
    },
    {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "label": "Qwen2.5-Coder-7B",
        "category": "Coding",
        "vram_gb": 16,
        "description": "Fast and cheap coding model",
    },
    {
        "id": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        "label": "DeepSeek-Coder-V2-Lite",
        "category": "Coding",
        "vram_gb": 32,
        "description": "MoE coder, strong for its size",
    },
    {
        "id": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "label": "Qwen2.5-Coder-14B",
        "category": "Coding",
        "vram_gb": 28,
        "description": "Best mid-size coding model",
    },
    {
        "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "label": "Qwen2.5-Coder-32B",
        "category": "Coding",
        "vram_gb": 64,
        "description": "Top coding quality, needs A100",
    },
    # ── General ─────────────────────────────────────────────────────────────
    {
        "id": "meta-llama/Llama-3.2-1B-Instruct",
        "label": "Llama-3.2-1B",
        "category": "General",
        "vram_gb": 3,
        "description": "Ultra-small, very fast",
    },
    {
        "id": "meta-llama/Llama-3.2-3B-Instruct",
        "label": "Llama-3.2-3B",
        "category": "General",
        "vram_gb": 8,
        "description": "Small general purpose",
    },
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct",
        "label": "Llama-3.1-8B",
        "category": "General",
        "vram_gb": 16,
        "description": "Fast general purpose",
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "label": "Mistral-7B",
        "category": "General",
        "vram_gb": 14,
        "description": "Lightweight, fast",
    },
    {
        "id": "mistralai/Mistral-Nemo-Instruct-2407",
        "label": "Mistral-Nemo-12B",
        "category": "General",
        "vram_gb": 24,
        "description": "Strong 12B from Mistral+NVIDIA",
    },
    {
        "id": "google/gemma-2-9b-it",
        "label": "Gemma-2-9B",
        "category": "General",
        "vram_gb": 18,
        "description": "Google's efficient 9B model",
    },
    {
        "id": "google/gemma-2-27b-it",
        "label": "Gemma-2-27B",
        "category": "General",
        "vram_gb": 54,
        "description": "Google's high-quality 27B model",
    },
    {
        "id": "meta-llama/Llama-3.1-70B-Instruct",
        "label": "Llama-3.1-70B",
        "category": "General",
        "vram_gb": 140,
        "description": "Powerful, needs multi-GPU",
    },
]

CUSTOM_MODEL_OPTION = "Custom (type manually)"

# vLLM --tool-call-parser value per model family
_TOOL_CALL_PARSERS: dict[str, str] = {
    "qwen":      "hermes",
    "deepseek":  "hermes",
    "llama":     "llama3_json",
    "mistral":   "mistral",
}


def tool_call_parser(model_id: str) -> str | None:
    lower = model_id.lower()
    for family, parser in _TOOL_CALL_PARSERS.items():
        if family in lower:
            return parser
    return None

_SIZE_OPTIONS = [
    ("ALL",    "Show all models"),
    ("small",  "Small  (≤16 GB VRAM) — cheapest GPUs"),
    ("medium", "Medium (17–40 GB VRAM)"),
    ("large",  "Large  (>40 GB VRAM) — highest quality"),
]


def filter_by_size(models: list[ModelEntry], size: str) -> list[ModelEntry]:
    if size == "ALL":
        return models
    if size == "small":
        return [m for m in models if m["vram_gb"] <= 16]
    if size == "medium":
        return [m for m in models if 17 <= m["vram_gb"] <= 40]
    if size == "large":
        return [m for m in models if m["vram_gb"] > 40]
    return models


_SIZE_RANGES: dict[str, tuple[int, int]] = {
    "small":  (0, 16),
    "medium": (17, 40),
    "big":    (41, 999),
}


def get_models_by_size(size: str) -> list[ModelEntry]:
    """Filter by size name (small/medium/big/all). Case-insensitive."""
    key = size.lower()
    if key == "all":
        return MODELS
    lo, hi = _SIZE_RANGES.get(key, (0, 999))
    return [m for m in MODELS if lo <= m["vram_gb"] <= hi]
