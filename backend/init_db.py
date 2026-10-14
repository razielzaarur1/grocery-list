from database import engine, SessionLocal, Base
import models
from models import Category, Setting, DeviceToken

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
    "pin_code": "1234",
    "failed_attempts": "0",
    "is_locked": "false",
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

        # Add new columns to gemini_models if they don't exist
        from sqlalchemy import text
        for col, col_type in [("status", "VARCHAR(50) DEFAULT 'active'"), ("status_message", "VARCHAR(255) DEFAULT ''"), ("latency", "FLOAT DEFAULT 0.0")]:
            try:
                db.execute(text(f"ALTER TABLE gemini_models ADD COLUMN {col} {col_type}"))
                db.commit()
            except Exception:
                db.rollback()

        # Seed standard Gemini models if fewer than 2 models exist
        from models import GeminiModel
        from ai_client import PREFERRED_CORE_MODELS
        from datetime import datetime
        if db.query(GeminiModel).count() < 2:
            db.query(GeminiModel).delete()
            for idx, m_id in enumerate(PREFERRED_CORE_MODELS):
                disp = m_id.replace("models/", "").replace("-", " ").title()
                db.add(GeminiModel(
                    model_id=m_id,
                    display_name=disp,
                    rank=idx + 1,
                    is_active=True,
                    status="active",
                    status_message="תקין ומוגדר",
                    latency=1.5,
                    last_tested_at=datetime.utcnow()
                ))
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
