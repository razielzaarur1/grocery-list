import asyncio
import sys
from database import SessionLocal
from models import Item, Category
from command_processor import process_user_input

sys.stdout.reconfigure(encoding='utf-8')

async def run_command_tests():
    db = SessionLocal()
    db.query(Item).delete()
    db.commit()

    # 1. Add some initial items
    print("\n--- 1. Adding initial items ---")
    res = await process_user_input("חלב\nלחם\nביצים", db)
    print("Add result:", res)
    count = db.query(Item).count()
    print(f"Total items in DB: {count}")

    # 2. Test feedback phrase (should NOT be added as item)
    print("\n--- 2. Sending feedback phrase ---")
    res = await process_user_input("יש הרבה פריטים בשונות שאמורים להיות במקומות אחרים", db)
    print("Feedback result:", res)
    count = db.query(Item).count()
    print(f"Total items in DB after feedback: {count}")
    assert count == 3, f"Expected 3 items, got {count}!"

    # 3. Test check all command
    print("\n--- 3. Command: תסמן הכל ---")
    res = await process_user_input("תסמן הכל", db)
    print("Check all result:", res)
    checked_count = db.query(Item).filter(Item.is_checked == True).count()
    print(f"Checked items: {checked_count} / {count}")
    assert checked_count == 3

    # 4. Test delete all command with punctuation
    print("\n--- 4. Command: תמחק את כל הפריטים. ---")
    res = await process_user_input("תמחק את כל הפריטים.", db)
    print("Delete all result:", res)
    count = db.query(Item).count()
    print(f"Total items in DB after delete all: {count}")
    assert count == 0, f"Expected 0 items, got {count}!"

    # 5. Test command: בבקשה תמחק את כל הפריטים
    print("\n--- 5. Command: בבקשה תמחק את כל הפריטים ---")
    await process_user_input("עגבניה\nמלפפון", db)
    assert db.query(Item).count() == 2
    res = await process_user_input("בבקשה תמחק את כל הפריטים", db)
    print("Polite delete result:", res)
    assert db.query(Item).count() == 0

    print("\nALL COMMAND TESTS PASSED SUCCESSFULLY!")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_command_tests())
