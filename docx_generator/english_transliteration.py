"""
Transliterate ASCII (English) letter runs inside a designation string into
Bangla Unicode letter-names, so that acronyms like "RMM" become "আরএমএম"
instead of being passed through the Bijoy converter as Latin glyphs.

Bijoy's Unicode->Bijoy converter only handles Bangla Unicode codepoints;
Latin characters pass through unchanged and render in the Latin fallback
font on the log sheet, which the user doesn't want.

Strategy: scan the input for runs of ASCII letters and replace each run
with the concatenated Bangla letter-name for each character. Non-letter
characters (spaces, digits, punctuation, Bangla text) are preserved as-is
so the downstream Bijoy converter still works for mixed strings like
"RMM সাহেব".
"""

import re

# Per-letter Bangla pronunciation (uppercase keys; lowercase is folded in).
LETTER_BN = {
    "A": "এ",
    "B": "বি",
    "C": "সি",
    "D": "ডি",
    "E": "ই",
    "F": "এফ",
    "G": "জি",
    "H": "এইচ",
    "I": "আই",
    "J": "জে",
    "K": "কে",
    "L": "এল",
    "M": "এম",
    "N": "এন",
    "O": "ও",
    "P": "পি",
    "Q": "কিউ",
    "R": "আর",
    "S": "এস",
    "T": "টি",
    "U": "ইউ",
    "V": "ভি",
    "W": "ডব্লিউ",
    "X": "এক্স",
    "Y": "ওয়াই",
    "Z": "জেড",
}

# Common multi-letter words/titles that should NOT be spelled letter-by-letter.
# Add to this dict over time as new cases appear. Keys are uppercase.
WORD_BN = {
    "MR": "মি",
    "MRS": "মিসেস",
    "MS": "মিস",
    "DR": "ড",
    "SIR": "স্যার",
}

_LATIN_RUN = re.compile(r"[A-Za-z]+")


def transliterate_english_to_bangla(text: str) -> str:
    """Replace every ASCII letter run in *text* with its Bangla spelling.

    Whole-word overrides in WORD_BN win; otherwise each letter is mapped
    via LETTER_BN. Unknown characters (shouldn't happen for [A-Za-z]) are
    dropped silently.
    """
    if not text:
        return text

    def _replace(match: "re.Match[str]") -> str:
        token = match.group(0).upper()
        if token in WORD_BN:
            return WORD_BN[token]
        return "".join(LETTER_BN.get(ch, "") for ch in token)

    return _LATIN_RUN.sub(_replace, text)
