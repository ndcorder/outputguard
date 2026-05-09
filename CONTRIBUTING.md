# Contributing to outputguard

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ndcorder/outputguard.git
   cd outputguard
   ```

2. Install [uv](https://docs.astral.sh/uv/):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install dependencies:
   ```bash
   uv sync --dev
   ```

4. Run the tests:
   ```bash
   uv run pytest tests/ -v
   ```

## Making Changes

1. Create a branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Run the test suite: `uv run pytest tests/ -v`
4. Commit with a descriptive message: `git commit -m "feat: add xyz"`

## Adding a Repair Strategy

outputguard's architecture makes it easy to add new repair strategies:

1. Create `outputguard/strategies/your_strategy.py`:
   ```python
   NAME = "your_strategy"
   DESCRIPTION = "What this strategy does"

   def apply(text: str) -> str:
       # Your repair logic here
       # MUST: return text unchanged if nothing to fix
       # MUST: never raise exceptions
       return text
   ```

2. Register it in `outputguard/strategies/__init__.py`:
   - Import your module
   - Add `(your_strategy.NAME, your_strategy.apply)` to `ALL_STRATEGIES`
   - Add the description to `STRATEGY_DESCRIPTIONS`

3. Create tests in `tests/test_strategies/test_your_strategy.py`

4. Run the full suite to make sure nothing breaks

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` -- new feature
- `fix:` -- bug fix
- `docs:` -- documentation changes
- `test:` -- test additions or fixes
- `refactor:` -- code changes that neither fix a bug nor add a feature
- `chore:` -- maintenance tasks

## Code Style

- We use `ruff` for linting and formatting
- Type hints are encouraged
- No comments unless the WHY is non-obvious
- Keep functions focused and small

## Testing

- Every new feature needs tests
- Every bug fix needs a regression test
- Run `uv run pytest tests/ -v --tb=short` before submitting

## Pull Requests

- Keep PRs focused -- one feature or fix per PR
- Include a clear description of what changed and why
- Make sure all tests pass
- Update README.md if adding user-facing features
