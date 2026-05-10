"""Fix GPT-2 byte-pair encoding artifacts in model output."""

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


def apply(text: str) -> str:
    if not any(c in text for c in _BPE_MAP):
        return text
    for bpe_char, replacement in _BPE_MAP.items():
        text = text.replace(bpe_char, replacement)
    return text
