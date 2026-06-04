import re

class BijoyConverter:
    def __init__(self):
        self.main_char = {
            "।": "|", "‘": "Ô", "’": "Õ", "“": "Ò", "”": "Ó",
            "্র্য": "ª¨", "ম্প্র": "¤cÖ", "র‌্য": "i¨", "ক্ষ্ম": "²",
            "ক্ক": "°", "ক্ট": "±", "ক্ত": "³", "ক্ব": "K¡", "স্ক্র": "¯Œ",
            "ক্র": "µ", "ক্ল": "K¬", "ক্ষ": "¶", "ক্স": "·", "গু": "¸",
            "গ্ধ": "»", "গ্ন": "Mœ", "গ্ম": "M¥", "গ্ল": "M­", "গ্রু": "Mªy",
            "ঙ্ক": "¼", "ঙ্ক্ষ": "•¶", "ঙ্খ": "•L", "ঙ্গ": "½", "ঙ্ঘ": "•N",
            "চ্ছ্ব": "”Q¡", "চ্চ": "”P", "চ্ছ": "”Q", "চ্ঞ": "”T", "জ্জ্ব": "¾¡",
            "জ্জ": "¾", "জ্ঝ": "À", "জ্ঞ": "Á", "জ্ব": "R¡", "ঞ্চ": "Â",
            "ঞ্ছ": "Ã", "ঞ্জ": "Ä", "ঞ্ঝ": "Å", "ট্ট": "Æ", "ট্ব": "U¡",
            "ট্ম": "U¥", "ড্ড": "Ç", "ণ্ট": "È", "ণ্ঠ": "É", "ন্স": "Ý",
            "ণ্ড": "Ê", "ন্তু": "š‘", "ণ্ব": "Y^", "ত্ত্ব": "Ë¡", "ত্ত": "Ë",
            "ত্থ": "Ì", "ত্ন": "Zœ", "ত্ম": "Z¥", "ন্ত্ব": "š—¡", "ত্ব": "Z¡",
            "থ্ব": "_¡", "দ্গ": "˜M", "দ্ঘ": "˜N", "দ্দ": "Ï", "দ্ধ": "×",
            "দ্ব": "Ø", "দ্ভ": "™¢", "দ্ম": "Ù", "দ্রু": "`ª“", "ধ্ব": "aŸ",
            "ধ্ম": "a¥", "ন্ট": "›U", "ন্ঠ": "Ú", "ন্ড": "Û", "ন্ত্র": "š¿",
            "ন্ত": "š—", "স্ত্র": "¯¿", "ত্র": "Î", "ন্থ": "š’", "ন্দ": "›`",
            "ন্দ্ব": "›Ø", "ন্ধ": "Ü", "ন্ন": "bœ", "ন্ব": "š^", "ন্ম": "b¥",
            "প্ট": "Þ", "প্ত": "ß", "প্ন": "cœ", "প্প": "à", "প্ল": "cø",
            "প্স": "á", "ফ্ল": "d¬", "ব্জ": "â", "ব্দ": "ã", "ব্ধ": "ä",
            "ব্ব": "eŸ", "ব্ল": "e­", "ভ্র": "å", "ম্ন": "gœ", "ম্প": "¤ú",
            "ম্ফ": "ç", "ম্ব": "¤^", "ম্ভ": "¤¢", "ম্ভ্র": "¤£", "ম্ম": "¤§",
            "ম্ল": "¤­", "্র": "ª", "রু": "i“", "রূ": "iƒ", "ল্ক": "é",
            "ল্গ": "ê", "ল্ট": "ë", "ল্ড": "ì", "ল্প": "í", "ল্ফ": "î",
            "ল্ব": "j¦", "ল্ম": "j¥", "ল্ল": "jø", "শু": "ï", "শ্চ": "ð",
            "শ্ন": "kœ", "শ্ব": "k¦", "শ্ম": "k¥", "শ্ল": "k­", "ষ্ক": "®‹",
            "ষ্ক্র": "®Œ", "ষ্ট": "ó", "ষ্ঠ": "ô", "ষ্ণ": "ò", "ষ্প": "®ú",
            "ষ্ফ": "õ", "ষ্ম": "®§", "স্ক": "¯‹", "স্ট": "÷", "স্খ": "ö",
            "স্ত": "¯Í", "স্তু": "¯‘", "স্থ": "¯’", "স্ন": "mœ", "স্প": "¯ú",
            "স্ফ": "ù", "স্ব": "¯^", "স্ম": "¯§", "স্ল": "¯­", "হু": "û",
            "হ্ণ": "nè", "হ্ব": "nŸ", "হ্ন": "ý", "হ্ম": "þ", "হ্ল": "n¬",
            "হৃ": "ü", "র্": "©", "্য": "¨", "্": "&", "আ": "Av",
            "অ": "A", "ই": "B", "ঈ": "C", "উ": "D", "ঊ": "E",
            "ঋ": "F", "এ": "G", "ঐ": "H", "ও": "I", "ঔ": "J",
            "ক": "K", "খ": "L", "গ": "M", "ঘ": "N", "ঙ": "O",
            "চ": "P", "ছ": "Q", "জ": "R", "ঝ": "S", "ঞ": "T",
            "ট": "U", "ঠ": "V", "ড": "W", "ঢ": "X", "ণ": "Y",
            "ত": "Z", "থ": "_", "দ": "`", "ধ": "a", "ন": "b",
            "প": "c", "ফ": "d", "ব": "e", "ভ": "f", "ম": "g",
            "য": "h", "র": "i", "ল": "j", "শ": "k", "ষ": "l",
            "স": "m", "হ": "n", "ড়": "o", "ঢ়": "p", "য়": "q",
            "ৎ": "r", "০": "0", "১": "1", "২": "2", "৩": "3",
            "৪": "4", "৫": "5", "৬": "6", "৭": "7", "৮": "8",
            "৯": "9", "া": "v", "ি": "w", "ী": "x", "ু": "y",
            "ূ": "~", "ৃ": "…", "ে": "‡", "ৈ": "‰", "ৗ": "Š",
            "ং": "s", "ঃ": "t", "ঁ": "u"
        }

    def is_bangla_pre_kar(self, c):
        return c in ['ি', 'ৈ', 'ে']

    def is_bangla_banjonborno(self, c):
        return c in ['ক', 'খ', 'গ', 'ঘ', 'ঙ', 'চ', 'ছ', 'জ', 'ঝ', 'ঞ', 'ট', 'ঠ', 'ড', 'ঢ', 'ণ', 'ত', 'থ', 'দ', 'ধ', 'ন', 'প', 'ফ', 'ব', 'ভ', 'ম', 'য', 'র', 'ল', 'শ', 'ষ', 'স', 'হ', 'ড়', 'ঢ়', 'য়', 'ৎ', 'ং', 'ঃ', 'ঁ']

    def is_bangla_halant(self, c):
        return c == '্'

    def re_arrange_unicode_for_bijoy(self, text):
        i = 0
        while i < len(text):
            # Pre-Kar rearrangement
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
                
                # Move Kar before the consonant group
                text = text[:i - j] + text[i] + text[i - j:i] + text[i + 1:]
                i += 1
                continue

            # Reph (Ref) rearrangement
            if i < len(text) - 1 and self.is_bangla_halant(text[i]) and i > 0 and text[i - 1] == 'র' and (i < 2 or not self.is_bangla_halant(text[i - 2])):
                j = 1
                az = 0
                while i + j < len(text):
                    if i + j + 1 < len(text) and self.is_bangla_banjonborno(text[i + j]) and self.is_bangla_halant(text[i + j + 1]):
                        j += 2
                    elif i + j + 1 < len(text) and self.is_bangla_banjonborno(text[i + j]) and self.is_bangla_pre_kar(text[i + j + 1]):
                        az = 1
                        break
                    else:
                        break
                
                # Move Reph after the consonant group
                text = text[:i - 1] + text[i + j + 1:i + j + az + 1] + text[i + 1:i + j + 1] + text[i - 1:i + 1] + text[i + j + az + 1:]
                i += j + az + 1
                continue
            
            i += 1
        return text

    def unicode_to_bijoy(self, text):
        if not text:
            return ""
        
        # Handle compound kars
        text = text.replace('ো', 'ো')
        text = text.replace('ৌ', 'ৌ')
        
        # Normalize some characters
        text = text.replace('ড়', 'ড়')
        text = text.replace('য়', 'য়')
        
        # Re-arrange for Bijoy rules (Kars and Reph)
        text = self.re_arrange_unicode_for_bijoy(text)
        
        # Character mapping
        result = ""
        i = 0
        # Sort keys by length descending to match longest sequences first (like '্র্য')
        sorted_keys = sorted(self.main_char.keys(), key=len, reverse=True)
        
        while i < len(text):
            matched = False
            for key in sorted_keys:
                if text.startswith(key, i):
                    result += self.main_char[key]
                    i += len(key)
                    matched = True
                    break
            if not matched:
                result += text[i]
                i += 1
        
        # Post-processing fixes
        result = result.replace("q‡", "‡q")
        result = result.replace("o‡", "‡o")
        return result

# Helper function for external use
def convert_to_bijoy(text):
    converter = BijoyConverter()
    return converter.unicode_to_bijoy(text)
