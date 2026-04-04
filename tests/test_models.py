from deuscode.models import MODELS


def test_all_models_have_required_fields():
    required = {"id", "label", "category", "vram_gb", "description"}
    for m in MODELS:
        assert required <= m.keys(), f"Model missing fields: {m}"


def test_vram_values_are_positive():
    for m in MODELS:
        assert m["vram_gb"] > 0, f"Non-positive vram_gb for {m['id']}"


def test_no_duplicate_model_ids():
    ids = [m["id"] for m in MODELS]
    assert len(ids) == len(set(ids)), "Duplicate model IDs found"
