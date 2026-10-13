import logging
from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy.orm import Session

from models import Category, ClassifierCache
from hebrew_utils import normalize_hebrew_text, hebrew_similarity
from ai_client import call_gemini_with_fallback, extract_json

logger = logging.getLogger(__name__)

def check_local_cache(
    item_name: str,
    categories: List[Category],
    db: Session,
    threshold: float = 0.99
) -> Optional[Tuple[Category, float]]:
    """
    Checks if an item is already known in the local cache with high confidence.
    Runs in 0ms without any AI API calls.
    """
    norm_name = normalize_hebrew_text(item_name)
    category_map = {c.id: c for c in categories}

    # 1. Exact match
    exact_entry = db.query(ClassifierCache).filter(
        ClassifierCache.item_name_normalized == norm_name
    ).first()

    if exact_entry and exact_entry.category_id in category_map:
        if exact_entry.confidence >= threshold:
            exact_entry.usage_count += 1
            exact_entry.updated_at = datetime.utcnow()
            db.commit()
            return category_map[exact_entry.category_id], exact_entry.confidence

    # 2. Hebrew fuzzy match
    all_cached = db.query(ClassifierCache).all()
    best_match_entry: Optional[ClassifierCache] = None
    best_sim: float = 0.0

    for cached in all_cached:
        if cached.category_id not in category_map:
            continue
        sim = hebrew_similarity(norm_name, cached.item_name_normalized)
        if sim > best_sim:
            best_sim = sim
            best_match_entry = cached

    if best_match_entry and best_sim >= 0.90:
        eff_confidence = best_match_entry.confidence * best_sim
        if eff_confidence >= threshold:
            best_match_entry.usage_count += 1
            best_match_entry.updated_at = datetime.utcnow()
            db.commit()
            return category_map[best_match_entry.category_id], eff_confidence

    return None

async def classify_item(
    item_name: str,
    categories: List[Category],
    db: Session,
    threshold: float = 0.99
) -> Tuple[Category, float, str]:
    """
    Classifies a grocery item into one of the available categories.
    """
    if not categories:
        raise ValueError("No categories available in system.")

    norm_name = normalize_hebrew_text(item_name)
    category_map = {c.id: c for c in categories}
    default_cat = next((c for c in categories if c.name == "שונות"), categories[-1])

    cached = check_local_cache(item_name, categories, db, threshold)
    if cached:
        cat, conf = cached
        return cat, conf, "cache"

    # Call Gemini AI
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
    raw_ai_res, _ = await call_gemini_with_fallback(
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
