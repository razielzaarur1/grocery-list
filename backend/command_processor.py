import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Item, Category
from classifier import classify_item, save_to_cache, record_user_correction, check_local_cache
from hebrew_utils import normalize_hebrew_text, hebrew_similarity
from ai_client import call_gemini_with_fallback, extract_json

logger = logging.getLogger(__name__)

# Heuristic list of explicit command words in Hebrew
COMMAND_TRIGGER_WORDS = [
    "תמחק", "מחק", "תמחוק", "תמחקי", "תמחקו",
    "תוריד", "הורד", "תורידי", "תורידו",
    "תוסיף", "הוסף", "תוסיפי", "תוסיפו",
    "תחליף", "החלף", "תעביר", "העבר", "שנה", "תשנה",
    "תנקה", "נקה", "סמן", "תסמן", "בטל",
    "כל ה", "שמתחיל", "שנגמר", "שמכיל", "תרוקן"
]

def looks_like_command(text: str) -> bool:
    """
    Checks if the user input is an explicit command rather than items to add.
    """
    clean = text.strip()
    words = clean.split()
    for w in words:
        w_norm = re.sub(r'[\'\"״׳]', '', w).strip()
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

    categories = db.query(Category).order_by(Category.order_index.asc()).all()
    if not categories:
        return {"success": False, "message": "אין קטגוריות במערכת", "items_affected": []}

    if looks_like_command(raw_text):
        return await execute_dynamic_command(raw_text, categories, db)
    else:
        return await process_items_list(raw_text, categories, db)

async def execute_dynamic_command(
    text: str,
    categories: List[Category],
    db: Session
) -> Dict[str, Any]:
    """
    Sends the current full list state + categories + user prompt to Gemini
    to interpret and execute dynamic, conditional, and bulk actions.
    Falls back gracefully to item parser if Gemini response is non-standard.
    """
    current_items = db.query(Item).all()
    categories_map = {c.name: c for c in categories}
    cat_id_to_name = {c.id: c.name for c in categories}

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
    raw_res = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה מנהל רשימת קניות מבריק ומדויק בעברית. החזר תמיד JSON תקני.",
        json_mode=True
    )

    parsed = extract_json(raw_res) if raw_res else None

    # Robust normalization of actions from parsed JSON
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

    # If Gemini failed or didn't return valid actions, fallback to standard items parser!
    if not actions:
        logger.warning(f"Could not parse actions from Gemini response. Falling back to process_items_list for: {text}")
        return await process_items_list(text, categories, db)

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

async def process_items_list(
    text: str,
    categories: List[Category],
    db: Session
) -> Dict[str, Any]:
    """
    Parses comma- or newline-separated items from user input.
    Extracts name, quantity, unit, and notes.
    """
    raw_parts = [p.strip() for p in re.split(r'[,;\n]+', text) if p.strip()]
    if not raw_parts:
        return {"success": True, "message": "אין פריטים להוספה", "items_affected": []}

    added_items = []
    items_to_ai = []
    local_resolved = []

    for part in raw_parts:
        parsed_simple = parse_simple_item(part)
        
        # Check local cache first (runs in 0ms, zero API cost)
        cached_match = check_local_cache(parsed_simple["name"], categories, db, threshold=0.99)
        if cached_match and not (parsed_simple["note"] and len(parsed_simple["note"]) > 30):
            cat, conf = cached_match
            local_resolved.append({
                "name": parsed_simple["name"],
                "quantity": parsed_simple["quantity"],
                "unit": parsed_simple["unit"],
                "note": parsed_simple["note"],
                "category": cat
            })
            continue

        # Collect un-cached items for a single batch AI call
        items_to_ai.append(part)

    if items_to_ai:
        ai_resolved = await parse_items_with_ai(items_to_ai, categories, db)
        local_resolved.extend(ai_resolved)

    for it_data in local_resolved:
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
    return {
        "success": True,
        "message": f"נוספו {len(added_items)} פריטים לרשימה",
        "items_affected": added_items
    }

def parse_simple_item(part: str) -> Dict[str, str]:
    """
    Fast local extractor for Hebrew items, including inline notes and conditions:
    e.g. 'בשר טחון אבל רק אם זול', 'חלב 3% 2', 'לחם שחור - פרוס'
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

    # 2. Extract Hebrew conversational notes (אבל, רק אם, בתנאי ש, בלי, ללא)
    convo_note_match = re.search(r'\s+(אבל\s+.+|רק\s+אם\s+.+|אם\s+יש\s+.+|בתנאי\s+ש.+|ללא\s+.+|בלי\s+.+)$', name)
    if convo_note_match:
        extracted_note = convo_note_match.group(1).strip()
        note = f"{note} {extracted_note}".strip()
        name = name[:convo_note_match.start()].strip()

    # 3. Match standalone unit words
    standalone_unit = re.search(r'\s+(תבנית|חבילה|שקית|בקבוק|קרטון|מארז|יח\'|יחידות)$', name)
    if standalone_unit:
        unit = standalone_unit.group(1)
        name = name[:standalone_unit.start()].strip()
    else:
        # Match quantity & unit at end or start
        qty_unit_end = re.search(r'\s+(\d+(?:\.\d+)?)\s*(ק"ג|קג|גרם|גר|ליטר|יח\'|יחידות|חבילה|תבנית|בקבוק|מארז)?$', name)
        if qty_unit_end:
            quantity = qty_unit_end.group(1)
            unit = qty_unit_end.group(2) or ""
            name = name[:qty_unit_end.start()].strip()
        else:
            qty_unit_start = re.match(r'^(\d+(?:\.\d+)?)\s*(ק"ג|קג|גרם|גר|ליטר|יח\'|יחידות|חבילה|תבנית|בקבוק|מארז)?\s+(.+)$', name)
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
) -> List[Dict[str, Any]]:
    """
    Uses Gemini to parse and classify complex items with notes/conditions.
    Caches classifications for future zero-cost recall.
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
    raw_res = await call_gemini_with_fallback(
        prompt=prompt,
        db=db,
        system_instruction="אתה מנתח מוצרי קניות מומחה בעברית. החזר תמיד מערך JSON.",
        json_mode=True
    )

    results = []
    parsed_list = extract_json(raw_res) if raw_res else None

    # Handle dictionary wrapped in {"items": [...]} or raw list
    if isinstance(parsed_list, dict):
        if "items" in parsed_list:
            parsed_list = parsed_list["items"]
        elif "actions" in parsed_list:
            parsed_list = parsed_list["actions"]

    if isinstance(parsed_list, list):
        for item_obj in parsed_list:
            if not isinstance(item_obj, dict):
                continue
            name = item_obj.get("name", "").strip()
            if not name:
                continue
            cat_name = item_obj.get("category", "")
            cat = categories_map.get(cat_name)
            if not cat:
                cat, _, _ = await classify_item(name, categories, db)
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
        # Fallback if Gemini failed
        for raw in items_raw:
            simple = parse_simple_item(raw)
            cat, _, _ = await classify_item(simple["name"], categories, db)
            results.append({
                "name": simple["name"],
                "quantity": simple["quantity"],
                "unit": simple["unit"],
                "note": simple["note"],
                "category": cat
            })

    return results

def json_dumps_hebrew(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)
