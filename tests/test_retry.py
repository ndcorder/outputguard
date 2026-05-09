from outputguard.models import ValidationError
from outputguard.retry import retry_prompt


def test_contains_errors():
    errors = [
        ValidationError(
            message="expected number", path="$.price", schema_path="properties.price.type"
        ),
    ]
    prompt = retry_prompt(
        '{"price": "free"}', {"type": "object", "properties": {"price": {"type": "number"}}}, errors
    )
    assert "$.price" in prompt
    assert "expected number" in prompt


def test_contains_schema_summary():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    errors = [ValidationError(message="missing", path="$", schema_path="required")]
    prompt = retry_prompt("{}", schema, errors)
    assert "name" in prompt
    assert "age" in prompt


def test_long_output_truncated():
    long_text = '{"x": "' + "a" * 1000 + '"}'
    errors = [ValidationError(message="err", path="$", schema_path="")]
    prompt = retry_prompt(long_text, {"type": "object"}, errors)
    assert "..." in prompt
    assert len(prompt) < len(long_text) + 500
