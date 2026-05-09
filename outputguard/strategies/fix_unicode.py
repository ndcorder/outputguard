"""Fix malformed Unicode escape sequences."""

import re

NAME = "fix_unicode"
DESCRIPTION = "Fix malformed Unicode escape sequences"


def _fix_string_content(s: str) -> str:
    """Fix escape sequences inside a JSON string body (without quotes)."""
    result: list[str] = []
    i = 0
    n = len(s)

    while i < n:
        if s[i] != "\\":
            result.append(s[i])
            i += 1
            continue

        # We have a backslash
        if i + 1 >= n:
            result.append(s[i])
            i += 1
            continue

        next_ch = s[i + 1]

        # \uXXXX — Unicode escape
        if next_ch == "u":
            # Grab whatever hex digits follow (up to 4)
            hex_start = i + 2
            hex_chars = []
            for j in range(hex_start, min(hex_start + 4, n)):
                if s[j] in "0123456789abcdefABCDEF":
                    hex_chars.append(s[j])
                else:
                    break

            if len(hex_chars) == 4:
                # Valid \uXXXX — keep as-is
                result.append(s[i : i + 6])
                i += 6
            elif len(hex_chars) == 0:
                # \uGGGG — no valid hex digits at all; remove escape
                # Skip \u and up to 4 following non-hex chars that look
                # like they were meant to be the escape
                i += 2
                skip = 0
                while skip < 4 and i < n and s[i] not in '"\\' and not s[i].isspace():
                    if s[i] in "0123456789abcdefABCDEF":
                        break
                    i += 1
                    skip += 1
            else:
                # Incomplete hex (1-3 digits) — pad to 4 with leading zeros
                padded = hex_chars[0:]
                while len(padded) < 4:
                    padded.insert(0, "0")
                result.append("\\u" + "".join(padded))
                i = hex_start + len(hex_chars)
        elif next_ch == "x":
            # \xNN — Python-style hex escape (not valid JSON)
            hex_start = i + 2
            hex_chars = []
            for j in range(hex_start, min(hex_start + 2, n)):
                if s[j] in "0123456789abcdefABCDEF":
                    hex_chars.append(s[j])
                else:
                    break
            if len(hex_chars) == 2:
                char = chr(int("".join(hex_chars), 16))
                result.append(char)
                i = hex_start + 2
            else:
                # Malformed \x — just remove it
                result.append(s[i])
                i += 1
        elif next_ch == "0":
            # \0 null byte — remove it
            i += 2
        else:
            # Some other valid escape (\n, \t, \", \\, etc.) — keep
            result.append(s[i : i + 2])
            i += 2

    return "".join(result)


def apply(text: str) -> str:
    try:
        result: list[str] = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            if ch != '"':
                result.append(ch)
                i += 1
                continue

            # Opening quote of a string
            result.append(ch)
            i += 1

            # Collect string content
            string_content: list[str] = []
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    string_content.append(c)
                    string_content.append(text[i + 1])
                    i += 2
                    continue
                if c == '"':
                    break
                string_content.append(c)
                i += 1

            # Fix the content
            fixed = _fix_string_content("".join(string_content))
            result.append(fixed)

            # Closing quote
            if i < n:
                result.append(text[i])  # the "
                i += 1

        return "".join(result)
    except Exception:
        return text
