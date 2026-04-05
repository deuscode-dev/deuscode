from deuscode.models import MODELS, _tier_label


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


def test_tier_label_boundaries():
    assert _tier_label(70) == "★ Best for complex tasks"
    assert _tier_label(32) == "★ Recommended — full power"
    assert _tier_label(14) == "✓ Good for most tasks"
    assert _tier_label(7) == "⚡ Basic tasks only"


def test_all_models_have_tier_label():
    for m in MODELS:
        assert "tier_label" in m and m["tier_label"], f"Missing tier_label for {m['id']}"


def test_all_models_have_param_count():
    for m in MODELS:
        assert m.get("param_count_b", 0) > 0, f"Missing param_count_b for {m['id']}"
