"""Replace single-quoted strings with double-quoted in JSON-like text."""

NAME = "fix_quotes"


def apply(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Double-quoted string — pass through unchanged
        if ch == '"':
            result.append(ch)
            i += 1
            while i < n:
                c = text[i]
                result.append(c)
                if c == "\\" and i + 1 < n:
                    result.append(text[i + 1])
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    break
                i += 1
            continue

        # Single-quoted string — convert to double-quoted
        if ch == "'":
            # Collect the content of the single-quoted string
            content: list[str] = []
            i += 1
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n and text[i + 1] == "'":
                    # Escaped single quote → emit unescaped
                    content.append("'")
                    i += 2
                    continue
                if c == "'":
                    i += 1
                    break
                content.append(c)
                i += 1

            # Escape any double quotes that were inside the single-quoted string
            inner = "".join(content)
            inner = inner.replace('"', '\\"')
            result.append('"')
            result.append(inner)
            result.append('"')
            continue

        result.append(ch)
        i += 1

    return "".join(result)
