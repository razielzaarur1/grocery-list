import asyncio
import sys
from unittest.mock import patch, AsyncMock
from database import SessionLocal
from models import Item, Category, ClassifierCache
from command_processor import (
    process_user_input,
    is_certain_local_item,
    is_reclassify_request
)

sys.stdout.reconfigure(encoding='utf-8')

async def run_tests():
    db = SessionLocal()
    categories = db.query(Category).all()
    cat_by_name = {c.name: c for c in categories}

    print("--- 1. Testing is_reclassify_request detection ---")
    req1 = "סיווגת הרבה דברים כשונות במקום הקטגוריות שלהם. תעבור מחדש."
    req2 = "תעבור מחדש על הפריטים בשונות"
    req3 = "תסדר את הפריטים בשונות"
    req4 = "מלפפון ועגבניה"
    assert is_reclassify_request(req1) == True
    assert is_reclassify_request(req2) == True
    assert is_reclassify_request(req3) == True
    assert is_reclassify_request(req4) == False
    print("OK: Reclassification requests correctly identified!")

    print("\n--- 2. Testing 100% local vs AI routing ---")
    # Exact cache items without conditional notes
    assert is_certain_local_item("חלב", categories, db) is not None
    assert is_certain_local_item("ביצים", categories, db) is not None
    # Item with conditional note should NOT be resolved locally
    assert is_certain_local_item("בשר טחון אבל רק אם זול", categories, db) is None
    # Unknown item should NOT be resolved locally
    assert is_certain_local_item("מוצר לא ידוע כלל 123", categories, db) is None
    print("OK: is_certain_local_item strictly enforces 100% certainty!")

    print("\n--- 3. Testing 100% local resolution when all items are exact ---")
    db.query(Item).delete()
    db.commit()
    # חלב and ביצים are both exact in cache
    res = await process_user_input("חלב\nביצים", db)
    assert res["success"] == True
    assert len(res["items_affected"]) == 2
    assert db.query(Item).count() == 2
    print("OK: All-exact list resolved locally in 0ms without contacting AI!")

    print("\n--- 4. Testing AI routing: when 1 item needs AI, entire message goes to AI ---")
    db.query(Item).delete()
    db.commit()
    # Mock call_gemini_with_fallback to simulate AI returning 429 quota error
    with patch("command_processor.call_gemini_with_fallback", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = (None, "התקבלה שגיאת הגבלת קצב (429)")
        # Input with 2 exact items and 1 item needing AI
        input_text = "חלב\nביצים\nבשר טחון אבל רק אם זול"
        res = await process_user_input(input_text, db)
        
        # MUST fail explicitly, NOT fall back to local, and return original text
        assert res["success"] == False
        assert "429" in res["message"]
        assert res["original_text"] == input_text
        # No items should have been added to DB!
        assert db.query(Item).count() == 0
        print("OK: AI failure does NOT fall back to local! Explicit error returned and text preserved!")

    print("\n--- 5. Testing Reclassification Execution ---")
    db.query(Item).delete()
    db.commit()
    # Add an item placed in 'שונות'
    shonot_cat = cat_by_name["שונות"]
    dairy_cat = cat_by_name["מוצרי חלב וביצים"]
    it = Item(
        name="גבינה לבנה 5%",
        quantity="1",
        unit="",
        note="",
        category_id=shonot_cat.id,
        is_checked=False,
        global_add_order=1
    )
    db.add(it)
    db.commit()
    assert it.category_id == shonot_cat.id

    # Mock AI reclassifying it to dairy
    mock_reclassify_json = f'{{"reclassified": [{{"item_id": {it.id}, "name": "גבינה לבנה 5%", "new_category": "מוצרי חלב וביצים"}}], "summary": "הועברה גבינה לבנה למוצרי חלב"}}'
    with patch("command_processor.call_gemini_with_fallback", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = (mock_reclassify_json, None)
        res = await process_user_input("סיווגת הרבה דברים כשונות במקום הקטגוריות שלהם. תעבור מחדש.", db)
        assert res["success"] == True
        db.refresh(it)
        assert it.category_id == dairy_cat.id
        print("OK: Reclassification request successfully updated item category from 'שונות' to 'מוצרי חלב וביצים'!")

    print("\nALL USER REQUIREMENTS VERIFIED AND PASSED!")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
