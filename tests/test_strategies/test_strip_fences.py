from outputguard.strategies.strip_fences import apply


def test_json_fence():
    assert apply('```json\n{"a":1}\n```') == '{"a":1}'


def test_plain_fence():
    assert apply('```\n{"a":1}\n```') == '{"a":1}'


def test_no_fences():
    assert apply('{"a":1}') == '{"a":1}'


def test_multiple_fences():
    # Extracts from first fenced block
    text = '```json\n{"a":1}\n```\n```json\n{"b":2}\n```'
    assert apply(text) == '{"a":1}'


def test_jsonc_fence():
    assert apply('```jsonc\n{"a":1}\n```') == '{"a":1}'


def test_javascript_fence():
    assert apply('```javascript\n{"a":1}\n```') == '{"a":1}'
