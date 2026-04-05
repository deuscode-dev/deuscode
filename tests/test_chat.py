from deuscode.chat import parse_special_command


def test_parse_model_command_with_id():
    result = parse_special_command("--model Qwen/Qwen2.5-7B")
    assert result == ("model", {"model_id": "Qwen/Qwen2.5-7B"})


def test_parse_model_command_without_id():
    result = parse_special_command("--model")
    assert result == ("model", {"model_id": None})


def test_parse_resource_command():
    result = parse_special_command("--resource")
    assert result == ("resource", {})


def test_parse_non_special_command():
    result = parse_special_command("write me a function")
    assert result is None
