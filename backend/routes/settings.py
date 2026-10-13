from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from database import get_db
from models import Setting, GeminiModel
from ai_client import (
    scan_and_verify_gemini_models,
    get_all_api_keys,
    save_all_api_keys,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_api_keys: Optional[List[str]] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id_1: Optional[str] = None
    telegram_chat_id_2: Optional[str] = None

class AddApiKeyRequest(BaseModel):
    key: str

class DeleteApiKeyRequest(BaseModel):
    key: str

@router.get("")
def get_settings(db: Session = Depends(get_db)):
    """Returns current settings, all API keys, and verified Gemini models list."""
    settings_rows = db.query(Setting).all()
    settings_dict = {s.key: s.value for s in settings_rows}

    all_keys = get_all_api_keys(db)
    keys_list = [
        {
            "key": k,
            "masked_key": (k[:4] + "..." + k[-4:]) if len(k) > 8 else k,
            "is_primary": idx == 0
        }
        for idx, k in enumerate(all_keys)
    ]
    primary_key = all_keys[0] if all_keys else ""
    masked_primary = (primary_key[:4] + "..." + primary_key[-4:]) if len(primary_key) > 8 else primary_key

    models = db.query(GeminiModel).order_by(GeminiModel.rank.asc()).all()
    models_list = [
        {
            "id": m.id,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "rank": m.rank,
            "is_active": m.is_active,
            "status": getattr(m, "status", "active") or "active",
            "status_message": getattr(m, "status_message", "") or "",
            "latency": getattr(m, "latency", 0.0) or 0.0,
            "last_tested": m.last_tested_at.isoformat() if m.last_tested_at else None
        }
        for m in models
    ]

    return {
        "gemini_api_key": primary_key,
        "masked_gemini_key": masked_primary,
        "gemini_api_keys": keys_list,
        "telegram_bot_token": settings_dict.get("telegram_bot_token", ""),
        "telegram_chat_id_1": settings_dict.get("telegram_chat_id_1", ""),
        "telegram_chat_id_2": settings_dict.get("telegram_chat_id_2", ""),
        "gemini_models": models_list
    }

@router.post("")
async def update_settings(req: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Updates settings and triggers Gemini model scan if keys changed."""
    key_changed = False
    current_keys = get_all_api_keys(db)

    if req.gemini_api_keys is not None:
        new_keys = [k.strip() for k in req.gemini_api_keys if k.strip()]
        if new_keys != current_keys:
            key_changed = True
            save_all_api_keys(new_keys, db)
    elif req.gemini_api_key is not None:
        new_val = req.gemini_api_key.strip()
        if not current_keys or current_keys[0] != new_val:
            key_changed = True
            other_keys = [k for k in current_keys if k != new_val]
            save_all_api_keys([new_val] + other_keys if new_val else other_keys, db)

    if req.telegram_bot_token is not None:
        _set_setting(db, "telegram_bot_token", req.telegram_bot_token.strip())

    if req.telegram_chat_id_1 is not None:
        _set_setting(db, "telegram_chat_id_1", req.telegram_chat_id_1.strip())

    if req.telegram_chat_id_2 is not None:
        _set_setting(db, "telegram_chat_id_2", req.telegram_chat_id_2.strip())

    db.commit()

    scanned_models = []
    if key_changed:
        scanned_models = await scan_and_verify_gemini_models(db)

    return {
        "success": True,
        "scanned_models_count": len(scanned_models) if key_changed else None
    }

@router.post("/keys")
async def add_api_key(req: AddApiKeyRequest, db: Session = Depends(get_db)):
    """Appends a new Gemini API key, validates, and triggers rescan."""
    new_k = req.key.strip()
    if not new_k:
        raise HTTPException(status_code=400, detail="מפתח ה-API ריק")

    keys = get_all_api_keys(db)
    if new_k in keys:
        return {"success": True, "message": "המפתח כבר קיים במערכת", "keys_count": len(keys)}

    keys.append(new_k)
    save_all_api_keys(keys, db)
    await scan_and_verify_gemini_models(db)
    return {"success": True, "message": "מפתח API נוסף בהצלחה", "keys_count": len(keys)}

@router.delete("/keys")
async def delete_api_key(req: DeleteApiKeyRequest, db: Session = Depends(get_db)):
    """Removes a Gemini API key and rescans remaining keys."""
    target_k = req.key.strip()
    keys = get_all_api_keys(db)
    filtered = [k for k in keys if k != target_k]
    save_all_api_keys(filtered, db)
    await scan_and_verify_gemini_models(db)
    return {"success": True, "message": "המפתח הוסר", "keys_count": len(filtered)}

@router.post("/gemini/scan")
async def scan_models(db: Session = Depends(get_db)):
    """Manually scans and tests all Gemini models across all configured keys."""
    keys = get_all_api_keys(db)
    if not keys:
        raise HTTPException(status_code=400, detail="לא הוגדר אף מפתח Gemini API")

    models = await scan_and_verify_gemini_models(db)
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
