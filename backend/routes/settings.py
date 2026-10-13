from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from database import get_db
from models import Setting, GeminiModel
from ai_client import scan_and_verify_gemini_models

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id_1: Optional[str] = None
    telegram_chat_id_2: Optional[str] = None

@router.get("")
def get_settings(db: Session = Depends(get_db)):
    """Returns current settings and verified Gemini models list."""
    settings_rows = db.query(Setting).all()
    settings_dict = {s.key: s.value for s in settings_rows}

    # Hide part of secret keys for safety in UI
    gemini_key = settings_dict.get("gemini_api_key", "")
    masked_gemini = (gemini_key[:4] + "..." + gemini_key[-4:]) if len(gemini_key) > 8 else gemini_key

    models = db.query(GeminiModel).order_by(GeminiModel.rank.asc()).all()
    if len(models) < 2:
        from ai_client import STANDARD_MODELS
        from datetime import datetime
        db.query(GeminiModel).delete()
        models = []
        for idx, (m_id, disp) in enumerate(STANDARD_MODELS):
            rec = GeminiModel(
                model_id=m_id,
                display_name=disp,
                rank=idx + 1,
                is_active=True,
                last_tested_at=datetime.utcnow()
            )
            db.add(rec)
            models.append(rec)
        db.commit()
    models_list = [
        {
            "id": m.id,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "rank": m.rank,
            "is_active": m.is_active,
            "last_tested": m.last_tested_at.isoformat() if m.last_tested_at else None
        }
        for m in models
    ]

    return {
        "gemini_api_key": gemini_key,
        "masked_gemini_key": masked_gemini,
        "telegram_bot_token": settings_dict.get("telegram_bot_token", ""),
        "telegram_chat_id_1": settings_dict.get("telegram_chat_id_1", ""),
        "telegram_chat_id_2": settings_dict.get("telegram_chat_id_2", ""),
        "gemini_models": models_list
    }

@router.post("")
async def update_settings(req: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Updates settings and triggers Gemini model scan if key changed."""
    updated = {}
    key_changed = False

    if req.gemini_api_key is not None:
        curr_key = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        new_val = req.gemini_api_key.strip()
        if not curr_key or curr_key.value != new_val:
            key_changed = True
        _set_setting(db, "gemini_api_key", new_val)
        updated["gemini_api_key"] = new_val

    if req.telegram_bot_token is not None:
        _set_setting(db, "telegram_bot_token", req.telegram_bot_token.strip())
        updated["telegram_bot_token"] = req.telegram_bot_token.strip()

    if req.telegram_chat_id_1 is not None:
        _set_setting(db, "telegram_chat_id_1", req.telegram_chat_id_1.strip())
        updated["telegram_chat_id_1"] = req.telegram_chat_id_1.strip()

    if req.telegram_chat_id_2 is not None:
        _set_setting(db, "telegram_chat_id_2", req.telegram_chat_id_2.strip())
        updated["telegram_chat_id_2"] = req.telegram_chat_id_2.strip()

    db.commit()

    scanned_models = []
    # If Gemini API key changed or was set, scan & verify models
    if key_changed and req.gemini_api_key:
        scanned_models = await scan_and_verify_gemini_models(req.gemini_api_key.strip(), db)

    return {
        "success": True,
        "scanned_models_count": len(scanned_models) if key_changed else None
    }

@router.post("/gemini/scan")
async def scan_models(db: Session = Depends(get_db)):
    """Manually scans and tests all Gemini models."""
    key_row = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
    key = key_row.value.strip() if key_row and key_row.value else ""
    if not key:
        raise HTTPException(status_code=400, detail="לא הוגדר מפתח Gemini API")

    models = await scan_and_verify_gemini_models(key, db)
    return {
        "success": True,
        "models": models
    }

@router.post("/telegram/test")
async def test_telegram(db: Session = Depends(get_db)):
    """Sends a test ping message to the configured Telegram chat IDs."""
    token_row = db.query(Setting).filter(Setting.key == "telegram_bot_token").first()
    id1_row = db.query(Setting).filter(Setting.key == "telegram_chat_id_1").first()
    id2_row = db.query(Setting).filter(Setting.key == "telegram_chat_id_2").first()

    token = token_row.value.strip() if token_row and token_row.value else ""
    if not token:
        raise HTTPException(status_code=400, detail="לא הוגדר טוקן לבוט של טלגרם")

    chat_ids = []
    if id1_row and id1_row.value.strip():
        chat_ids.append(id1_row.value.strip())
    if id2_row and id2_row.value.strip():
        chat_ids.append(id2_row.value.strip())

    if not chat_ids:
        raise HTTPException(status_code=400, detail="לא הוגדר אף Chat ID")

    sent = 0
    errors = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                resp = await client.post(url, json={
                    "chat_id": cid,
                    "text": "🛒 בדיקת חיבור: בוט רשימת הקניות מחובר בהצלחה!"
                })
                if resp.status_code == 200:
                    sent += 1
                else:
                    errors.append(f"Chat ID {cid}: {resp.text}")
            except Exception as e:
                errors.append(f"Chat ID {cid}: {str(e)}")

    return {
        "success": sent > 0,
        "sent_count": sent,
        "errors": errors
    }

def _set_setting(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
