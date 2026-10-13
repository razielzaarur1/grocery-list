import os
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Category, Item, ClassifierCache, Setting
from hebrew_utils import normalize_hebrew_text, hebrew_similarity
from classifier import save_to_cache, record_user_correction
from command_processor import looks_like_command, parse_simple_item

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def test_db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # Seed test categories
    cats = [
        Category(name="פירות וירקות", order_index=0),
        Category(name="מוצרי חלב וביצים", order_index=1),
        Category(name="שונות", order_index=2),
    ]
    db.add_all(cats)
    db.commit()

    yield db
    db.close()

def test_hebrew_normalization():
    assert normalize_hebrew_text("עגבניה") == normalize_hebrew_text("עגבנייה")
    assert normalize_hebrew_text("חלב 3%") == normalize_hebrew_text("חלב 3%")
    # Check final letter normalization
    assert normalize_hebrew_text("לימון") == normalize_hebrew_text("לימונ")

def test_hebrew_similarity():
    # Identical with single/double yod
    sim = hebrew_similarity("עגבניה", "עגבנייה")
    assert sim >= 0.95

    # Singular and plural
    sim_plural = hebrew_similarity("מלפפונים", "מלפפון")
    assert sim_plural >= 0.95

    # Prefix 'ה'
    sim_prefix = hebrew_similarity("החלב", "חלב")
    assert sim_prefix >= 0.95

def test_command_detection():
    assert looks_like_command("תמחק את כל הירקות") == True
    assert looks_like_command("אם יש מלפפון תוסיף 3") == True
    assert looks_like_command("תוסיף 2 חלב") == True
    assert looks_like_command("עגבניות 6, מלפפונים 1 ק\"ג, בננות") == False
    assert looks_like_command("חלב 2") == False

def test_parse_simple_item():
    res1 = parse_simple_item("עגבניות 6")
    assert res1["name"] == "עגבניות"
    assert res1["quantity"] == "6"

    res2 = parse_simple_item("מלפפונים 1 ק\"ג")
    assert res2["name"] == "מלפפונים"
    assert res2["quantity"] == "1"
    assert res2["unit"] == "ק\"ג"

    res3 = parse_simple_item("לחם מחמצת (פרוס)")
    assert res3["name"] == "לחם מחמצת"
    assert res3["note"] == "פרוס"

    res4 = parse_simple_item("בשר טחון אבל רק אם זול")
    assert res4["name"] == "בשר טחון"
    assert "רק אם זול" in res4["note"]

def test_item_ordering_and_checked_logic(test_db):
    cat = test_db.query(Category).first()

    # Add 3 items in order
    item1 = Item(name="עגבניות", category_id=cat.id, global_add_order=1, is_checked=False)
    item2 = Item(name="מלפפונים", category_id=cat.id, global_add_order=2, is_checked=False)
    item3 = Item(name="בננות", category_id=cat.id, global_add_order=3, is_checked=False)
    test_db.add_all([item1, item2, item3])
    test_db.commit()

    # Check item1 first
    t1 = datetime.utcnow() - timedelta(minutes=5)
    item1.is_checked = True
    item1.checked_at = t1

    # Check item3 second (most recently checked)
    t2 = datetime.utcnow()
    item3.is_checked = True
    item3.checked_at = t2
    test_db.commit()

    # Query items for category
    items = test_db.query(Item).filter(Item.category_id == cat.id).all()
    unchecked = [i for i in items if not i.is_checked]
    checked = [i for i in items if i.is_checked]

    unchecked.sort(key=lambda x: x.global_add_order)
    checked.sort(key=lambda x: x.checked_at, reverse=True)
    ordered = unchecked + checked

    # Unchecked first: item2
    assert ordered[0].name == "מלפפונים"

    # Checked items: item3 (most recently checked) should be first among checked
    assert ordered[1].name == "בננות"

    # item1 (checked earlier) should be at the very bottom
    assert ordered[2].name == "עגבניות"

def test_cache_learning(test_db):
    cat_fruits = test_db.query(Category).filter(Category.name == "פירות וירקות").first()
    cat_dairy = test_db.query(Category).filter(Category.name == "מוצרי חלב וביצים").first()

    # User re-assigns tomato to dairy (as a test case for user learning)
    record_user_correction("עגבניה", cat_dairy.id, test_db)

    # Check cache
    cached = test_db.query(ClassifierCache).filter(
        ClassifierCache.item_name_normalized == normalize_hebrew_text("עגבניה")
    ).first()

    assert cached is not None
    assert cached.category_id == cat_dairy.id
    assert cached.confidence == 1.0
    assert cached.source == "user"

@pytest.mark.anyio
async def test_cached_items_processing_without_ai(test_db):
    from command_processor import process_user_input

    cat_fruits = test_db.query(Category).filter(Category.name == "פירות וירקות").first()
    # Pre-train classifier cache with high confidence
    save_to_cache(normalize_hebrew_text("עגבניות"), cat_fruits.id, 1.0, "user", test_db)
    save_to_cache(normalize_hebrew_text("מלפפונים"), cat_fruits.id, 1.0, "user", test_db)

    # Process items that match cache
    res = await process_user_input("עגבניות 6, מלפפונים 1 ק\"ג", test_db)
    assert res["success"] == True

    items = test_db.query(Item).all()
    assert len(items) == 2
    names = [i.name for i in items]
    assert "עגבניות" in names
    assert "מלפפונים" in names

