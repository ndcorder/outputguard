"""Fix GPT-2 byte-pair encoding artifacts in model output."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_encoding"
DESCRIPTION = "Fix BPE tokenizer artifacts (raw byte tokens as Unicode)"

# GPT-2 BPE uses these Unicode characters as byte representations.
# Some model APIs serve them raw instead of decoding.
_BPE_MAP = {
    "Ġ": " ",  # Ġ → space
    "Ċ": "\n",  # Ċ → newline
    "ĉ": "\t",  # ĉ → tab
    "č": "\r",  # č → carriage return
}
_EVENT = re.compile(r"""["'/ĠĊĉč]""")


def apply(text: str) -> str:
    if not any(c in text for c in _BPE_MAP):
        return text
    # Literal Unicode alone is not evidence of an encoded document.
    index = 0
    while event := _EVENT.search(text, index):
        index = event.start()
        char = text[index]
        if char in "\"'":
            index = quoted_end(text, index)
        elif char == "/" and index + 1 < len(text) and text[index + 1] in "/*":
            index = comment_end(text, index)
        elif char in _BPE_MAP:
            for bpe_char, replacement in _BPE_MAP.items():
                text = text.replace(bpe_char, replacement)
            return text
        else:
            index += 1
    return text
