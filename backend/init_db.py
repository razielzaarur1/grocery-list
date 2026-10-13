from database import engine, SessionLocal, Base
from models import Category, Setting

DEFAULT_CATEGORIES = [
    "פירות וירקות",
    "מוצרי חלב וביצים",
    "בשר, עוף, דגים וקפואים",
    "לחם ומאפים",
    "מזון יבש, שימורים ותבלינים",
    "ניקיון והיגיינה",
    "שונות",
]

DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "telegram_bot_token": "",
    "telegram_chat_id_1": "",
    "telegram_chat_id_2": "",
}

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed categories if none exist
        existing_categories = db.query(Category).count()
        if existing_categories == 0:
            for idx, cat_name in enumerate(DEFAULT_CATEGORIES):
                category = Category(name=cat_name, order_index=idx)
                db.add(category)
            db.commit()

        # Seed settings if none exist
        for key, default_val in DEFAULT_SETTINGS.items():
            setting = db.query(Setting).filter(Setting.key == key).first()
            if not setting:
                db.add(Setting(key=key, value=default_val))
        db.commit()

        # Seed classifier cache
        try:
            from seed_cache import seed_database
            seed_database()
        except Exception as e:
            print(f"Error seeding cache: {e}")

        # Seed standard Gemini models if fewer than 2 models exist
        from models import GeminiModel
        from ai_client import STANDARD_MODELS
        from datetime import datetime
        if db.query(GeminiModel).count() < 2:
            db.query(GeminiModel).delete()
            for idx, (m_id, disp) in enumerate(STANDARD_MODELS):
                db.add(GeminiModel(
                    model_id=m_id,
                    display_name=disp,
                    rank=idx + 1,
                    is_active=True,
                    last_tested_at=datetime.utcnow()
                ))
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
