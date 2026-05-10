# OutputGuard Documentation

This directory contains the detailed guides for OutputGuard. The README gives a
quick overview; these pages spell out the behavior you need when wiring
OutputGuard into an application, an eval pipeline, or a command-line workflow.

## Start Here

- [Getting started](getting-started.md) walks through the first useful
  validation, repair, retry, guarded-generation, and CLI workflows.
- [Concepts](concepts.md) explains the mental model: parsing, validation,
  repair, formats, retries, and message history.
- [API guide](api.md) explains which function to call and what each result
  object contains.
- [Formats guide](formats.md) explains supported input formats, format aliases,
  auto detection, and JSON compatibility.
- [Guarded generation guide](guarded-generation.md) explains how to wrap an LLM
  call with validation, repair, retry, and failure reporting.
- [Batch processing guide](batch-processing.md) explains the Python batch APIs
  and the `outputguard batch` command.
- [CLI guide](cli.md) lists commands, flags, input shapes, output behavior, and
  exit codes.
- [Recipes](recipes.md) gives copy-paste patterns for common application,
  eval, CI, and privacy workflows.
- [Troubleshooting](troubleshooting.md) maps common symptoms to concrete fixes.
- [Migration to 2.0](migration-2.0.md) explains what changed and how to adopt
  the new APIs safely.
- [2.0 implementation plan](2.0-plan.md) records the design and verification
  checklist used for the 2.0 release.

## Suggested Reading Path

1. Read [Getting started](getting-started.md) if you are new to OutputGuard.
2. Read [Concepts](concepts.md) when you want to understand why a workflow is
   shaped a certain way.
3. Keep [API guide](api.md), [Formats guide](formats.md), and [CLI guide](cli.md)
   open while wiring OutputGuard into a project.
4. Use [Recipes](recipes.md) and [Troubleshooting](troubleshooting.md) when you
   are adapting OutputGuard to real model output.

## Version 2.0 in One Page

OutputGuard 2.0 expands the project from JSON repair into a small structured
output guardrail toolkit. JSON remains the default. Existing calls such as
`validate_and_repair(text, schema)` still behave as JSON workflows unless you
pass a different `format`.

New 2.0 capabilities:

- Validate and repair JSON, YAML, TOML, and Python literals.
- Use `auto` when a pipeline receives mixed structured-output formats.
- Use `forced-json-off` when the model was explicitly told not to produce JSON.
- Wrap a model call with `guarded_generate()` or `guarded_generate_async()`.
- Process many outputs with `validate_batch()` and `repair_batch()`.
- Run batch validation or repair from the CLI with `outputguard batch`.

## Compatibility Notes

- JSON is still the default format.
- The package does not call an LLM provider directly. You pass your own callable
  to guarded generation.
- OutputGuard repairs syntax and common structural problems. It does not infer
  your product schema unless you validate the parsed result yourself.
- `strict=True` means unresolved repair issues raise exceptions instead of
  returning a partial result.
