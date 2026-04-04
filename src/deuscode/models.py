from typing import TypedDict


class ModelEntry(TypedDict):
    id: str
    label: str
    category: str
    vram_gb: int
    description: str


MODELS: list[ModelEntry] = [
    {
        "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "label": "Qwen2.5-Coder-32B",
        "category": "Coding",
        "vram_gb": 40,
        "description": "Best coding model, recommended",
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
        "vram_gb": 24,
        "description": "Strong coding alternative",
    },
    {
        "id": "meta-llama/Llama-3.1-70B-Instruct",
        "label": "Llama-3.1-70B",
        "category": "General",
        "vram_gb": 80,
        "description": "Powerful general purpose",
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
        "vram_gb": 16,
        "description": "Lightweight, fast",
    },
]

CUSTOM_MODEL_OPTION = "Custom (type manually)"
