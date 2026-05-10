# Examples

These examples show common outputguard usage patterns.

| Example | Description |
|---|---|
| [basic_usage.py](basic_usage.py) | Core validate/repair workflow |
| [retry_loop.py](retry_loop.py) | Retry pattern with correction prompts |
| [guarded_generation.py](guarded_generation.py) | Provider-agnostic guarded generation |
| [custom_pipeline.py](custom_pipeline.py) | Custom strategy configuration |
| [batch_processing.py](batch_processing.py) | Process multiple outputs with statistics |

## Running

```bash
# From the project root:
uv run python examples/basic_usage.py
uv run python examples/retry_loop.py
uv run python examples/guarded_generation.py
uv run python examples/custom_pipeline.py
uv run python examples/batch_processing.py
```
