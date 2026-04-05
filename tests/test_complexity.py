from deuscode.complexity import detect_complexity, Complexity


def test_simple_question():
    assert detect_complexity("What is a generator?") == Complexity.SIMPLE


def test_simple_short_prompt():
    assert detect_complexity("How does asyncio work?") == Complexity.SIMPLE


def test_simple_explain():
    assert detect_complexity("Explain this code") == Complexity.SIMPLE


def test_complex_implement():
    assert detect_complexity("Implement a caching layer with Redis and add tests") == Complexity.COMPLEX


def test_complex_multi_step():
    assert detect_complexity("Refactor the auth module and also add error handling") == Complexity.COMPLEX


def test_complex_long_prompt():
    prompt = " ".join(["word"] * 30)
    assert detect_complexity(prompt) == Complexity.COMPLEX
