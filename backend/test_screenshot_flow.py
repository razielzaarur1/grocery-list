
import asyncio
import sys
from database import SessionLocal
from models import Item, Category
from command_processor import process_user_input

sys.stdout.reconfigure(encoding='utf-8')

text = """
קניות
מלפפון
עגבניה
גמבה
בצל סגול
בצל לבן
בטטה
קישוא
גזר
חציל
ביצים
פיתות
לחמניות
גבינה בולגרית מעודנת
גבינה לבנה/יוגורט
קוטג תוקף ארוך
טופו
תפוח
כרוב לבן/סגול
חמוציות לא מסוכרים
שקדים
חמאת בוטנים
בשר טחון/חזה עוף
תות/מנגו קפוא אם מחיר טוב
שניצל עוף טוב אם מחיר טוב
שתייה מתוקה אשכוליות/שוופס/ספרייט/קולה..
"""

async def run_flow():
    db = SessionLocal()
    # Clear items first for clean test
    db.query(Item).delete()
    db.commit()

    print("Sending text to process_user_input...", flush=True)
    res = await process_user_input(text, db)
    print("Result:", res)

    items = db.query(Item).all()
    categories = {c.id: c.name for c in db.query(Category).all()}

    print(f"\n--- TOTAL ITEMS ADDED: {len(items)} ---")
    shonot_count = 0
    for it in items:
        cat_name = categories.get(it.category_id, "לא ידוע")
        if cat_name == "שונות":
            shonot_count += 1
        note_str = f" [הערה: {it.note}]" if it.note else ""
        print(f"[{cat_name}] {it.name}{note_str}")

    print(f"\nItems in 'שונות': {shonot_count} (out of {len(items)})")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_flow())
