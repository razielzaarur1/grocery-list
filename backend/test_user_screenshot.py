import asyncio
from database import SessionLocal
from models import Category, ClassifierCache
from classifier import check_local_cache
from command_processor import parse_simple_item, process_user_input
from hebrew_utils import normalize_hebrew_text, hebrew_similarity

db = SessionLocal()
categories = db.query(Category).all()

test_items = [
    "קניות",
    "גבינה בולגרית מעודנת",
    "גבינה לבנה/יוגורט",
    "קוטג תוקף ארוך",
    "טופו",
    "תפוח",
    "כרוב לבן/סגול",
    "חמוציות לא מסוכרים",
    "שקדים",
    "חמאת בוטנים",
    "בשר טחון/חזה עוף",
    "תות/מנגו קפוא אם מחיר טוב",
    "שניצל עוף טוב אם מחיר טוב",
    "שתייה מתוקה אשכוליות/שוופס/ספרייט/קולה..",
    "יש הרבה פריטים בשונות שאמורים להיות במקומות אחרים"
]

print("--- LOCAL CACHE MATCH TEST ---")
for it in test_items:
    simple = parse_simple_item(it)
    res = check_local_cache(simple["name"], categories, db, threshold=0.99)
    if res:
        print(f"OK: {it} -> {res[0].name} (conf={res[1]:.2f})".encode('ascii', 'backslashreplace').decode('ascii'))
    else:
        norm = normalize_hebrew_text(simple["name"])
        # Check best match
        all_cached = db.query(ClassifierCache).all()
        best_sim = 0
        best_match = None
        for c in all_cached:
            sim = hebrew_similarity(norm, c.item_name_normalized)
            if sim > best_sim:
                best_sim = sim
                best_match = c
        match_info = f"best sim={best_sim:.2f} with '{best_match.item_name_normalized if best_match else ''}'"
        print(f"MISS: {it} (name='{simple['name']}', note='{simple['note']}') [{match_info}]".encode('ascii', 'backslashreplace').decode('ascii'))
