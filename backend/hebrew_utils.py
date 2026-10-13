import re
import unicodedata
from rapidfuzz import fuzz

def normalize_hebrew_text(text: str) -> str:
    """
    Normalizes Hebrew text for comparison:
    - Lowercase (for any English/Latin letters)
    - Strips niqqud (vocalization points)
    - Normalizes double yod (יי -> י) and double vav (וו -> ו)
    - Normalizes final letters (ם->מ, ן->נ, ץ->צ, ף->פ, ך->כ)
    - Removes superfluous spaces
    """
    if not text:
        return ""

    # Remove niqqud
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().strip()

    # Normalization of multiple yods and vavs
    text = re.sub(r"י+", "י", text)
    text = re.sub(r"ו+", "ו", text)

    # Replace final Hebrew letters with standard letters for root/stem similarity
    final_to_standard = {
        'ם': 'מ',
        'ן': 'נ',
        'ץ': 'צ',
        'ף': 'פ',
        'ך': 'כ'
    }
    normalized_chars = [final_to_standard.get(c, c) for c in text]
    text = "".join(normalized_chars)

    # Remove quotes like " or ' or ` often used in abbreviations (ק"ג -> קג or keep for units)
    # But for item names keep alphanumeric
    text = re.sub(r'[\'\"״׳]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def strip_hebrew_prefix(text: str) -> str:
    """
    Strips common prefixes like 'ה' (the), 'ו' (and), 'ב' (in), 'ל' (to)
    if the word length permits.
    """
    words = text.split()
    cleaned_words = []
    for w in words:
        if len(w) > 3 and w.startswith("ה"):
            w = w[1:]
        elif len(w) > 3 and w.startswith("ו"):
            w = w[1:]
        cleaned_words.append(w)
    return " ".join(cleaned_words)

def hebrew_similarity(s1: str, s2: str) -> float:
    """
    Calculates similarity between two Hebrew strings (0.0 to 1.0)
    using multiple normalized metrics.
    """
    if not s1 or not s2:
        return 0.0

    n1 = normalize_hebrew_text(s1)
    n2 = normalize_hebrew_text(s2)

    if n1 == n2:
        return 1.0

    # Test with prefix stripped
    p1 = strip_hebrew_prefix(n1)
    p2 = strip_hebrew_prefix(n2)
    if p1 == p2:
        return 0.98

    # Singular/plural common Hebrew endings: ים, ות
    # e.g. עגבניות vs עגבניה, מלפפונים vs מלפפון
    stem1 = re.sub(r'(ימ|ות|יה|ה)$', '', p1)
    stem2 = re.sub(r'(ימ|ות|יה|ה)$', '', p2)
    if len(stem1) >= 3 and stem1 == stem2:
        return 0.97

    # RapidFuzz similarity ratios
    ratio = fuzz.ratio(n1, n2) / 100.0
    token_sort = fuzz.token_sort_ratio(n1, n2) / 100.0

    return max(ratio, token_sort)
