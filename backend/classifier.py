import logging
from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy.orm import Session

from models import Category, ClassifierCache
from hebrew_utils import normalize_hebrew_text, hebrew_similarity
from ai_client import call_gemini_with_fallback, extract_json

logger = logging.getLogger(__name__)

# Pre-compiled high-confidence keyword and stem rules
CATEGORY_KEYWORD_RULES = {
    "פירות וירקות": [
        "עגבניות שרי", "תפוח אדמה", "תפוחי אדמה", "בצל סגול", "בצל ירוק", "בצל לבן", "פלפל אדום",
        "פלפל צהוב", "פלפל חריף", "גמבה אדומה", "עלי בייבי", "עשבי תיבול", "פטריות שמפיניון",
        "עגבני", "עגבניה", "עגבניות", "מלפפון", "מלפפונים", "בצל", "שום", "בטט", "בטטה", "בטטות",
        "חסה", "כרוב", "כרובית", "ברוקולי", "גזר", "גזרים", "פלפל", "גמבה", "קישוא", "קישואים",
        "חציל", "חצילים", "פטרוזילי", "כוסבר", "שמיר", "בזיליק", "נענע", "לימון", "לימונים",
        "תפוח", "תפוחים", "בננ", "בננה", "בננות", "תפוז", "תפוזים", "קלמנטינ", "אבוקדו",
        "תות שדה", "תותים", "תות", "ענב", "ענבים", "אבטיח", "מלון", "מנגו", "אפרסק", "שזיף", "אגס",
        "פטריו", "פטריות", "סלרי", "צנוני", "סלק", "תרד", "שרי", "אננס", "קיווי", "רימון",
        "אשכולית", "פומלה", "דלעת", "דלורית", "אספרגוס", "ארטישוק", "נבטים", "רוקט", "אורוגולה",
        "תמר", "תמרים"
    ],
    "מוצרי חלב וביצים": [
        "גבינה בולגרית מעודנת", "בולגרית מעודנת", "גבינה בולגרית", "גבינה לבנה", "גבינה צהובה",
        "גבינת שמנת", "גבינת עיזים", "גבינת נועם", "גבינת עמק", "גבינת גאודה", "קוטג תוקף ארוך",
        "שמנת חמוצה", "שמנת מתוקה", "שמנת לבישול", "יוגורט יווני", "יוגורט ביו", "מעדן שוקולד",
        "חלב שיבולת שועל", "חלב סויה", "חלב שקדים", "חלב דל לקטוז",
        "קוטג", "קוטג'", "חלב", "ביצ", "ביצה", "ביצים", "חמא", "חמאה", "שמנת", "גבינ", "גבינה",
        "גבינות", "יוגורט", "דנונה", "מילקי", "אקטימל", "ריוויון", "מוצרלה", "פטה", "בולגרית",
        "צהובה", "פרמזן", "ריקוטה", "גאודה", "קשקבל", "ברי", "קממבר", "מעדן", "מעדנים", "יולו",
        "דני", "נועם", "עמק", "צפתית", "לבנה", "טופו", "מסקרפונה"
    ],
    "בשר, עוף, דגים וקפואים": [
        "בשר טחון", "חזה עוף", "שניצל עוף טוב", "שניצל מאמא עוף", "שניצל ביתי", "שניצל תירס",
        "שניצל קפוא", "בשר בקר", "בקר טחון", "נקניקיות עוף", "פילה סלמון", "פילה מושט",
        "טונה קפואה", "נסיכת הנילוס", "אפונה קפואה", "שעועית קפואה", "תירס קפוא", "גזר גמדי קפוא",
        "גזר גמדי", "לקט ירקות קפוא", "צ'יפס קפוא", "בצק עלים קפוא", "בצק פילו", "פיצה קפואה",
        "בורקס קפוא", "תות קפוא", "מנגו קפוא", "פירות יער קפואים",
        "בשר", "טחון", "עוף", "שניצל", "כרעיים", "שוקיים", "כנפיים", "פרגיות", "פילה", "צלעות",
        "סטייק", "אנטריקוט", "המבורגר", "נקניק", "נקניקיות", "קבב", "דג", "דגים", "סלמון",
        "דניס", "מושט", "אמנון", "ברמונדי", "לברק", "קפוא", "קפואים", "סנפרוסט", "ציפס", "צ'יפס",
        "בצק עלים", "בצק פילו", "מלוואח", "גחנון", "ג'חנון", "גלידה", "ארטיק", "טילון",
        "שווארמה", "אסאדו", "צלי", "בקר", "הודו"
    ],
    "לחם ומאפים": [
        "לחם כוסמין", "פיתות כוסמין", "פיתות מקמח מלא", "לחם אחיד", "לחם מלא", "לחם שיפון",
        "לחמניות המבורגר", "עוגיות שוקולד צ'יפס", "בורקס גבינה", "בורקס תפוחי אדמה",
        "חלה לשבת", "חלות לשבת",
        "לחם", "לחמני", "לחמניה", "לחמניות", "פיתה", "פיתות", "בגט", "חלה", "חלות", "טורטי",
        "טורטיות", "קרקר", "קרקרים", "פריכיות", "עוגה", "עוגות", "עוגיות", "רוגלך", "קרואסון",
        "בורקס", "מאפה", "מאפים", "טוסט", "פירורי לחם", "מצות", "כוסמין", "שיפון"
    ],
    "מזון יבש, שימורים ותבלינים": [
        "חמאת בוטנים", "רוטב עגבניות לבסיס פיצה", "רוטב עגבניות", "רוטב לפיצה", "עגבניות מרוסקות",
        "רסק עגבניות", "שימורי טונה", "שימורי תירס", "שימורי אפונה", "מלפפונים חמוצים",
        "זיתים ירוקים", "זיתים שחורים", "חמוציות ללא סוכר", "חמוציות לא מסוכרות",
        "חמוציות לא מסוכרים", "שתייה מתוקה", "שתיה מתוקה", "מים מינרליים", "שישיית מים",
        "שמן זית", "שמן קנולה", "טחינה גולמית", "דגני בוקר", "שיבולת שועל",
        "אורז", "פסטה", "ספגטי", "מקרוני", "פתיתים", "קוסקוס", "קמח", "סוכר", "מלח", "שמן",
        "טחינה", "חומוס", "חרדל", "מיונז", "קטשופ", "רוטב", "שימורים", "טונה", "חמוצים",
        "זיתים", "שוקולד", "נוטלה", "ממרח", "ריבה", "דבש", "סילאן", "קורנפלקס", "כריות",
        "קוואקר", "גרנולה", "קפה", "נס קפה", "תה", "תיונים", "שוקולית", "תבלין", "פפריקה",
        "פלפל שחור", "כמון", "כורכום", "אבקת מרק", "שום גבישי", "אורגנו", "קינמון", "שקדי מרק",
        "קטניות", "עדשים", "שעועית", "גרגרי חומוס", "חמוציות", "שקדים", "אגוז", "אגוזים",
        "בוטן", "בוטנים", "קשיו", "פיסטוק", "גרעינים", "חלבה", "ופלים", "ביסקוויט", "חטיף",
        "חטיפים", "במבה", "ביסלי", "דוריטוס", "תפוצ'יפס", "קולה", "ספרייט", "פאנטה",
        "שוופס", "מיץ", "שתייה", "שתיה", "סודה", "בירה", "יין", "סירופ"
    ],
    "ניקיון והיגיינה": [
        "סבון כלים", "נוזל כלים", "סבון ידיים", "סבון נוזלי", "משחת שיניים", "מברשת שיניים",
        "נייר טואלט", "מגבונים לחים", "מגבונים", "נייר סופג", "מגבות נייר", "אבקת כביסה",
        "ג'ל כביסה", "מרכך כביסה", "קפסולות כביסה", "נוזל רצפות", "חומר לרצפה", "שקיות אשפה",
        "שקיות זבל", "מטליות לחות", "מטליות", "טבליות למדיח", "נוזל הברקה למדיח", "מסיר שומנים",
        "סבון", "שמפו", "מרכך", "רחצה", "דאודורנט", "ספוג", "סקוטש", "כביסה", "אקונומיקה",
        "סנו", "מטהר אוויר", "חיתולים"
    ],
    "שונות": [
        "סוללות AA", "סוללות AAA", "סוללות", "גפרורים", "מצת", "נייר כסף", "רדיד אלומיניום",
        "נייר אפייה", "ניילון נצמד", "קיסמים", "כוסות חד פעמיות", "צלחות חד פעמיות",
        "מזלגות חד פעמיים", "סכו\"ם חד פעמי", "נרות שבת", "נרות", "אוכל לכלב", "אוכל לחתול"
    ]
}

def classify_locally(
    item_name: str,
    categories: List[Category],
    db: Session
) -> Optional[Tuple[Category, float, str]]:
    """
    High-speed, 0ms local classification using:
    1. Exact match in ClassifierCache (confidence 1.0)
    2. Slash alternatives decomposition (A/B)
    3. Cached substring matching (longer matches prioritized)
    4. Semantic keyword/stem rules (sorted by specificity)
    5. High-threshold fuzzy match in cache
    """
    if not item_name or not item_name.strip():
        return None

    cat_map = {c.id: c for c in categories}
    cat_by_name = {c.name: c for c in categories}
    norm_name = normalize_hebrew_text(item_name)

    # 1. Exact match in cache
    exact = db.query(ClassifierCache).filter(
        ClassifierCache.item_name_normalized == norm_name
    ).first()
    if exact and exact.category_id in cat_map:
        return cat_map[exact.category_id], exact.confidence, "cache_exact"

    # 2. Slash alternatives: if item has slashes (e.g. גבינה לבנה/יוגורט, בשר טחון/חזה עוף)
    if "/" in item_name:
        parts = [p.strip() for p in item_name.split("/") if p.strip()]
        for p in parts:
            res = classify_locally(p, categories, db)
            if res and res[0].name != "שונות":
                return res[0], 0.99, f"slash_part({res[2]})"

    all_cached = db.query(ClassifierCache).all()

    # 3. Substring match in cache (longest matching cached item wins)
    best_sub: Optional[ClassifierCache] = None
    best_len = 0
    for c in all_cached:
        if c.category_id not in cat_map:
            continue
        c_norm = c.item_name_normalized
        if len(c_norm) >= 3 and c_norm in norm_name:
            if len(c_norm) > best_len:
                best_len = len(c_norm)
                best_sub = c

    if best_sub and best_len >= 4:
        return cat_map[best_sub.category_id], 0.98, f"cache_substring('{best_sub.item_name_normalized}')"

    # 4. Keyword rules: check specific rules (sort by rule length descending to avoid short prefixes)
    all_rules = []
    for cat_name, kw_list in CATEGORY_KEYWORD_RULES.items():
        if cat_name not in cat_by_name:
            continue
        for kw in kw_list:
            all_rules.append((len(kw), kw, cat_by_name[cat_name]))
    all_rules.sort(key=lambda x: x[0], reverse=True)

    for _, kw, cat in all_rules:
        kw_norm = normalize_hebrew_text(kw)
        if kw_norm in norm_name:
            return cat, 0.95, f"keyword_rule('{kw}')"

    # 5. Fuzzy match against cache (high threshold)
    best_sim = 0.0
    best_match_entry: Optional[ClassifierCache] = None
    for cached in all_cached:
        if cached.category_id not in cat_map:
            continue
        sim = hebrew_similarity(norm_name, cached.item_name_normalized)
        if sim > best_sim:
            best_sim = sim
            best_match_entry = cached

    if best_match_entry and best_sim >= 0.82:
        return cat_map[best_match_entry.category_id], best_sim, f"fuzzy({best_sim:.2f})"

    return None

def check_local_cache(
    item_name: str,
    categories: List[Category],
    db: Session,
    threshold: float = 0.90
) -> Optional[Tuple[Category, float]]:
    """
    Checks if an item can be classified locally with confidence >= threshold.
    Runs in 0ms without any AI API calls.
    """
    res = classify_locally(item_name, categories, db)
    if res:
        cat, conf, _ = res
        if conf >= threshold and cat.name != "שונות":
            return cat, conf
    return None

async def classify_item(
    item_name: str,
    categories: List[Category],
    db: Session,
    threshold: float = 0.90
) -> Tuple[Category, float, str]:
    """
    Classifies a grocery item. Uses ultra-fast local classifier first.
    Falls back to Gemini AI only if unknown, with safe fallback to prevent 429 cascades.
    """
    if not categories:
        raise ValueError("No categories available in system.")

    norm_name = normalize_hebrew_text(item_name)
    default_cat = next((c for c in categories if c.name == "שונות"), categories[-1])

    # 1. Try local classification (0ms)
    local_res = classify_locally(item_name, categories, db)
    if local_res:
        cat, conf, src = local_res
        if conf >= threshold and cat.name != "שונות":
            return cat, conf, src

    # 2. Try Gemini AI (only for genuinely unknown items)
    prompt = f"""
סווג את פריט הקניות הבא לאחת מתוך הקטגוריות הקיימות בדיוק.
פריט: "{item_name}"

רשימת הקטגוריות המותרות:
{chr(10).join(f"- {c.name}" for c in categories)}

החזר אך ורק אובייקט JSON בפורמט הבא:
{{
  "category": "שם הקטגוריה בדיוק מתוך הרשימה",
  "confidence": 1.0
}}
"""
    raw_ai_res, ai_err = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה עוזר חכם לסיווג מוצרי קניות לסופרמרקט בעברית.",
        json_mode=True
    )

    if raw_ai_res:
        data = extract_json(raw_ai_res)
        if isinstance(data, dict):
            matched_cat_name = data.get("category", "").strip()
            ai_confidence = float(data.get("confidence", 1.0))

            matched_cat = next((c for c in categories if c.name == matched_cat_name), None)
            if not matched_cat:
                best_c_sim = 0.0
                for c in categories:
                    csim = hebrew_similarity(matched_cat_name, c.name)
                    if csim > best_c_sim:
                        best_c_sim = csim
                        matched_cat = c

            if matched_cat:
                save_to_cache(norm_name, matched_cat.id, ai_confidence, "ai", db)
                return matched_cat, ai_confidence, "ai"

    # 3. If AI failed (e.g. 429 quota limit), use local classifier result or default
    if local_res:
        cat, conf, src = local_res
        return cat, conf, f"local_fallback_after_ai({src})"

    return default_cat, 0.5, "fallback_default"

def save_to_cache(
    norm_name: str,
    category_id: int,
    confidence: float,
    source: str,
    db: Session
):
    """Saves or updates item classification in local cache."""
    existing = db.query(ClassifierCache).filter(
        ClassifierCache.item_name_normalized == norm_name
    ).first()

    if existing:
        existing.category_id = category_id
        existing.confidence = confidence
        existing.source = source
        existing.usage_count += 1
        existing.updated_at = datetime.utcnow()
    else:
        new_entry = ClassifierCache(
            item_name_normalized=norm_name,
            category_id=category_id,
            confidence=confidence,
            source=source,
            usage_count=1,
            updated_at=datetime.utcnow()
        )
        db.add(new_entry)
    db.commit()

def record_user_correction(
    item_name: str,
    category_id: int,
    db: Session
):
    """
    Called when a user manually modifies an item's category.
    Sets 100% confidence with source='user' to permanently train the local classifier.
    """
    norm_name = normalize_hebrew_text(item_name)
    save_to_cache(norm_name, category_id, 1.0, "user", db)
