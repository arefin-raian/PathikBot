"""
Unicode to Bijoy converter ported from bangla.plus fontconverter.min.js.
"""
import re


_UNI2BIJOY_MAP = {
    "\u0964": "|",
    "\u2018": "\u00d4",
    "\u2019": "\u00d5",
    "\u201c": "\u00d2",
    "\u201d": "\u00d3",
    "\u09cd\u09b0\u09cd\u09af": "\u00aa\u00a8",
    "\u09b0\u200c\u09cd\u09af": "i\u00a8",
    "\u0995\u09cd\u0995": "\u00b0",
    "\u0995\u09cd\u099f": "\u00b1",
    "\u0995\u09cd\u09a4": "\u00b3",
    "\u0995\u09cd\u09ac": "K\u00a1",
    "\u09b8\u09cd\u0995\u09cd\u09b0": "\u00af\u0152",
    "\u0995\u09cd\u09b0": "\u00b5",
    "\u0995\u09cd\u09b2": "K\u00ac",
    "\u0995\u09cd\u09b7\u09cd\u09a8": "\u00b6\u00e8",
    "\u0995\u09cd\u09b7\u09cd\u09a3": "\u00b6\u00e8",
    "\u09b9\u09cd\u09ae": "\u00fe",
    "\u0995\u09cd\u09b7\u09cd\u09ae": "\u00b2",
    "\u0999\u09cd\u0995\u09cd\u09b7": "\u2022\u00b6",
    "\u0995\u09cd\u09b7": "\u00b6",
    "\u0995\u09cd\u09b8": "\u00b7",
    "\u0995\u09cd\u09ae": "\u00b4",
    "\u0999\u09cd\u0997\u09c1": "\u00bdy",
    "\u0997\u09c1": "\u00b8",
    "\u0997\u09cd\u09a7": "\u00bb",
    "\u0997\u09cd\u09a8": "M\u0153",
    "\u0997\u09cd\u09ae": "M\u00a5",
    "\u0997\u09cd\u09b2\u09c1": "M\u00f8\u00e6",
    "\u0997\u09cd\u09b2": "M\u00f8",
    "\u0997\u09cd\u09b0\u09c1": "M\u00aa\u00e6",
    "\u0998\u09cd\u09a8": "N\u0153",
    "\u0999\u09cd\u0995": "\u00bc",
    "\u0999\u09cd\u0996": "\u2022L",
    "\u0999\u09cd\u0997": "\u00bd",
    "\u0999\u09cd\u0998": "\u2022N",
    "\u099a\u09cd\u099a": "\u201dP",
    "\u099a\u09cd\u099b": "\u201dQ",
    "\u099a\u09cd\u099b\u09cd\u09ac": "\u201dQ\u00a1",
    "\u099a\u09cd\u099e": "\u201dT",
    "\u099c\u09cd\u099c\u09cd\u09ac": "\u00be\u00a1",
    "\u099c\u09cd\u099c": "\u00be",
    "\u099c\u09cd\u099d": "\u00c0",
    "\u099c\u09cd\u099e": "\u00c1",
    "\u099c\u09cd\u09ac": "R\u00a1",
    "\u099e\u09cd\u099a": "\u00c2",
    "\u099e\u09cd\u099b": "\u00c3",
    "\u099e\u09cd\u099c": "\u00c4",
    "\u099e\u09cd\u099d": "\u00c5",
    "\u099f\u09cd\u099f": "\u00c6",
    "\u099f\u09cd\u09ac": "U\u00a1",
    "\u099f\u09cd\u09ae": "U\u00a5",
    "\u09a1\u09cd\u09a1": "\u00c7",
    "\u09a3\u09cd\u099f": "\u00c8",
    "\u09a3\u09cd\u09a0": "\u00c9",
    "\u09a8\u09cd\u09b8": "\u00dd",
    "\u09a3\u09cd\u09a1": "\u00d0",
    "\u09a8\u09cd\u09a4\u09c1": "\u0161\u2018",
    "\u09a3\u09cd\u09ac": "Y^",
    "\u09a4\u09cd\u09a4\u09cd\u09ac": "\u00cb\u00a1",
    "\u09a8\u09cd\u09a4\u09cd\u09ac": "\u0161\u00cd\u00a1",
    "\u09a4\u09cd\u09a4": "\u00cb",
    "\u09a4\u09cd\u09a5": "\u00cc",
    "\u09a4\u09cd\u09a8": "Z\u0153",
    "\u09a4\u09cd\u09ae": "Z\u00a5",
    "\u09a4\u09cd\u09ac": "Z\u00a1",
    "\u09a4\u09cd\u09b0\u09c1": "\u00ce\u00e6",
    "\u09a4\u09cd\u09b0\u09c2": "\u00ce\u0192",
    "\u09a5\u09cd\u09ac": "_\u00a1",
    "\u09a6\u09cd\u0997": "\u02dcM",
    "\u09a6\u09cd\u0998": "\u02dcN",
    "\u09a6\u09cd\u09a6": "\u00cf",
    "\u09a6\u09cd\u09a7": "\u00d7",
    "\u09a8\u09cd\u09a6\u09cd\u09ac": "\u203a\u00d8",
    "\u09a6\u09cd\u09ac": "\u00d8",
    "\u09a6\u09cd\u09ad\u09cd\u09b0": "\u2122\u00a3",
    "\u09a6\u09cd\u09ad": "\u2122\u00a2",
    "\u09a6\u09cd\u09ae": "\u00d9",
    "\u09a6\u09cd\u09b0\u09c1": "`\u00aa\u00e6",
    "\u09b6\u09cd\u09b0\u09c1": "k\u00d6\u00e6",
    "\u09aa\u09cd\u09b0\u09c1": "c\u00d6\u00e6",
    "\u09aa\u09cd\u09b2\u09c1": "c\u00f8\u00e6",
    "\u09a7\u09cd\u09ac": "a\u0178",
    "\u09a7\u09cd\u09ae": "a\u00a5",
    "\u09a8\u09cd\u099f": "\u203aU",
    "\u09a8\u09cd\u09a0": "\u00da",
    "\u09a8\u09cd\u09a1": "\u00db",
    "\u09a8\u09cd\u09a4\u09cd\u09b0": "\u0161\u00bf",
    "\u09a8\u09cd\u09a4": "\u0161\u00cd",
    "\u09b8\u09cd\u09a4\u09cd\u09b0": "\u00af\u00bf",
    "\u09a4\u09cd\u09b0": "\u00ce",
    "\u09a8\u09cd\u09a5": "\u0161\u2019",
    "\u09a8\u09cd\u09a6": "\u203a`",
    "\u09a8\u09cd\u09a7": "\u00dc",
    "\u09a3\u09cd\u09a3": "Y\u0153",
    "\u09a3\u09cd\u09a8": "Y\u0153",
    "\u09a8\u09cd\u09a8": "b\u0153",
    "\u09a8\u09cd\u09ac": "\u0161^",
    "\u09a8\u09cd\u09ae": "b\u00a5",
    "\u09aa\u09cd\u099f": "\u00de",
    "\u09aa\u09cd\u09a4": "\u00df",
    "\u09aa\u09cd\u09a8": "c\u0153",
    "\u09aa\u09cd\u09aa": "\u00e0",
    "\u09aa\u09cd\u09b2": "c\u00f8",
    "\u09aa\u09cd\u09b8": "\u00e1",
    "\u09ab\u09cd\u09b2": "d\u00ac",
    "\u09ac\u09cd\u099c": "\u00e2",
    "\u09ac\u09cd\u09a6": "\u00e3",
    "\u09ac\u09cd\u09a7": "\u00e4",
    "\u09ac\u09cd\u09ac": "e\u0178",
    "\u09ac\u09cd\u09b2": "e\u00f8",
    "\u09ad\u09cd\u09b0": "\u00e5",
    "\u09ae\u09cd\u09a8": "g\u0153",
    "\u09ae\u09cd\u09aa": "\u00a4\u00fa",
    "\u09ae\u09cd\u09ab": "\u00e7",
    "\u09ae\u09cd\u09ac": "\u00a4^",
    "\u09ae\u09cd\u09ad": "\u00a4\u00a2",
    "\u09ae\u09cd\u09ad\u09cd\u09b0": "\u00a4\u00a3",
    "\u09ae\u09cd\u09ae": "\u00a4\u00a7",
    "\u09ae\u09cd\u09b2": "\u00a4\u00f8",
    "\u09dc\u09c1": "o\u2013",
    "\u09dd\u09c1": "p\u2013",
    "\u09b0\u09c1": "i\u00e6",
    "\u09b0\u09c2": "i\u0192",
    "\u09b2\u09cd\u0995": "\u00e9",
    "\u09b2\u09cd\u0997": "\u00ea",
    "\u09b2\u09cd\u09aa": "\u00ed",
    "\u09b2\u09cd\u099f": "\u00eb",
    "\u09b2\u09cd\u09a1": "\u00ec",
    "\u09b2\u09cd\u09ab": "\u00ee",
    "\u09b2\u09cd\u09ac": "j\u00a6",
    "\u09b2\u09cd\u09ae": "j\u00a5",
    "\u09b2\u09cd\u09b2": "j\u00f8",
    "\u09b6\u09c1": "\u00ef",
    "\u09b6\u09cd\u099a": "\u00f0",
    "\u09b6\u09cd\u099b": "\u00f1",
    "\u09b6\u09cd\u09a8": "k\u0153",
    "\u09b6\u09cd\u09ac": "k\u00a6",
    "\u09b6\u09cd\u09ae": "k\u00a5",
    "\u09b6\u09cd\u09b2": "k\u00f8",
    "\u09b7\u09cd\u0995": "\u00ae\u2039",
    "\u09b7\u09cd\u0995\u09cd\u09b0": "\u00ae\u0152",
    "\u09b7\u09cd\u099f": "\u00f3",
    "\u09b7\u09cd\u09a0": "\u00f4",
    "\u09b7\u09cd\u09a3": "\u00f2",
    "\u09b7\u09cd\u09aa": "\u00ae\u00fa",
    "\u09b7\u09cd\u09ab": "\u00f5",
    "\u09b7\u09cd\u09ae": "\u00ae\u00a7",
    "\u09b8\u09cd\u0995": "\u00af\u2039",
    "\u09b8\u09cd\u099f": "\u00f7",
    "\u09b8\u09cd\u0996": "\u00f6",
    "\u09b8\u09cd\u09a4\u09c1": "\u00af\u2018",
    "\u09b8\u09cd\u09a4": "\u00af\u00cd",
    "\u09b8\u09cd\u09a5": "\u00af\u2019",
    "\u09b8\u09cd\u09a8": "m\u0153",
    "\u09b8\u09cd\u09aa": "\u00af\u00fa",
    "\u09b8\u09cd\u09ab": "\u00f9",
    "\u09b8\u09cd\u09ac": "\u00af^",
    "\u09b8\u09cd\u09ae": "\u00af\u00a7",
    "\u09b8\u09cd\u09b2": "\u00af\u00f8",
    "\u09b9\u09cd\u09ac": "n\u0178",
    "\u09b9\u09c1": "\u00fb",
    "\u09b9\u09cd\u09a3": "n\u00e8",
    "\u09b9\u09cd\u09a8": "\u00fd",
    "\u09b9\u09cd\u09b2": "n\u00ac",
    "\u09b9\u09c3": "\u00fc",
    "\u09b0\u09cd": "\u00a9",
    "\u09cd\u09b0": "\u00aa",
    "\u09cd\u09af": "\u00a8",
    "\u09cd": "&",
    "\u0986": "Av",
    "\u0985": "A",
    "\u0987": "B",
    "\u0988": "C",
    "\u0989": "D",
    "\u098a": "E",
    "\u098b": "F",
    "\u098f": "G",
    "\u0990": "H",
    "\u0993": "I",
    "\u0994": "J",
    "\u0995": "K",
    "\u0996": "L",
    "\u0997": "M",
    "\u0998": "N",
    "\u0999": "O",
    "\u099a": "P",
    "\u099b": "Q",
    "\u099c": "R",
    "\u099d": "S",
    "\u099e": "T",
    "\u099f": "U",
    "\u09a0": "V",
    "\u09a1": "W",
    "\u09a2": "X",
    "\u09a3": "Y",
    "\u09a4": "Z",
    "\u09a5": "_",
    "\u09a6": "`",
    "\u09a7": "a",
    "\u09a8": "b",
    "\u09aa": "c",
    "\u09ab": "d",
    "\u09ac": "e",
    "\u09ad": "f",
    "\u09ae": "g",
    "\u09af": "h",
    "\u09b0": "i",
    "\u09b2": "j",
    "\u09b6": "k",
    "\u09b7": "l",
    "\u09b8": "m",
    "\u09b9": "n",
    "\u09dc": "o",
    "\u09dd": "p",
    "\u09df": "q",
    "\u09ce": "r",
    "\u09e6": "0",
    "\u09e7": "1",
    "\u09e8": "2",
    "\u09e9": "3",
    "\u09ea": "4",
    "\u09eb": "5",
    "\u09ec": "6",
    "\u09ed": "7",
    "\u09ee": "8",
    "\u09ef": "9",
    "\u09be": "v",
    "\u09bf": "w",
    "\u09c0": "x",
    "\u09c1": "y",
    "\u09c2": "~",
    "\u2026": "...",
    "\u09c3": "\u2026",
    "\u09c7": "\u2021",
    "\u09c8": "\u2030",
    "\u09d7": "\u0160",
    "\u0982": "s",
    "\u0983": "t",
    "\u0981": "u",
    "\u2014": "\u00d1",
    "\u0965": "\\",
}

_BIJOY_KAR_REPLACEMENTS = {
    "\u00a8y": "y\u00a8",
    "\u00a8~": "~\u00a8",
    "vu": "uv",
    "\u00a8u": "u\u00a8",
    "Ky": "Kz",
    "K~": "K\u201a",
    "Py": "Pz",
    "P~": "P\u201a",
    "Qy": "Qz",
    "Q~": "Q\u201a",
    "Sy": "Sz",
    "S~": "S\u201a",
    "Uy": "Uz",
    "U~": "U\u201a",
    "Vy": "Vz",
    "V~": "V\u201a",
    "Wy": "Wz",
    "W~": "W\u201a",
    "Xy": "Xz",
    "X~": "X\u201a",
    "Zy": "Zz",
    "Z~": "Z\u201a",
    "dy": "dz",
    "d~": "d\u201a",
    "fy": "fz",
    "f~": "f\u201a",
    "\u00b6y": "\u00b6z",
    "\u00b6~": "\u00b6\u201a",
    "\u00c1y": "\u00c1z",
    "\u00c1~": "\u00c1\u201a",
    "\u00fey": "\u00fez",
    "\u00fe~": "\u00fe\u201a",
    "\u00bey": "\u00bez",
    "\u00be~": "\u00be\u201a",
    "\u00b0y": "\u00b0z",
    "\u00b0~": "\u00b0\u201a",
    "\u00bcy": "\u00bcz",
    "\u00bc~": "\u00bc\u201a",
    "\u00dcy": "\u00dcz",
    "\u00dc~": "\u00dc\u201a",
    "\u00d7y": "\u00d7z",
    "\u00d7~": "x\u201a",
    "\u00e4y": "\u00e4z",
    "\u00e4~": "\u00e4\u201a",
    "\u00a7\u2026": "\u00a7\u201e",
    "\u00a5\u2026": "\u00a5\u201e",
    "c\u2026": "c\u201e",
    "N\u2026": "N\u201e",
    "g\u2026": "g\u201e",
    "e\u2026": "e\u201e",
    "k\u2026": "k\u201e",
    "L\u2026": "L\u201e",
    "M\u2026": "M\u201e",
    "m\u2026": "m\u201e",
    "l\u2026": "l\u201e",
    "R\u2026": "R\u201e",
    "_\u2026": "_\u201e",
    "`\u2026": "`\u201e",
    "a\u2026": "a\u201e",
    "b\u2026": "b\u201e",
    "j\u2026": "j\u201e",
    "h\u2026": "h\u201e",
    "Y\u2026": "Y\u201e",
    "j&\u00b8": "\u00eay",
    "'\u2021": "'\u2020",
    "\"\u2021": "\"\u2020",
    "{\u2021": "{\u2020",
    "-\u2021": "-\u2020",
    "'\u2030": "'\u02c6",
    "\"\u2030": "\"\u02c6",
    "{\u2030": "{\u02c6",
    "-\u2030": "-\u02c6",
    "\u00a9y": "\u00a9z",
    "\u00a9~": "\u00a9\u201a",
    "\u2039y": "\u2039z",
    "\u2039~": "\u2039\u201a",
    "\u00f7y": "\u00f7z",
    "\u00f7~": "\u00f7\u201a",
    "\u00f9y": "\u00f9z",
    "\u00f9~": "\u00f9\u201a",
}

_BIJOY_ROFOLA_REPLACEMENTS = {
    "&i\u00e6": "\u00aa\u00e6",
    "&i\u0192": "\u00aa\u0192",
    "M\u00aa": "M\u00d6",
    "c\u00aa": "c\u00d6",
    "d\u00aa": "d\u00ab",
    "N\u00aa\u00e6": "N\u00aay",
    "P\u00aa\u00e6": "P\u00aay",
    "Q\u00aa\u00e6": "Q\u00aay",
    "S\u00aa\u00e6": "S\u00aay",
    "U\u00aa\u00e6": "U\u00aay",
    "V\u00aa\u00e6": "V\u00aay",
    "W\u00aa\u00e6": "W\u00aay",
    "X\u00aa\u00e6": "X\u00aay",
    "Y\u00aa\u00e6": "Y\u00aay",
    "b\u00aa\u00e6": "b\u00aay",
    "d\u00ab\u00e6": "d\u00aby",
    "h\u00aa\u00e6": "h\u00aay",
    "j\u00aa\u00e6": "j\u00aay",
    "l\u00aa\u00e6": "l\u00aay",
    "n\u00aa\u00e6": "n\u00aay",
    "\u00e5y": "\u00e5\u00e6",
    "N\u00aa\u0192": "N\u00aa~",
    "P\u00aa\u0192": "P\u00aa~",
    "Q\u00aa\u0192": "Q\u00aa~",
    "S\u00aa\u0192": "S\u00aa~",
    "U\u00aa\u0192": "U\u00aa~",
    "V\u00aa\u0192": "V\u00aa~",
    "W\u00aa\u0192": "W\u00aa~",
    "X\u00aa\u0192": "X\u00aa~",
    "Y\u00aa\u0192": "Y\u00aa~",
    "b\u00aa\u0192": "b\u00aa~",
    "d\u00ab\u0192": "d\u00ab~",
    "h\u00aa\u0192": "h\u00aa~",
    "j\u00aa\u0192": "j\u00aa~",
    "l\u00aa\u0192": "l\u00aa~",
    "n\u00aa\u0192": "n\u00aa~",
    "\u00e5~": "\u00e5\u0192",
    "\u201dQ&e": "\u201dQ\u00a1",
    "k\u00aa": "k\u00d6",
    "m\u00aa": "m\u00d6",
    "g&\u00e5": "\u00a4\u00a3",
}

# Regex-special chars that JS buildConversionPatterns escapes
_SPECIAL_REGEX_CHARS = set(r'\.*+?^$()[]{}|')


def _escape_regex(s: str) -> str:
    """Escape regex special chars, matching JS buildConversionPatterns."""
    return ''.join('\\' + c if c in _SPECIAL_REGEX_CHARS else c for c in s)


def _build_patterns(mapping: dict) -> list:
    """Build sorted list of (compiled_regex, replacement) preserving dict order."""
    patterns = []
    for key, replacement in mapping.items():
        patterns.append((re.compile(_escape_regex(key)), replacement))
    return patterns


def _replace_multiple(text: str, replacements: dict, global_match: bool = True) -> str:
    """Apply multiple string->string replacements as regex patterns.
    Uses callable replacement to avoid re.sub backslash escaping issues.
    """
    result = text
    for pattern_str, replacement in replacements.items():
        count = 0 if global_match else 1
        result = re.sub(pattern_str, lambda m, r=replacement: r, result, count=count)
    return result


def _replace_first_letter(text: str, char: str, replacement: str) -> str:
    """For each line, replace first occurrence of char at start of each word (like JS)."""
    lines = text.split('\n')
    result = []
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        words = re.split(r'(\s+)', line)
        processed = []
        for i, word in enumerate(words):
            if i % 2 == 0:
                word = re.sub('^' + _escape_regex(char), replacement, word, count=1)
            processed.append(word)
        result.append(''.join(processed).strip())
    return '\n'.join(result)


def _replace_last_letter(text: str, char: str, replacement: str) -> str:
    """For each line, replace last occurrence of char at end of each word (like JS)."""
    lines = text.split('\n')
    result = []
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        words = re.split(r'(\s+)', line)
        processed = []
        for i, word in enumerate(words):
            if i % 2 == 0:
                word = re.sub(_escape_regex(char) + '$', replacement, word, count=1)
            processed.append(word)
        result.append(''.join(processed).strip())
    return '\n'.join(result)


def _is_bangla_pre_kar(ch: str) -> bool:
    return ch in ('ি', 'ৈ', 'ে')


def _is_bangla_post_kar(ch: str) -> bool:
    return ch in ('া', 'ো', 'ৌ', 'ৗ', 'ু', 'ূ', 'ী', 'ৃ')


def _is_bangla_kar(ch: str) -> bool:
    return _is_bangla_pre_kar(ch) or _is_bangla_post_kar(ch)


def _is_bangla_banjonborno(ch: str) -> bool:
    return ch in (
        'ক', 'খ', 'গ', 'ঘ', 'ঙ',
        'চ', 'ছ', 'জ', 'ঝ', 'ঞ',
        'ট', 'ঠ', 'ড', 'ঢ', 'ণ',
        'ত', 'থ', 'দ', 'ধ', 'ন',
        'প', 'ফ', 'ব', 'ভ', 'ম',
        'শ', 'ষ', 'স', 'হ',
        'য', 'র', 'ল', 'য়',
        'ং', 'ঃ', 'ঁ', 'ৎ',
    )


def _is_bangla_halant(ch: str) -> bool:
    return ch == '্'


def _is_bangla_nukta(ch: str) -> bool:
    return ch in ('ং', 'ঃ', 'ঁ')


def _is_space(ch: str) -> bool:
    return ch in (' ', '\t', '\n', '\r')


def _rearrange_unicode_text(text: str) -> str:
    """ReArrangeUnicodeText for Unicode→Bijoy direction.
    
    Ported from JS fontconverter.min.js ReArrangeUnicodeText:
    - Pre-kar movement: move pre-kar (ে/ৈ) backward before the consonant cluster
    - Reph reordering: move consonant(s) after র্ forward, then place র্ after them
    
    Both operations reorder characters so the conversion map produces correct Bijoy.
    """
    n = list(text)
    o = 0
    t = 0
    while t < len(n):
        # Pre-kar movement: move ে/ৈ backward before the consonant cluster
        if t < len(n) and _is_bangla_pre_kar(n[t]):
            r = 1
            while t - r >= 0 and _is_bangla_banjonborno(n[t - r]):
                if t - r <= o:
                    break
                if t - r - 1 >= 0 and _is_bangla_halant(n[t - r - 1]):
                    r += 2
                else:
                    break
            f = list(n)
            pre = ''.join(f[:t - r])
            reconstructed = pre + f[t] + ''.join(f[t - r:t]) + ''.join(f[t + 1:])
            n = list(reconstructed)
            o = t + 1
            continue

        # Reph handling: move consonant(s) after র্ before the র্
        if (t < len(n) - 1 and _is_bangla_halant(n[t])
                and t > 0 and n[t - 1] == 'র'):
            i_count = 1
            e_count = 0
            while True:
                ci = t + i_count
                if (ci < len(n) and _is_bangla_banjonborno(n[ci])
                        and ci + 1 < len(n) and _is_bangla_halant(n[ci + 1])):
                    i_count += 2
                elif (ci < len(n) and _is_bangla_banjonborno(n[ci])
                      and ci + 1 < len(n) and _is_bangla_pre_kar(n[ci + 1])):
                    e_count = 1
                    break
                else:
                    break
            u = list(n)
            reconstructed = (''.join(u[:t - 1])
                            + ''.join(u[t + i_count + 1: t + i_count + e_count + 1])
                            + ''.join(u[t + 1: t + i_count + 1])
                            + u[t - 1]
                            + u[t]
                            + ''.join(u[t + i_count + e_count + 1:]))
            n = list(reconstructed)
            t += i_count + e_count
            o = t + 1
            continue

        t += 1

    return ''.join(n)


# Build patterns once
_uni2bijoy_patterns = _build_patterns(_UNI2BIJOY_MAP)


def convert_unicode_to_bijoy(text: str) -> str:
    """Convert Unicode Bangla text to Bijoy ANSI (port of ConvertToASCII from fontconverter.min.js).
    
    This is designed for distributor names with complex character combinations.
    """
    n = text
    # Pre-processing: normalize specific Unicode sequences
    n = re.sub('ব়', 'র', n)
    n = re.sub('ড়', 'ড়', n)
    n = re.sub('ঢ়', 'ঢ়', n)
    n = re.sub('য়', 'য়', n)
    n = re.sub('ো', 'ো', n)
    n = re.sub('ৌ', 'ৌ', n)
    n = re.sub('্র্য', '্র‍্য', n)
    
    # Last letter replacement for র্
    n = _replace_last_letter(n, 'র্', 'i&')
    n = _replace_last_letter(n, 'র্‌', 'i&')
    
    # Rearrange Unicode text
    n = _rearrange_unicode_text(n)
    
    # Apply conversion map patterns
    # Use callable replacement to avoid re.sub backslash escaping issues
    for pattern, replacement in _uni2bijoy_patterns:
        n = pattern.sub(lambda m, r=replacement: r, n)
    
    # Post-processing: replaceFirstLetter for ‡ and ‰
    n = _replace_first_letter(n, '‡', '†')
    n = _replace_first_letter(n, '‰', 'ˆ')
    
    # Specific replacements for contexts after specific chars
    n = n.replace('(‡', '(†')
    n = n.replace('[‡', '[†')
    n = n.replace('Ô‡', 'Ô†')
    n = n.replace('Ò‡', 'Ò†')
    n = n.replace('(‰', '(ˆ')
    n = n.replace('[‰', '[ˆ')
    n = n.replace('Ô‰', 'Ôˆ')
    n = n.replace('Ò‰', 'Òˆ')
    
    # Apply kar and rofola post-processing
    n = _replace_multiple(n, _BIJOY_KAR_REPLACEMENTS, True)
    n = _replace_multiple(n, _BIJOY_ROFOLA_REPLACEMENTS, True)
    
    return n
