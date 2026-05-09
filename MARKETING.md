# outputguard — Launch Plan

Ready-to-post content for each platform. Copy, paste, adjust as needed.

---

## Reddit

### r/Python (largest reach, most critical audience)

**Title:** `I built a library that fixes broken JSON from LLMs — 13 repair strategies, zero dependencies on any LLM provider`

**Body:**

If you've built anything with LLMs that expects JSON back, you know the pain. They wrap it in markdown fences. They use single quotes. They add trailing commas. They output Python `True` instead of `true`. They hit the token limit and give you truncated JSON. They add "Here's the JSON you requested!" before and after.

I got tired of writing the same `try/except json.loads` + regex cleanup in every project, so I built **outputguard**.

```python
import outputguard

# LLM gave you this mess:
llm_output = """```json
{name: 'Alice', age: 30, active: True,}
```"""

# One line to fix it:
data = outputguard.parse(llm_output, schema)
# → {'name': 'Alice', 'age': 30, 'active': True}
```

It handles 13 different failure modes I've collected from real LLM outputs:

- Markdown code fences
- Commentary text before/after JSON
- JS-style comments inside JSON
- Trailing commas
- Single quotes instead of double
- Unquoted object keys
- `NaN`, `Infinity`, `undefined`
- Python `True`/`False`/`None`
- Truncated JSON (token limit cutoffs)
- `...` placeholders
- Malformed Unicode escapes
- Missing closing braces/brackets
- Unescaped newlines in strings

It also validates against JSON Schema, generates retry prompts you can send back to the LLM, and has a CLI with `--verbose` mode that shows you exactly what each strategy changed:

```
$ echo '{name: \"Alice\", age: 30,}' | outputguard repair - --verbose
⚠ Repaired  strategies: fix_commas, fix_keys

=== fix_commas ===
- {name: "Alice", age: 30,}
+ {name: "Alice", age: 30}

=== fix_keys ===
- {name: "Alice", age: 30}
+ {"name": "Alice", "age": 30}

Confidence: 72%
```

**Why not just use `json.loads` with some regex?** You can, and I did for a year. But the edge cases compound — single quotes with apostrophes inside, comments that look like URLs, braces inside string values. Each strategy handles these correctly.

Pure Python, 3 runtime deps (click, jsonschema, rich), works with any LLM provider. MIT licensed.

- GitHub: https://github.com/ndcorder/outputguard
- `pip install outputguard`

Happy to answer questions about the implementation. The repair strategies are each their own module if you want to look at how they work.

---

### r/LocalLLaMA

**Title:** `outputguard — automatically fixes broken JSON from local models (13 repair strategies for common failures)`

**Body:**

Local models are especially bad at producing valid JSON. Even with grammar-constrained generation, you still get trailing commas, Python-style booleans, truncated output from context limits, and markdown fences.

I built a Python library that catches and repairs all of these automatically:

```python
import outputguard

# Your local model returned this:
llm_output = "{name: 'Alice', age: 30, active: True,}"

# Fix and validate in one call:
data = outputguard.parse(llm_output, your_schema)
```

13 repair strategies, runs in <1ms, works offline, no API calls. Especially useful if you're building agents or tool-calling workflows where the model needs to return structured data.

Also has retry prompt generation — if repair isn't enough, it generates a correction prompt you can feed back to the model with specific error details.

`pip install outputguard` | https://github.com/ndcorder/outputguard

---

### r/ChatGPTCoding / r/ClaudeAI

**Title:** `Stop fighting with broken JSON from LLMs — outputguard fixes it automatically`

**Body:**

Quick share — I built a Python library that handles the "LLM returned garbage JSON" problem.

You know when ChatGPT/Claude wraps JSON in markdown fences, adds helpful commentary around it, uses single quotes, or just truncates mid-output? This fixes all of that:

```python
import outputguard

result = outputguard.validate_and_repair(llm_output, schema)
if result.valid:
    print(result.data)  # clean, validated dict
    print(result.strategies_applied)  # what it fixed
```

13 different repair strategies, JSON Schema validation, and if repair isn't enough, it generates a retry prompt you can send back to the model.

https://github.com/ndcorder/outputguard

---

### r/ExperiencedDevs or r/programming

**Title:** `outputguard: a repair pipeline for LLM JSON output (13 strategies, schema validation, retry prompts)`

**Body:**

Structured output from LLMs is unreliable. Even with system prompts demanding "return only valid JSON," models produce markdown fences, trailing commas, JavaScript literals, Python-style booleans, and truncated output.

I built outputguard — a repair pipeline that applies 13 strategies in order, validates against JSON Schema, and optionally generates correction prompts for retry loops.

The architecture is intentionally simple: each strategy is a pure `str → str` function, applied in sequence. The repairer tries all strategies first, then falls back to one-at-a-time with parse attempts between each. There's a `RepairReport` that gives you diffs and a confidence score.

The interesting engineering decisions:
- Strategies must be string-safe (e.g., `remove_comments` can't strip `://` from URLs inside strings, `fix_values` can't replace `NaN` inside string values)
- `fix_truncated` handles the "ran out of tokens" case by closing open strings, completing partial key-value pairs, and balancing braces
- The CLI `--verbose` mode shows each strategy's diff — useful for debugging why a particular repair succeeded or failed

3 dependencies (click, jsonschema, rich). 162 tests. MIT.

https://github.com/ndcorder/outputguard

---

## Hacker News

**Title:** `Show HN: Outputguard – Fix broken JSON from LLMs (13 repair strategies)`

**URL:** `https://github.com/ndcorder/outputguard`

**Top comment (post immediately after submitting):**

Hi HN, I built this because every project I've worked on that uses LLMs for structured output eventually accumulates the same pile of JSON-fixing regexes.

The core idea: apply a pipeline of repair strategies (strip markdown fences → extract JSON from commentary → remove JS comments → fix trailing commas → fix quotes → quote keys → fix JS values → fix Python booleans → handle truncation → fix ellipsis placeholders → fix Unicode escapes → balance braces → escape newlines), validate against JSON Schema, and optionally generate a retry prompt.

Each strategy is a standalone module with a simple `apply(text: str) -> str` interface. The tricky parts were making them string-aware — you can't just regex-replace `NaN` if it appears inside a string value like `"NaN means Not a Number"`.

Works with any LLM provider, no vendor dependencies. 162 tests, runs in <1ms.

---

## Twitter/X

### Launch tweet

```
Just released outputguard — a Python library that fixes broken JSON from LLMs.

13 repair strategies for the stuff LLMs actually do:
→ markdown fences
→ trailing commas
→ Python True/False/None
→ truncated output
→ commentary text
→ unquoted keys
→ and 7 more

One line: data = outputguard.parse(llm_output, schema)

pip install outputguard
https://github.com/ndcorder/outputguard
```

### Follow-up thread

```
The --verbose CLI mode shows exactly what each strategy changed:

[screenshot of the verbose output]

Useful for debugging why a repair succeeded or failed.
```

```
My favorite feature: retry prompt generation.

If repair isn't enough, outputguard generates a correction prompt with specific error details you can send back to the LLM.

The LLM gets told exactly what's wrong + what the schema expects.
```

```
162 tests. 3 dependencies. <1ms repair time. MIT licensed.

Works with OpenAI, Anthropic, local models, or anything that produces text.
```

---

## LinkedIn

```
I just open-sourced outputguard — a Python library that solves a problem every AI developer hits: broken JSON from LLMs.

When you ask an LLM to return structured JSON, you get:
• Markdown code fences wrapped around it
• Single quotes instead of double quotes
• Python True/False instead of JSON true/false
• Trailing commas
• Helpful commentary before and after the JSON
• Truncated output when the model hits token limits

outputguard automatically detects and repairs all of these (13 strategies total), validates against your JSON Schema, and generates retry prompts when repair isn't enough.

One line to go from broken LLM output to clean, validated data:

data = outputguard.parse(llm_output, schema)

It's provider-agnostic (works with OpenAI, Anthropic, local models), has 162 tests, and runs in under a millisecond.

If you're building AI applications that need reliable structured output, check it out:
https://github.com/ndcorder/outputguard

pip install outputguard

#Python #AI #LLM #OpenSource #DeveloperTools
```

---

## Dev.to / Hashnode blog post

**Title:** `I Fixed the "LLMs Can't Return Valid JSON" Problem — Here's How`

**Outline:**

1. **The problem** (2 paragraphs) — Every AI app needs structured output. LLMs are terrible at it. Show 5-6 real examples of broken JSON from different models.

2. **The naive solution** (1 paragraph) — `try/except json.loads` + growing pile of regexes. Works until it doesn't.

3. **The outputguard approach** (2 paragraphs) — Pipeline of 13 repair strategies, each handling one failure mode. Show the architecture diagram: strategies are composable `str → str` functions.

4. **Code walkthrough** (3 examples)
   - Basic: `parse()` one-liner
   - Intermediate: `validate_and_repair()` with strategy inspection
   - Advanced: retry loop with prompt generation

5. **The hard parts** (2 paragraphs) — String awareness (can't replace tokens inside JSON strings), truncation recovery (closing open strings + partial values), strategy ordering.

6. **Results** — Before/after table. "Here's what 8 real LLM outputs looked like, and what outputguard did with them" (use the batch_processing.py example output).

7. **Try it** — `pip install outputguard`, link to GitHub.

---

## Where to post (priority order)

| Platform | Subreddit/Section | When | Notes |
|---|---|---|---|
| Reddit | r/Python | Day 1 | Largest Python community. Post as "Show r/Python". |
| Hacker News | Show HN | Day 1 | Post the GitHub URL. Comment immediately with context. |
| Reddit | r/LocalLLaMA | Day 1-2 | Very active, loves tools for local models. |
| Twitter/X | Your account | Day 1 | Thread format. Tag #Python #AI #LLM. |
| Reddit | r/MachineLearning | Day 2-3 | Post as [P] project tag. More academic audience. |
| LinkedIn | Your profile | Day 1-2 | Professional audience. |
| Reddit | r/ChatGPTCoding | Day 2-3 | Practical coding audience. |
| Dev.to | Blog post | Day 3-5 | Longer-form content, good for SEO. |
| Reddit | r/artificial | Day 3-5 | Broader AI audience. |
| Reddit | r/OpenSource | Day 3-5 | OSS-focused community. |

**Timing tips:**
- Post on Tuesday-Thursday, 9-11am EST (peak Reddit/HN traffic)
- Don't post everywhere on the same day — spread over a week
- Engage with every comment. Answer questions thoroughly.
- If HN gets traction, don't post Reddit the same day (split your attention)

**What NOT to do:**
- Don't use marketing language ("revolutionary", "game-changing")
- Don't compare to paid products
- Don't post and disappear — respond to every comment
- Don't astroturf or ask friends to upvote
- Don't cross-post the exact same text

---

## Demo GIF / Screenshot

The single most impactful thing for social posts is a terminal screenshot or GIF showing the `--verbose` repair output. Run this and capture it with a tool like [vhs](https://github.com/charmbracelet/vhs) or just a screenshot:

```bash
echo '{name: '"'"'Alice'"'"', age: 30, active: True,}' | outputguard repair - --verbose
```

This produces colorized output showing each strategy's diff — it's visually compelling and immediately communicates what the tool does.

For Reddit, a terminal screenshot in the post body gets 2-3x more engagement than text-only.

---

## Responding to common objections

**"Why not just use Pydantic + instructor?"**
> Instructor is great if you're using OpenAI's API. outputguard works at a different layer — it fixes the raw text before parsing, works with any provider (including local models), and doesn't require you to change your LLM client. They're complementary, not competing.

**"Just use structured output / function calling"**
> Structured output modes help a lot but aren't available everywhere (local models, older APIs), don't prevent truncation, and some models still break the schema. outputguard is the safety net for when the LLM doesn't cooperate.

**"I just use a try/except with some regex"**
> That works until you hit apostrophes in single-quoted strings, URLs in comment-stripped JSON, or braces inside string values. Each of these is a 30-minute debugging session. outputguard has 162 tests for these edge cases.

**"Seems over-engineered for a simple problem"**
> The API is one function: `data = outputguard.parse(text, schema)`. The complexity is behind the scenes. You don't need to know about the 13 strategies unless you want to.
