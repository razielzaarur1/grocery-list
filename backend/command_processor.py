import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Item, Category, ClassifierCache
from classifier import classify_item, save_to_cache, record_user_correction, check_local_cache, classify_locally
from hebrew_utils import normalize_hebrew_text, hebrew_similarity
from ai_client import call_gemini_with_fallback, extract_json

logger = logging.getLogger(__name__)

# Explicit command trigger words in Hebrew
COMMAND_TRIGGER_WORDS = [
    "תמחק", "מחק", "תמחוק", "תמחקי", "תמחקו", "למחוק",
    "תוריד", "הורד", "תורידי", "תורידו", "להוריד",
    "תוסיף", "הוסף", "תוסיפי", "תוסיפו", "להוסיף",
    "תחליף", "החלף", "תעביר", "העבר", "שנה", "תשנה",
    "תנקה", "נקה", "לנקות", "סמן", "תסמן", "לסמן", "בטל", "לבטל",
    "כל ה", "שמתחיל", "שנגמר", "שמכיל", "תרוקן", "רוקן", "לרוקן",
    "תעבור", "תסדר", "תתקן", "סיווגת", "סווגת", "שמת", "סווג", "לסדר"
]

HEADER_PATTERNS = [
    r'^(רשימת\s+)?(קניות|סופר|מצרכים)(\s+לסופר|\s+לבית)?[:\s\.-]*$',
    r'^(רשימה)[:\s\.-]*$',
    r'^(קניות|מצרכים)[:\s\.-]*$'
]

def is_header_line(text: str) -> bool:
    """Checks if a line is just a title/header like 'קניות', 'רשימת קניות'."""
    clean = text.strip()
    clean_norm = re.sub(r'[\'\"״׳:!\.-]', '', clean).strip()
    for pat in HEADER_PATTERNS:
        if re.match(pat, clean_norm):
            return True
    return False

RECLASSIFY_PATTERNS = [
    r'(סיווגת|סווגת|שמת|הכנסת|זרקת).*(בשונות|לא נכון)',
    r'(תעבור\s+מחדש|תעבור\s+שוב|תסדר\s+מחדש|סווג\s+מחדש|תסדר\s+את\s+הפריטים|תתקן\s+את\s+הקטגוריות|לסדר\s+מחדש)',
    r'(תעביר|תסדר).*(משונות|בשונות)'
]

def is_reclassify_request(text: str) -> bool:
    """Checks if the user is asking to review, reclassify, or fix categories of existing items."""
    clean = text.strip()
    for pat in RECLASSIFY_PATTERNS:
        if re.search(pat, clean):
            return True
    return False

FEEDBACK_PATTERNS = [
    r'^(למה|מדוע|איך|איפה|האם)\s+.*',
    r'^(תגיד|תסביר|שגיאה|הודעת שגיאה).*'
]

def is_feedback_or_conversational(text: str) -> bool:
    """Checks if text looks like generic question rather than grocery items or commands."""
    clean = text.strip()
    # Do not treat reclassification commands as generic feedback!
    if is_reclassify_request(clean):
        return False
    for pat in FEEDBACK_PATTERNS:
        if re.search(pat, clean):
            return True
    return False

def looks_like_command(text: str) -> bool:
    """
    Checks if the user input is an explicit command rather than items to add.
    """
    clean = text.strip()
    words = clean.split()
    for w in words:
        w_norm = re.sub(r'[\'\"״׳:!\.\?\-,]', '', w).strip()
        if w_norm in COMMAND_TRIGGER_WORDS:
            return True
        if len(w_norm) > 3 and w_norm[0] == 'ו' and w_norm[1:] in COMMAND_TRIGGER_WORDS:
            return True
    # Condition commands like "אם יש X תוסיף Y אם אין תשים Z"
    if "אם יש" in clean or "במידה ויש" in clean:
        return True
    return False

def get_next_global_add_order(db: Session) -> int:
    """Returns the next sequential global_add_order index."""
    max_val = db.query(func.max(Item.global_add_order)).scalar()
    return (max_val or 0) + 1

def handle_local_command(
    raw_text: str,
    categories: List[Category],
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    Executes standard commands directly in 0ms without contacting AI.
    Handles: delete all, delete checked, check all, uncheck all, delete category, delete single item.
    """
    clean = raw_text.strip()
    norm = re.sub(r'[\'\"״׳:!\.\?\-,]', '', clean).strip()

    # 1. Delete all items
    # Variations: תמחק את כל הפריטים, מחק את כל הפריטים, תמחק הכל, מחק הכל, תנקה הכל, רוקן הכל, תרוקן הכל, למחוק הכל, תמחק את כל הרשימה
    delete_all_patterns = [
        r'^(בבקשה\s+|אפשר\s+)?(ת?מחק|ת?מחוק|למחוק|ת?רוקן|לרוקן|ת?נקה|לנקות)\s+(את\s+)?(כל\s+)?(הפריטים|המוצרים|הרשימה|הכל)(\s+ברשימה)?$',
        r'^(בבקשה\s+|אפשר\s+)?(ת?מחק|ת?מחוק|למחוק|ת?רוקן|לרוקן|ת?נקה|לנקות)\s+הכל$',
        r'^(בבקשה\s+|אפשר\s+)?(רוקן|ת?רוקן|לרוקן)(\s+את)?\s+הרשימה$',
        r'^(בבקשה\s+|אפשר\s+)?(נקה|ת?נקה|לנקות)(\s+את)?\s+הרשימה$'
    ]
    for pat in delete_all_patterns:
        if re.match(pat, norm):
            db.query(Item).delete()
            db.commit()
            return {
                "success": True,
                "message": "כל הפריטים ברשימה נמחקו בהצלחה",
                "items_affected": []
            }

    # 2. Delete checked items
    # Variations: תמחק את כל המסומנים, מחק מסומנים, תמחק מסומנים, נקה מסומנים
    delete_checked_patterns = [
        r'^(בבקשה\s+|אפשר\s+)?(ת?מחק|ת?מחוק|למחוק|ת?נקה|לנקות)\s+(את\s+)?(כל\s+)?(ה?מסומנים|ה?מחוקים)(\s+ברשימה)?$',
    ]
    for pat in delete_checked_patterns:
        if re.match(pat, norm):
            checked_items = db.query(Item).filter(Item.is_checked == True).all()
            cnt = len(checked_items)
            for it in checked_items:
                db.delete(it)
            db.commit()
            return {
                "success": True,
                "message": f"נמחקו {cnt} פריטים מסומנים מהרשימה",
                "items_affected": []
            }

    # 3. Check all items
    check_all_patterns = [
        r'^(בבקשה\s+|אפשר\s+)?(ת?סמן|לסמן)\s+(את\s+)?(כל\s+)?(הפריטים|המוצרים|הרשימה|הכל)(\s+ברשימה)?$',
        r'^(בבקשה\s+|אפשר\s+)?(ת?סמן|לסמן)\s+הכל$',
    ]
    for pat in check_all_patterns:
        if re.match(pat, norm):
            items = db.query(Item).all()
            now = datetime.utcnow()
            for it in items:
                it.is_checked = True
                it.checked_at = now
            db.commit()
            return {
                "success": True,
                "message": f"כל {len(items)} הפריטים סומנו בהצלחה",
                "items_affected": [it.id for it in items]
            }

    # 4. Uncheck all items
    uncheck_all_patterns = [
        r'^(בטל|לבטל)\s+(את\s+)?(כל\s+)?(ה?סימונים|ה?סימון|ה?מסומנים)(\s+ברשימה)?$',
        r'^(בטל|לבטל)\s+(את\s+)?(ה?סימון\s+לכל\s+הפריטים|הכל)$',
        r'^(נקה|ת?נקה|לנקות)\s+סימונים$',
    ]
    for pat in uncheck_all_patterns:
        if re.match(pat, norm):
            items = db.query(Item).all()
            for it in items:
                it.is_checked = False
                it.checked_at = None
            db.commit()
            return {
                "success": True,
                "message": f"בוטל הסימון עבור {len(items)} פריטים",
                "items_affected": [it.id for it in items]
            }

    # 5. Delete category items
    # Variations: תמחק את כל הפירות וירקות, תמחק קטגוריית חלב, מחק את מוצרי חלב
    del_cat_match = re.match(r'^(ת?מחק|ת?מחוק|למחוק|ת?רוקן|ת?נקה)\s+(את\s+)?(כל\s+)?(קטגוריית\s+|קטגוריה\s+)?(.+)$', norm)
    if del_cat_match:
        target = del_cat_match.group(5).strip()
        for cat in categories:
            sim = hebrew_similarity(target, cat.name)
            if sim >= 0.75 or target in cat.name or cat.name in target:
                items_in_cat = db.query(Item).filter(Item.category_id == cat.id).all()
                cnt = len(items_in_cat)
                for it in items_in_cat:
                    db.delete(it)
                db.commit()
                return {
                    "success": True,
                    "message": f"נמחקו {cnt} פריטים מקטגוריית '{cat.name}'",
                    "items_affected": []
                }

    # 6. Delete specific single item
    # Variations: תמחק את החלב, תמחק עגבניות, תוריד את הביצים
    del_single_match = re.match(r'^(ת?מחק|ת?מחוק|למחוק|ת?וריד|להוריד)\s+(את\s+)?(.+)$', norm)
    if del_single_match:
        target_item = del_single_match.group(3).strip()
        existing_items = db.query(Item).all()
        for it in existing_items:
            sim = hebrew_similarity(target_item, it.name)
            if sim >= 0.85 or target_item == it.name:
                item_id = it.id
                db.delete(it)
                db.commit()
                return {
                    "success": True,
                    "message": f"הפריט '{it.name}' נמחק מהרשימה",
                    "items_affected": [item_id]
                }

    return None

async def process_user_input(
    raw_text: str,
    db: Session
) -> Dict[str, Any]:
    """
    Main entry point for processing input from web UI or Telegram.
    Can be a simple item list, an item with notes/conditions, or a conversational dynamic command.
    """
    raw_text = raw_text.strip()
    if not raw_text:
        return {"success": True, "message": "טקסט ריק", "items_affected": []}

    # Filter standalone headers
    if is_header_line(raw_text):
        return {"success": True, "message": "כותרת (לא נוספה כפריט)", "items_affected": []}

    categories = db.query(Category).order_by(Category.order_index.asc()).all()
    if not categories:
        return {"success": False, "message": "אין קטגוריות במערכת", "items_affected": []}

    # 1. Check if user is asking to reclassify / review items (e.g. "סיווגת הרבה דברים כשונות במקום הקטגוריות שלהם. תעבור מחדש.")
    if is_reclassify_request(raw_text):
        return await handle_reclassify_request(raw_text, categories, db)

    # 2. Filter generic conversational questions/feedback
    if is_feedback_or_conversational(raw_text):
        return {
            "success": True,
            "message": "ההודעה זוהתה כמשוב או פנייה ולא נוספה כפריט לרשימה.",
            "items_affected": []
        }

    # 3. Local command execution (0ms, 100% reliable)
    local_res = handle_local_command(raw_text, categories, db)
    if local_res is not None:
        return local_res

    # 4. Dynamic command execution via AI
    if looks_like_command(raw_text):
        return await execute_dynamic_command(raw_text, categories, db)
    else:
        return await process_items_list(raw_text, categories, db)

async def handle_reclassify_request(
    text: str,
    categories: List[Category],
    db: Session
) -> Dict[str, Any]:
    """
    Executes a re-classification review on existing items in the database.
    Sends items (especially items in 'שונות' or all items) to AI to fix their categories.
    """
    current_items = db.query(Item).all()
    if not current_items:
        return {
            "success": True,
            "message": "אין כרגע פריטים ברשימה לסידור מחדש.",
            "items_affected": []
        }

    categories_map = {c.name: c for c in categories}
    cat_id_to_name = {c.id: c.name for c in categories}

    list_representation = [
        {
            "id": it.id,
            "name": it.name,
            "quantity": it.quantity,
            "unit": it.unit,
            "note": it.note,
            "category": cat_id_to_name.get(it.category_id, "שונות")
        }
        for it in current_items
    ]

    prompt = f"""
המשתמש הזין את הבקשה הבאה לתיקון/סידור רשימת הקניות: "{text}"

מצב רשימת הקניות הנוכחית:
{json_dumps_hebrew(list_representation)}

קטגוריות מותרות בלבד במערכת:
{json_dumps_hebrew(list(categories_map.keys()))}

הוראות:
1. עיין בכל המוצרים ברשימה. עבור כל מוצר שנמצא בקטגוריה לא מתאימה או ב'שונות' (למשל מוצר חלב, בשר, ירק, מאפה וכו') - קבע מה הקטגוריה המדויקת ביותר מתוך רשימת הקטגוריות.
2. החזר אך ורק אובייקט JSON בפורמט:
{{
  "reclassified": [
    {{
      "item_id": 1,
      "name": "שם המוצר",
      "new_category": "שם הקטגוריה המדויק מתוך הרשימה"
    }}
  ],
  "summary": "הסבר בעברית על מה שתוקן והועבר"
}}
"""
    raw_res, ai_err = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה מנהל רשימת קניות מומחה בעברית האחראי על סיווג מדויק של מוצרים לקטגוריות הנכונות.",
        json_mode=True
    )

    if not raw_res:
        return {
            "success": False,
            "message": f"שגיאת AI בביצוע הסידור מחדש: {ai_err or 'שרת ה-AI אינו זמין'}. נסה שוב בעוד מספר רגעים.",
            "original_text": text,
            "items_affected": []
        }

    parsed = extract_json(raw_res)
    reclassified_list = []
    summary = "עברתי על הפריטים וסיווגתי אותם מחדש."

    if isinstance(parsed, dict):
        reclassified_list = parsed.get("reclassified") or parsed.get("actions") or []
        summary = parsed.get("summary", summary)
    elif isinstance(parsed, list):
        reclassified_list = parsed

    affected_ids = []
    for r in reclassified_list:
        if not isinstance(r, dict):
            continue
        item_id = r.get("item_id")
        new_cat_name = r.get("new_category") or r.get("category")
        target_item = None
        if item_id:
            target_item = db.query(Item).filter(Item.id == item_id).first()
        elif r.get("name"):
            target_item = db.query(Item).filter(Item.name == r.get("name")).first()

        if target_item and new_cat_name:
            cat = categories_map.get(new_cat_name)
            if not cat:
                for c in categories:
                    if hebrew_similarity(new_cat_name, c.name) >= 0.75:
                        cat = c
                        break
            if cat:
                target_item.category_id = cat.id
                db.flush()
                affected_ids.append(target_item.id)
                save_to_cache(normalize_hebrew_text(target_item.name), cat.id, 1.0, "ai", db)

    db.commit()
    return {
        "success": True,
        "message": f"{summary} (עודכנו {len(affected_ids)} פריטים)",
        "items_affected": affected_ids
    }

async def execute_dynamic_command(
    text: str,
    categories: List[Category],
    db: Session
) -> Dict[str, Any]:
    """
    Sends the current full list state + categories + user prompt to Gemini
    to interpret and execute dynamic, conditional, and bulk actions.
    If AI fails, reports error explicitly. NEVER adds command as a grocery item!
    """
    current_items = db.query(Item).all()
    categories_map = {c.name: c for c in categories}
    cat_id_to_name = {c.id: c for c in categories}

    list_representation = [
        {
            "id": it.id,
            "name": it.name,
            "quantity": it.quantity,
            "unit": it.unit,
            "note": it.note,
            "category": cat_id_to_name.get(it.category_id, "שונות"),
            "is_checked": it.is_checked
        }
        for it in current_items
    ]

    prompt = f"""
אתה מנהל רשימת קניות סופרמרקט חכם בעברית.
המשתמש הזין: "{text}"

מצב רשימת הקניות הנוכחית:
{json_dumps_hebrew(list_representation)}

קטגוריות קיימות במערכת:
{json_dumps_hebrew(list(categories_map.keys()))}

הוראות:
1. אם המשתמש מורה להוסיף מוצר עם הערה, בקשה או תנאי (למשל 'בשר טחון אבל רק אם זול', 'חלב אם במבצע') - הוסף אותו כפעולת ADD כאשר שם המוצר נקי ("בשר טחון") וההערה/תנאי בשדה note ("רק אם זול").
2. אם המשתמש מורה על תנאי כגון "אם יש מלפפון תוסיף 3 אם אין תשים 9" - בדוק ברשימה הנוכחית ובצע את הפעולה המתאימה.
3. אם המשתמש מורה למחוק קטגוריה, הכל, או לפי אות - בצע DELETE / DELETE_CATEGORY.
4. אם המשתמש מורה לתקן או להעביר קטגוריה של מוצר קיים - בצע UPDATE_CATEGORY עם item_id ו-new_category.

החזר אך ורק אובייקט JSON בפורמט:
{{
  "actions": [
    {{
      "type": "ADD", 
      "name": "שם המוצר הנקי", 
      "quantity": "כמות", 
      "unit": "יחידה", 
      "note": "הערה/תנאי", 
      "category": "שם קטגוריה מדויק"
    }},
    {{
      "type": "UPDATE_QUANTITY", 
      "item_id": 1, 
      "new_quantity": "3"
    }},
    {{
      "type": "UPDATE_CATEGORY", 
      "item_id": 1, 
      "new_category": "שם קטגוריה"
    }},
    {{
      "type": "DELETE", 
      "item_id": 1
    }},
    {{
      "type": "DELETE_CATEGORY", 
      "category_name": "שם הקטגוריה"
    }},
    {{
      "type": "DELETE_ALL"
    }}
  ],
  "summary": "הסבר קצר בעברית"
}}
"""
    raw_res, ai_err = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה מנהל רשימת קניות מבריק ומדויק בעברית. החזר תמיד JSON תקני.",
        json_mode=True
    )

    if not raw_res:
        error_msg = ai_err or "לא התקבלה תגובה משרת ה-AI."
        logger.warning(f"Gemini dynamic command failed for: '{text}' - Error: {error_msg}")
        return {
            "success": False,
            "message": f"שגיאה בביצוע הפקודה: {error_msg}",
            "original_text": text,
            "items_affected": []
        }

    parsed = extract_json(raw_res)

    actions = []
    summary = "בוצע בהצלחה"

    if isinstance(parsed, dict):
        if "actions" in parsed and isinstance(parsed["actions"], list):
            actions = parsed["actions"]
        elif "items" in parsed and isinstance(parsed["items"], list):
            actions = [{"type": "ADD", **it} for it in parsed["items"] if isinstance(it, dict)]
        summary = parsed.get("summary", summary)
    elif isinstance(parsed, list):
        for it in parsed:
            if isinstance(it, dict):
                act_type = it.get("type", "ADD")
                actions.append({"type": act_type, **it})

    if not actions:
        return {
            "success": False,
            "message": "הפקודה זוהתה, אך לא נמצאו פעולות מתאימות לביצוע ברשימה.",
            "original_text": text,
            "items_affected": []
        }

    affected_ids = []

    for act in actions:
        act_type = str(act.get("type") or "ADD").upper()

        if act_type == "ADD":
            name = act.get("name", "").strip()
            if not name:
                continue
            cat_name = act.get("category", "")
            cat = categories_map.get(cat_name)
            if not cat:
                cat, _, _ = await classify_item(name, categories, db)
            
            save_to_cache(normalize_hebrew_text(name), cat.id, 1.0, "ai", db)

            next_order = get_next_global_add_order(db)
            new_item = Item(
                name=name,
                quantity=str(act.get("quantity") or "").strip(),
                unit=str(act.get("unit") or "").strip(),
                note=str(act.get("note") or "").strip(),
                category_id=cat.id,
                is_checked=False,
                global_add_order=next_order,
                created_at=datetime.utcnow()
            )
            db.add(new_item)
            db.flush()
            affected_ids.append(new_item.id)

        elif act_type == "UPDATE_QUANTITY":
            item_id = act.get("item_id")
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                new_q = act.get("new_quantity")
                if new_q is not None:
                    item.quantity = str(new_q)
                db.flush()
                affected_ids.append(item.id)

        elif act_type in ["UPDATE_CATEGORY", "RECLASSIFY", "MOVE_CATEGORY"]:
            item_id = act.get("item_id")
            new_cat_name = act.get("new_category") or act.get("category", "")
            target_item = None
            if item_id:
                target_item = db.query(Item).filter(Item.id == item_id).first()
            elif act.get("name"):
                target_item = db.query(Item).filter(Item.name == act.get("name")).first()
            if target_item and new_cat_name:
                cat = categories_map.get(new_cat_name)
                if not cat:
                    for c in categories:
                        if hebrew_similarity(new_cat_name, c.name) >= 0.75:
                            cat = c
                            break
                if cat:
                    target_item.category_id = cat.id
                    db.flush()
                    affected_ids.append(target_item.id)
                    save_to_cache(normalize_hebrew_text(target_item.name), cat.id, 1.0, "ai", db)

        elif act_type == "DELETE":
            item_id = act.get("item_id")
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                affected_ids.append(item.id)
                db.delete(item)

        elif act_type == "DELETE_CATEGORY":
            cat_name = act.get("category_name", "")
            cat = categories_map.get(cat_name)
            if cat:
                items_to_del = db.query(Item).filter(Item.category_id == cat.id).all()
                for it in items_to_del:
                    affected_ids.append(it.id)
                    db.delete(it)

        elif act_type == "DELETE_ALL":
            items_to_del = db.query(Item).all()
            for it in items_to_del:
                affected_ids.append(it.id)
                db.delete(it)

    db.commit()
    return {
        "success": True,
        "message": summary,
        "actions_count": len(actions),
        "items_affected": affected_ids
    }

def is_certain_local_item(
    part: str,
    categories: List[Category],
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    Checks if an item can be resolved locally with absolute 100% certainty:
    - Exact match in ClassifierCache with confidence >= 0.99
    - Category is not 'שונות'
    - Has NO conversational conditional notes (e.g. 'אם...', 'רק אם...', 'אבל...')
    """
    parsed = parse_simple_item(part)
    if not parsed["name"]:
        return None

    # Any conditional/conversational note requires AI analysis
    if parsed["note"]:
        if any(w in parsed["note"] for w in ["אם", "רק", "אבל", "בתנאי", "שיהיה"]):
            return None

    cat_map = {c.id: c for c in categories}
    norm_name = normalize_hebrew_text(parsed["name"])

    exact = db.query(ClassifierCache).filter(
        ClassifierCache.item_name_normalized == norm_name,
        ClassifierCache.confidence >= 0.99
    ).first()

    if exact and exact.category_id in cat_map:
        cat = cat_map[exact.category_id]
        if cat.name != "שונות":
            return {
                "name": parsed["name"],
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
                "note": parsed["note"],
                "category": cat
            }

    return None

async def process_items_list(
    text: str,
    categories: List[Category],
    db: Session
) -> Dict[str, Any]:
    """
    Parses comma- or newline-separated items from user input.
    If ALL items are 100% certain locally (exact cache hits without conditional notes),
    resolves them locally.
    Otherwise, sends the ENTIRE message to AI. If AI fails, reports error explicitly
    and preserves user's text without falling back to uncertain local classification.
    """
    raw_parts = [p.strip() for p in re.split(r'[,;\n]+', text) if p.strip()]
    clean_parts = []
    for part in raw_parts:
        if is_header_line(part):
            continue
        local_cmd = handle_local_command(part, categories, db)
        if local_cmd:
            continue
        clean_parts.append(part)

    if not clean_parts:
        return {"success": True, "message": "אין פריטים להוספה", "items_affected": []}

    # Evaluate whether ALL items can be resolved with 100% certainty locally
    all_certain_local = True
    local_resolved_items = []
    for part in clean_parts:
        certain = is_certain_local_item(part, categories, db)
        if certain:
            local_resolved_items.append(certain)
        else:
            all_certain_local = False
            break

    if all_certain_local and len(local_resolved_items) == len(clean_parts):
        items_to_add = local_resolved_items
    else:
        # If any part requires AI, send the entire message to AI as a unified batch
        ai_resolved, ai_err = await parse_items_with_ai(clean_parts, categories, db)
        if not ai_resolved:
            error_msg = ai_err or "לא התקבלה תשובה משרת ה-AI."
            return {
                "success": False,
                "message": f"שגיאת AI בעיבוד הפריטים ({error_msg}). הטקסט הוחזר לתיבת ההקלדה.",
                "original_text": text,
                "items_affected": []
            }
        items_to_add = ai_resolved

    added_items = []
    for it_data in items_to_add:
        name = it_data["name"].strip()
        if not name:
            continue

        cat = it_data["category"]
        qty = str(it_data.get("quantity") or "").strip()
        unit = str(it_data.get("unit") or "").strip()
        note = str(it_data.get("note") or "").strip()

        existing = db.query(Item).filter(
            Item.name == name,
            Item.category_id == cat.id,
            Item.is_checked == False
        ).first()

        if existing:
            if qty:
                if existing.quantity and existing.quantity.isdigit() and qty.isdigit():
                    existing.quantity = str(int(existing.quantity) + int(qty))
                else:
                    existing.quantity = f"{existing.quantity} + {qty}".strip(" +")
            if note and not existing.note:
                existing.note = note
            added_items.append(existing.id)
        else:
            next_order = get_next_global_add_order(db)
            new_item = Item(
                name=name,
                quantity=qty,
                unit=unit,
                note=note,
                category_id=cat.id,
                is_checked=False,
                global_add_order=next_order,
                created_at=datetime.utcnow()
            )
            db.add(new_item)
            db.flush()
            added_items.append(new_item.id)

    db.commit()

    reply_msg = f"נוספו {len(added_items)} פריטים לרשימה"
    return {
        "success": True,
        "message": reply_msg,
        "items_affected": added_items
    }

def parse_simple_item(part: str) -> Dict[str, str]:
    """
    Fast local extractor for Hebrew items, including inline notes and conditions:
    e.g. 'בשר טחון אבל רק אם זול', 'חלב 3% 2', 'לחם שחור - פרוס', 'קוטג תוקף ארוך'
    """
    name = part.strip()
    quantity = ""
    unit = ""
    note = ""

    # 1. Extract notes from parentheses or dash
    dash_match = re.search(r'[-–]\s*(.+)$', name)
    if dash_match:
        note = dash_match.group(1).strip()
        name = name[:dash_match.start()].strip()

    paren_match = re.search(r'\((.+?)\)', name)
    if paren_match:
        note = f"{note} {paren_match.group(1)}".strip()
        name = re.sub(r'\(.+?\)', '', name).strip()

    # 2. Extract Hebrew conversational notes (אבל, רק אם, בתנאי ש, בלי, ללא, לא, תוקף, עדיף)
    convo_note_match = re.search(r'\s+(אבל\s+רק\s+אם\s+.+|אבל\s+.+|רק\s+אם\s+.+|אם\s+יש\s+.+|אם\s+.+|בתנאי\s+ש.+|ללא\s+.+|בלי\s+.+|לא\s+.+|תוקף\s+.+|עדיף\s+.+)$', name)
    if convo_note_match:
        extracted_note = convo_note_match.group(1).strip()
        note = f"{note} {extracted_note}".strip()
        name = name[:convo_note_match.start()].strip()

    # Strip trailing punctuation like .., :, etc.
    name = re.sub(r'[\.:!\-]+$', '', name).strip()
    note = re.sub(r'[\.:!\-]+$', '', note).strip()

    # 3. Match standalone unit words
    standalone_unit = re.search(r'\s+(תבנית|חבילה|שקית|בקבוק|קרטון|מארז|יח\'|יחידות|קופסה|קופסא|צנצנת)$', name)
    if standalone_unit:
        unit = standalone_unit.group(1)
        name = name[:standalone_unit.start()].strip()
    else:
        # Match quantity & unit at end or start
        qty_unit_end = re.search(r'\s+(\d+(?:\.\d+)?)\s*(ק"ג|קג|גרם|גר|ליטר|יח\'|יחידות|חבילה|תבנית|בקבוק|מארז|קופסה|קופסא|צנצנת)?$', name)
        if qty_unit_end:
            quantity = qty_unit_end.group(1)
            unit = qty_unit_end.group(2) or ""
            name = name[:qty_unit_end.start()].strip()
        else:
            qty_unit_start = re.match(r'^(\d+(?:\.\d+)?)\s*(ק"ג|קג|גרם|גר|ליטר|יח\'|יחידות|חבילה|תבנית|בקבוק|מארז|קופסה|קופסא|צנצנת)?\s+(.+)$', name)
            if qty_unit_start:
                quantity = qty_unit_start.group(1)
                unit = qty_unit_start.group(2) or ""
                name = qty_unit_start.group(3).strip()

    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "note": note
    }

async def parse_items_with_ai(
    items_raw: List[str],
    categories: List[Category],
    db: Session
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Uses Gemini to parse and classify complex items with notes/conditions.
    Caches classifications for future zero-cost recall.
    Returns (results, error_warning).
    """
    categories_map = {c.name: c for c in categories}
    default_cat = next((c for c in categories if c.name == "שונות"), categories[-1])

    prompt = f"""
נתח את רשימת המוצרים הבאה בעברית.
חלץ עבור כל מוצר את השם הנקי, כמות, יחידה, והערה.
אם יש תנאי או בקשה מיוחדת (כגון 'אבל רק אם זול' או 'שיהיה טרי') - שים זאת בשדה note!

דוגמאות:
"בשר טחון אבל רק אם זול" -> name: "בשר טחון", quantity: "", unit: "", note: "רק אם זול", category: "בשר, עוף, דגים וקפואים"
"עגבניות 6" -> name: "עגבניות", quantity: "6", unit: "", note: "", category: "פירות וירקות"
"מלפפונים 1 ק"ג" -> name: "מלפפונים", quantity: "1", unit: "ק\"ג", note: "", category: "פירות וירקות"
"חלב 3% 2" -> name: "חלב 3%", quantity: "2", unit: "", note: "", category: "מוצרי חלב וביצים"

מוצרים:
{chr(10).join(f"- {it}" for it in items_raw)}

קטגוריות מותרות בלבד:
{chr(10).join(f"- {c.name}" for c in categories)}

החזר אך ורק מערך JSON:
[
  {{
    "name": "שם המוצר הנקי",
    "quantity": "כמות",
    "unit": "יחידה",
    "note": "הערה",
    "category": "שם קטגוריה מדויק"
  }}
]
"""
    raw_res, ai_err = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה מנתח מוצרי קניות מומחה בעברית. החזר תמיד מערך JSON.",
        json_mode=True
    )

    if not raw_res:
        return [], (ai_err or "לא התקבלה תגובה משרת ה-AI.")

    results = []
    parsed_list = extract_json(raw_res)

    # Handle dictionary wrapped in {"items": [...]} or raw list
    if isinstance(parsed_list, dict):
        if "items" in parsed_list:
            parsed_list = parsed_list["items"]
        elif "actions" in parsed_list:
            parsed_list = parsed_list["actions"]

    if isinstance(parsed_list, list) and parsed_list:
        for item_obj in parsed_list:
            if not isinstance(item_obj, dict):
                continue
            name = item_obj.get("name", "").strip()
            if not name:
                continue
            cat_name = item_obj.get("category", "")
            cat = categories_map.get(cat_name)
            if not cat:
                best_sim = 0.0
                for c in categories:
                    sim = hebrew_similarity(cat_name, c.name)
                    if sim > best_sim:
                        best_sim = sim
                        cat = c
            if not cat:
                cat = default_cat

            save_to_cache(normalize_hebrew_text(name), cat.id, 1.0, "ai", db)

            results.append({
                "name": name,
                "quantity": str(item_obj.get("quantity") or ""),
                "unit": str(item_obj.get("unit") or ""),
                "note": str(item_obj.get("note") or ""),
                "category": cat
            })
    else:
        return [], (ai_err or "ה-AI לא החזיר מבנה תקין של פריטים.")

    return results, None

def json_dumps_hebrew(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)
