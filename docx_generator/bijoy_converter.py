import re
import unicodedata


class BijoyConverter:
    def __init__(self):
        self.main_char = {
            "।": "|", "\u2018": "Ô", "\u2019": "Õ", "\u201C": "Ò", "\u201D": "Ó",
            "্র্য": "ª¨", "ম্প্র": "¤cÖ", "র\u200C্য": "i¨", "ক্ষ্ম": "²",
            "ক্ক": "°", "ক্ট": "±", "ক্ত": "³", "ক্ব": "K¡", "স্ক্র": "¯Œ",
            "ক্র": "µ", "ক্ল": "K¬", "ক্ষ": "¶", "ক্স": "·", "গু": "¸",
            "গ্ধ": "»", "গ্ন": "Mœ", "গ্ম": "M¥", "গ্ল": "M­", "গ্রু": "Mªy",
            "ঙ্ক": "¼", "ঙ্ক্ষ": "•¶", "ঙ্খ": "•L", "ঙ্গ": "½", "ঙ্ঘ": "•N",
            "চ্ছ্ব": "\u201cQ¡", "চ্চ": "\u201cP", "চ্ছ": "\u201cQ", "চ্ঞ": "\u201cT", "জ্জ্ব": "¾¡",
            "জ্জ": "¾", "জ্ঝ": "À", "জ্ঞ": "Á", "জ্ব": "R¡", "ঞ্চ": "Â",
            "ঞ্ছ": "Ã", "ঞ্জ": "Ä", "ঞ্ঝ": "Å", "ট্ট": "Æ", "ট্ব": "U¡",
            "ট্ম": "U¥", "ড্ড": "Ç", "ণ্ট": "È", "ণ্ঠ": "É", "ন্স": "Ý",
            "ণ্ড": "Ê", "ন্তু": "š\u2018", "ণ্ব": "Y^", "ত্ত্ব": "Ë¡", "ত্ত": "Ë",
            "ত্থ": "Ì", "ত্ন": "Zœ", "ত্ম": "Z¥", "ন্ত্ব": "š\u2014¡", "ত্ব": "Z¡",
            "থ্ব": "_¡", "দ্গ": "˜M", "দ্ঘ": "˜N", "দ্দ": "Ï", "দ্ধ": "×",
            "দ্ব": "Ø", "দ্ভ": "™¢", "দ্ম": "Ù", "দ্রু": "`ª\u201d", "ধ্ব": "aŸ",
            "ধ্ম": "a¥", "ন্ট": "›U", "ন্ঠ": "Ú", "ন্ড": "Û", "ন্ত্র": "š¿",
            "ন্ত": "š\u2014", "স্ত্র": "¯¿", "ত্র": "Î", "ন্থ": "š\u2019", "ন্দ": "›`",
            "ন্দ্ব": "›Ø", "ন্ধ": "Ü", "ন্ন": "bœ", "ন্ব": "š^", "ন্ম": "b¥",
            "প্ট": "Þ", "প্ত": "ß", "প্ন": "cœ", "প্প": "à", "প্ল": "cø",
            "প্স": "á", "ফ্ল": "d¬", "ব্জ": "â", "ব্দ": "ã", "ব্ধ": "ä",
            "ব্ব": "eŸ", "ব্ল": "e­", "ভ্র": "å", "ম্ন": "gœ", "ম্প": "¤ú",
            "ম্ফ": "ç", "ম্ব": "¤^", "ম্ভ": "¤¢", "ম্ভ্র": "¤£", "ম্ম": "¤§",
            "ম্ল": "¤­", "্র": "ª", "রু": "i\u201d", "রূ": "iƒ", "ল্ক": "é",
            "ল্গ": "ê", "ল্ট": "ë", "ল্ড": "ì", "ল্প": "í", "ল্ফ": "î",
            "ল্ব": "j¦", "ল্ম": "j¥", "ল্ল": "jø", "শু": "ï", "শ্চ": "ð",
            "শ্ন": "kœ", "শ্ব": "k¦", "শ্ম": "k¥", "শ্ল": "k­", "ষ্ক": "®\u2039",
            "ষ্ক্র": "®Œ", "ষ্ট": "ó", "ষ্ঠ": "ô", "ষ্ণ": "ò", "ষ্প": "®ú",
            "ষ্ফ": "õ", "ষ্ম": "®§", "স্ক": "¯\u2039", "স্ট": "÷", "স্খ": "ö",
            "স্ত": "¯Í", "স্তু": "¯\u2018", "স্থ": "¯\u2019", "স্ন": "mœ", "স্প": "¯ú",
            "স্ফ": "ù", "স্ব": "¯^", "স্ম": "¯§", "স্ল": "¯­", "হু": "û",
            "হ্ণ": "nè", "হ্ব": "nŸ", "হ্ন": "ý", "হ্ম": "þ", "হ্ল": "n¬",
            "হৃ": "ü", "র্": "©", "্য": "¨",
            # FIX 3: "্" (bare hasanta) removed from mapping table.
            # An unmatched hasanta is suppressed (see unicode_to_bijoy) rather
            # than emitting "&" which corrupted output for unknown conjuncts.
            "আ": "Av",
            "অ": "A", "ই": "B", "ঈ": "C", "উ": "D", "ঊ": "E",
            "ঋ": "F", "এ": "G", "ঐ": "H", "ও": "I", "ঔ": "J",
            "ক": "K", "খ": "L", "গ": "M", "ঘ": "N", "ঙ": "O",
            "চ": "P", "ছ": "Q", "জ": "R", "ঝ": "S", "ঞ": "T",
            "ট": "U", "ঠ": "V", "ড": "W", "ঢ": "X", "ণ": "Y",
            "ত": "Z", "থ": "_", "দ": "`", "ধ": "a", "ন": "b",
            "প": "c", "ফ": "d", "ব": "e", "ভ": "f", "ম": "g",
            "য": "h", "র": "i", "ল": "j", "শ": "k", "ষ": "l",
            "স": "m", "হ": "n", "ড়": "o", "ঢ়": "p", "য়": "q",
            "ৎ": "r", "০": "0", "১": "1", "২": "2", "৩": "3",
            "৪": "4", "৫": "5", "৬": "6", "৭": "7", "৮": "8",
            "৯": "9", "া": "v", "ি": "w", "ী": "x", "ু": "y",
            "ূ": "~", "ৃ": "…", "ে": "‡", "ৈ": "‰", "ৗ": "Š",
            "ং": "s", "ঃ": "t", "ঁ": "u"
        }

        # Pre-sort keys once by descending length for longest-match
        self._sorted_keys = sorted(self.main_char.keys(), key=len, reverse=True)

    def is_bangla_pre_kar(self, c):
        return c in ('ি', 'ৈ', 'ে')

    def is_bangla_banjonborno(self, c):
        return c in (
            'ক', 'খ', 'গ', 'ঘ', 'ঙ', 'চ', 'ছ', 'জ', 'ঝ', 'ঞ',
            'ট', 'ঠ', 'ড', 'ঢ', 'ণ', 'ত', 'থ', 'দ', 'ধ', 'ন',
            'প', 'ফ', 'ব', 'ভ', 'ম', 'য', 'র', 'ল', 'শ', 'ষ',
            'স', 'হ', 'ড়', 'ঢ়', 'য়', 'ৎ', 'ং', 'ঃ', 'ঁ'
        )

    def is_bangla_halant(self, c):
        return c == '্'

    def re_arrange_unicode_for_bijoy(self, text):
        i = 0
        while i < len(text):
            # ── Pre-Kar rearrangement ──────────────────────────────────────
            # Move ি / ে / ৈ before the full consonant cluster it belongs to.
            if self.is_bangla_pre_kar(text[i]):
                j = 1
                while i - j >= 0:
                    if self.is_bangla_banjonborno(text[i - j]):
                        if i - j - 1 >= 0 and self.is_bangla_halant(text[i - j - 1]):
                            j += 2
                        else:
                            break
                    else:
                        break

                text = text[:i - j] + text[i] + text[i - j:i] + text[i + 1:]
                i += 1
                continue

            # ── Reph (র্) rearrangement ────────────────────────────────────
            # Condition: current char is hasanta, previous char is র,
            # and the char before that is NOT another hasanta (not already part
            # of a conjunct that starts with র).
            if (i < len(text) - 1
                    and self.is_bangla_halant(text[i])
                    and i > 0
                    and text[i - 1] == 'র'
                    and (i < 2 or not self.is_bangla_halant(text[i - 2]))):

                # Walk forward past the consonant cluster that reph sits over.
                j = 1
                az = 0  # 1 if there is a pre-kar immediately after the cluster
                while i + j < len(text):
                    if (i + j + 1 < len(text)
                            and self.is_bangla_banjonborno(text[i + j])
                            and self.is_bangla_halant(text[i + j + 1])):
                        # More conjunct: skip consonant + hasanta
                        j += 2
                    elif (i + j < len(text)
                          and self.is_bangla_banjonborno(text[i + j])
                          and i + j + 1 < len(text)
                          and self.is_bangla_pre_kar(text[i + j + 1])):
                        # Consonant followed by pre-kar — include the pre-kar
                        # in the block so it doesn't end up between reph and
                        # its base consonant after rearrangement.
                        # FIX 2: was `az = 1; break` but slice didn't include
                        # the pre-kar character, leaving it stranded between
                        # reph and the consonant.  We now advance j to cover
                        # the consonant and set az=1 to carry the pre-kar.
                        j += 1   # include the final consonant
                        az = 1   # signal: one more char (the pre-kar) follows
                        break
                    else:
                        break

                # Rebuild:  [pre-reph] [pre-kar if az] [cluster] [র্] [rest]
                # Original: text[i-1]='র', text[i]='্', cluster=text[i+1:i+j+1]
                # Optional pre-kar: text[i+j+1]  (only when az==1)
                pre_kar_char = text[i + j + 1] if az else ""
                cluster      = text[i + 1: i + j + 1]
                reph_pair    = text[i - 1: i + 1]          # "র্"
                after        = text[i + j + 1 + az:]

                text = text[:i - 1] + pre_kar_char + cluster + reph_pair + after
                # After rebuild i-1 now points into the rearranged block;
                # advance past pre_kar + cluster + reph_pair
                i += j + az  # net advance (we consumed reph_pair at i-1..i)
                continue

            i += 1
        return text

    def unicode_to_bijoy(self, text):
        if not text:
            return ""

        # FIX 1: Proper NFC normalisation so that ো, ৌ, ড়, য় composed via
        # two codepoints (e.g. ড = U+09A1 + U+09BC) are collapsed to their
        # single precomposed NFC forms (U+09DC, U+09DF, U+09CB, U+09CC)
        # before any further processing.  The original code replaced each
        # string with itself (identical literals), which was a no-op.
        text = unicodedata.normalize("NFC", text)

        # Re-arrange for Bijoy rules (pre-kars and reph)
        text = self.re_arrange_unicode_for_bijoy(text)

        # Character mapping — longest match first
        result = ""
        i = 0
        while i < len(text):
            matched = False
            for key in self._sorted_keys:
                if text.startswith(key, i):
                    result += self.main_char[key]
                    i += len(key)
                    matched = True
                    break
            if not matched:
                c = text[i]
                # FIX 3: A bare hasanta (্) that survived the conjunct-matching
                # phase means it is either a visible hasanta at word-end or
                # part of an unrecognised conjunct.  In both cases emitting "&"
                # (the old mapping) corrupted the Bijoy output.  We suppress it
                # silently; the surrounding consonants are already mapped.
                if c == '্':
                    i += 1
                    continue
                result += c
                i += 1

        # Post-processing: য়-e-kar and ড়-e-kar position fixes
        result = result.replace("q‡", "‡q")
        result = result.replace("o‡", "‡o")

        # FIX 4: Reph (©) position fix.
        # The original code swapped © with only the immediately next character.
        # When a conjunct maps to a multi-character Bijoy sequence (e.g. "¶"
        # for ক্ষ is one char, but some map to two), © must move to AFTER the
        # entire mapped sequence, not just one character.
        # Strategy: scan for © and move it past all non-space, non-ASCII-letter
        # Bijoy glyph characters that follow it, stopping at the first "base"
        # character (a-z / A-Z) or space — because in SutonnyMJ layout the
        # reph glyph always renders on top of the last typeable base character.
        chars = list(result)
        i = 0
        while i < len(chars):
            if chars[i] == '©':
                # Find where to insert © after the conjunct sequence
                j = i + 1
                # Move past the conjunct: consume chars until we hit a char
                # that is a plain ASCII letter (a-z / A-Z), which represents
                # the "base" consonant in Bijoy encoding.  © should sit after
                # that base character.
                while j < len(chars) and not (chars[j].isascii() and chars[j].isalpha()):
                    j += 1
                # Also include the base ASCII letter itself
                if j < len(chars):
                    j += 1
                # Re-insert © after position j-1
                chars.pop(i)
                chars.insert(j - 1, '©')
                i = j  # skip past the repositioned reph
            else:
                i += 1

        return "".join(chars)


# Helper function for external use
def convert_to_bijoy(text):
    converter = BijoyConverter()
    return converter.unicode_to_bijoy(text)