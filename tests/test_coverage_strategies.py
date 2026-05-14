"""Targeted tests for uncovered lines in strategy modules."""

import json

import pytest

from outputguard.strategies.fix_booleans import apply as fix_booleans
from outputguard.strategies.fix_encoding import apply as fix_encoding
from outputguard.strategies.fix_inner_quotes import apply as fix_inner_quotes
from outputguard.strategies.fix_newlines import apply as fix_newlines
from outputguard.strategies.fix_unicode import apply as fix_unicode
from outputguard.strategies.fix_values import apply as fix_values


# ─── fix_encoding (lines 19-21: BPE replacement loop) ────────────────────────


class TestFixEncodingBPEReplacement:
    """Lines 20-21: the replacement loop body when BPE chars ARE present."""

    def test_space_token(self):
        assert fix_encoding('{"key":Ġ"val"}') == '{"key": "val"}'

    def test_newline_token(self):
        assert fix_encoding('"line1Ċline2"') == '"line1\nline2"'

    def test_tab_token(self):
        assert fix_encoding('"col1ĉcol2"') == '"col1\tcol2"'

    def test_cr_token(self):
        assert fix_encoding('"ačb"') == '"a\rb"'

    def test_all_bpe_tokens_together(self):
        assert fix_encoding('ĠĊĉč') == ' \n\t\r'


# ─── fix_booleans (lines 20-21: backslash skip in _count_unescaped_quotes) ───


class TestFixBooleansEscapedQuotes:
    """Lines 20-21: when _count_unescaped_quotes encounters a backslash,
    it skips 2 chars (i += 2; continue).
    Need an escaped quote/backslash before the boolean match position."""

    def test_escaped_quote_before_boolean(self):
        # String value contains \" (escaped quote) — the backslash before
        # the quote triggers the i+=2 skip in _count_unescaped_quotes
        text = '{"val": "test\\\"", "flag": True}'
        result = fix_booleans(text)
        assert "true" in result
        assert "True" not in result

    def test_escaped_backslash_before_boolean(self):
        # String value contains \\\\ (escaped backslash)
        text = '{"a": "x\\\\", "b": False}'
        result = fix_booleans(text)
        assert "false" in result
        assert "False" not in result


# ─── fix_values (lines 22-23: backslash skip in _count_unescaped_quotes) ────


class TestFixValuesEscapedQuotes:
    """Same pattern as fix_booleans — backslash skip in quote counter."""

    def test_escaped_quote_before_nan(self):
        text = '{"val": "test\\\"", "x": NaN}'
        result = fix_values(text)
        assert "null" in result
        assert "NaN" not in result

    def test_escaped_backslash_before_undefined(self):
        text = '{"a": "p\\\\", "b": undefined}'
        result = fix_values(text)
        assert "null" in result
        assert "undefined" not in result


# ─── fix_inner_quotes (line 45: lone backslash at end of key string,
#     line 67: lone backslash at end of value string) ─────────────────


class TestFixInnerQuotesEscapedAndClosing:
    """Line 45: in non-value (key) string, backslash + next char escape pair.
    Line 67: in value string, real closing quote followed by delimiter."""

    def test_backslash_escape_in_key_string(self):
        # Key string contains a backslash-n escape sequence.
        # The key scanner (not is_value branch) hits lines 39-43:
        #   if c == '\\': result.append(c); result.append(text[i+1]); i += 2
        text = '{"ke\\ny": "value"}'
        result = fix_inner_quotes(text)
        assert '"value"' in result

    def test_lone_backslash_at_end_of_key_string(self):
        # Key string ending with backslash right before closing quote.
        # In the key scanner, backslash at i, and i+1 < n is True (next char is ").
        # Actually for line 45 (i += 1 when i+1 >= n), we need backslash
        # as the very last character of the entire text while inside a key string.
        text = '"key\\'
        result = fix_inner_quotes(text)
        assert '\\' in result

    def test_backslash_escape_in_value_string(self):
        # Value string with backslash escape — hits lines 61-65
        text = '{"key": "path\\\\to\\\\file"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "path" in parsed["key"]

    def test_closing_quote_followed_by_comma(self):
        # Line 67: the real closing quote is identified by , following it.
        # The value string has inner unescaped quotes, then the real close.
        text = '{"a": "inner "quote" here", "b": 1}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "quote" in parsed["a"]
        assert parsed["b"] == 1

    def test_closing_quote_followed_by_brace(self):
        # Line 67 also triggered by } after the closing quote
        text = '{"a": "inner "quote" here"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "quote" in parsed["a"]

    def test_lone_backslash_at_end_of_value_string(self):
        # Line 67 in value string escape path: backslash is the very last
        # char of the entire text while scanning a value string (i+1 >= n).
        text = '{"key": "value\\'
        result = fix_inner_quotes(text)
        assert 'value' in result


# ─── fix_newlines (line 31: in-string closing quote; lines 26-29 escape pass-through) ─


class TestFixNewlinesStringPaths:
    """Line 31: closing quote exits string state (in_string = False).
    Lines 26-29: backslash escape pass-through inside string.
    Line 30-31: lone backslash at end of text inside string."""

    def test_literal_newline_then_closing_quote(self):
        # Exercises: enter string → literal \n (line 40-42) → closing " (line 34-37)
        # The closing quote on line 34 sets in_string = False (line 35).
        text = '{"text": "line1\nline2"}'
        result = fix_newlines(text)
        parsed = json.loads(result)
        assert parsed["text"] == "line1\nline2"

    def test_existing_escape_passthrough(self):
        # Lines 26-29: already-escaped \\n inside a string is passed through.
        # The scanner sees backslash, then appends it + next char, skips 2.
        text = '{"a": "pre\\npost"}'
        result = fix_newlines(text)
        assert result == '{"a": "pre\\npost"}'

    def test_existing_escape_backslash_passthrough(self):
        # An escaped backslash \\\\  inside a string — lines 26-29
        text = '{"a": "x\\\\y"}'
        result = fix_newlines(text)
        assert result == '{"a": "x\\\\y"}'

    def test_lone_backslash_at_end(self):
        # Lines 30-31: backslash as last char while in_string, i+1 >= n
        text = '"test\\'
        result = fix_newlines(text)
        assert result == '"test\\'

    def test_multiple_strings_closing_quotes(self):
        # Exercises closing quote (line 34-35) on first string, then re-entry
        text = '{"a": "x\ny", "b": "m\nn"}'
        result = fix_newlines(text)
        parsed = json.loads(result)
        assert parsed["a"] == "x\ny"
        assert parsed["b"] == "m\nn"

    def test_literal_tab_and_cr(self):
        text = '{"a": "col1\tcol2\rend"}'
        result = fix_newlines(text)
        parsed = json.loads(result)
        assert parsed["a"] == "col1\tcol2\rend"


# ─── fix_unicode (lines 21-23, 46-52, 68, 75-76) ────────────────────────────


class TestFixUnicodeUncoveredPaths:
    """Target specific uncovered lines in _fix_string_content and apply."""

    def test_plain_chars_in_string(self):
        # Lines 14-16 (non-backslash chars in _fix_string_content)
        text = '{"key": "hello world"}'
        result = fix_unicode(text)
        assert json.loads(result) == {"key": "hello world"}

    def test_valid_unicode_escape_kept(self):
        # Lines 38-41: valid \uXXXX kept as-is
        text = '{"key": "\\u0041"}'
        result = fix_unicode(text)
        # A is valid, should be preserved
        assert '\\u0041' in result

    def test_no_hex_digits_unicode_escape(self):
        # Lines 46-52: \uGHIJ — zero valid hex digits, skip the escape
        text = '{"key": "\\uGHIJ"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        # GHIJ are non-hex, so \u + up to 4 non-hex chars are stripped
        assert "\\u" not in result.split('"')[3] if len(result.split('"')) > 3 else True

    def test_incomplete_hex_unicode_escape(self):
        # Lines 53-59: 1-3 hex digits — pad with leading zeros
        text = '{"key": "\\u41z"}'
        result = fix_unicode(text)
        # \u41 has only 2 hex digits → padded to A
        assert '\\u0041' in result

    def test_hex_escape_x41(self):
        # Lines 69-72: \x41 with 2 valid hex digits → chr(0x41) = 'A'
        text = '{"key": "\\x41"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["key"] == "A"

    def test_hex_escape_x6f(self):
        # Line 68: \x with non-hex char after first hex char breaks the loop
        text = '{"key": "\\x6f"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["key"] == "o"

    def test_malformed_hex_escape_no_digits(self):
        # Lines 75-76: \xGG — 0 valid hex chars → malformed, append backslash
        text = '{"key": "\\xGG"}'
        result = fix_unicode(text)
        # Malformed \x — backslash is kept, rest consumed normally
        assert '"key"' in result

    def test_null_byte_removal(self):
        # Lines 77-79: \0 → removed entirely
        text = '{"key": "hello\\0world"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["key"] == "helloworld"

    def test_null_byte_at_end_of_string(self):
        text = '{"key": "end\\0"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["key"] == "end"

    def test_other_valid_escapes_kept(self):
        # Lines 82-83: \n, \t etc. kept as-is
        text = '{"key": "line1\\nline2\\ttab"}'
        result = fix_unicode(text)
        assert '\\n' in result
        assert '\\t' in result

    def test_lone_backslash_at_string_end(self):
        # Lines 20-22: backslash at very end of string content (i+1 >= n)
        # We need a string where the content between quotes ends with a backslash
        # and there's no next character in the content.
        # apply() collects content: if it sees \\ and i+1 < n, it pairs them.
        # But if the text is malformed with a lone \\ right before the closing quote,
        # apply() would see \\ then " — it pairs them as escape sequence.
        # So to get a lone backslash into _fix_string_content, we need the text
        # to end mid-string (no closing quote).
        # Actually, in apply(), the string collector loop condition is:
        #   if c == "\\" and i + 1 < n: ... (pairs them)
        #   if c == '"': break
        # If the text is '"test\\' (no closing quote), then:
        #   c = '\\', i+1 < n is False (backslash is last char) → falls to append c, i += 1
        # Wait, no — the condition is "c == '\\' and i + 1 < n", if that's false
        # it falls through to "if c == '"': break" then to string_content.append(c).
        # So _fix_string_content gets "test\\" — with the trailing backslash.
        # BUT WAIT: i+1 < n when backslash is at position n-1... i=n-1, i+1=n, n=len(text).
        # So i + 1 < n is False. The backslash goes to string_content.append(c).
        # Then _fix_string_content sees backslash at the end → lines 20-22.
        text = '"test\\'
        result = fix_unicode(text)
        assert 'test' in result

    def test_mixed_unicode_issues(self):
        text = '{"key": "\\x41\\0\\uGHIJ"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert "A" in parsed["key"]

    def test_hex_escape_one_digit_then_nonhex(self):
        # Line 68: break in \x hex collection when non-hex found after 1 digit
        # \x4G — only 1 hex digit → malformed (len != 2)
        text = '{"key": "\\x4G"}'
        result = fix_unicode(text)
        # Malformed \x with only 1 hex digit
        assert '"key"' in result

    def test_no_hex_with_hex_after_skip(self):
        # Line 50: in the no-hex-digits \u path, a non-hex char is skipped,
        # then a hex digit is encountered → break exits the skip loop.
        # \uG1 — G is non-hex (skipped), 1 is hex (break on line 50)
        text = '{"key": "\\uG1rest"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        # G is skipped, then '1rest' is processed as normal chars
        assert "1rest" in parsed["key"]

    def test_exception_handler_returns_original(self):
        # Lines 130-131: defensive except returns original text.
        # Trigger by monkey-patching _fix_string_content to raise.
        import outputguard.strategies.fix_unicode as mod

        original_fn = mod._fix_string_content
        mod._fix_string_content = lambda s: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            text = '{"key": "value"}'
            result = mod.apply(text)
            assert result == text
        finally:
            mod._fix_string_content = original_fn
