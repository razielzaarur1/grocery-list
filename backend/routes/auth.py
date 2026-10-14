import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Setting, DeviceToken

router = APIRouter(prefix="/api/auth", tags=["auth"])

class VerifyPinRequest(BaseModel):
    pin: str
    device_name: Optional[str] = "מכשיר מורשה"

class ChangePinRequest(BaseModel):
    new_pin: str = Field(..., min_length=4, max_length=6)

def _get_setting_val(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row and row.value is not None else default

def _set_setting_val(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = str(value)
    else:
        db.add(Setting(key=key, value=str(value)))
    db.commit()

@router.get("/status")
def get_auth_status(
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Checks if current device is authenticated, if system is locked out,
    and returns current PIN length.
    """
    auth_token = x_device_token or token
    is_authenticated = False

    if auth_token:
        device = db.query(DeviceToken).filter(DeviceToken.token == auth_token.strip()).first()
        if device:
            is_authenticated = True
            device.last_used_at = datetime.utcnow()
            db.commit()

    is_locked = _get_setting_val(db, "is_locked", "false").lower() == "true"
    failed_attempts = int(_get_setting_val(db, "failed_attempts", "0") or "0")
    pin = _get_setting_val(db, "pin_code", "1234").strip() or "1234"

    return {
        "is_authenticated": is_authenticated,
        "is_locked": is_locked,
        "pin_length": len(pin),
        "failed_attempts": failed_attempts,
        "max_attempts": 3
    }

@router.post("/verify-pin")
def verify_pin(req: VerifyPinRequest, db: Session = Depends(get_db)):
    """
    Verifies user-entered PIN.
    If correct: generates persistent device token, resets failed attempts.
    If wrong 3 times: permanently locks system until unlocked via port 8889.
    """
    is_locked = _get_setting_val(db, "is_locked", "false").lower() == "true"
    if is_locked:
        raise HTTPException(
            status_code=403,
            detail="המערכת נעולה עקב 3 ניסיונות שגויים. יש לשחרר נעילה מקומית דרך פורט 8889."
        )

    stored_pin = _get_setting_val(db, "pin_code", "1234").strip() or "1234"
    entered_pin = req.pin.strip()

    if entered_pin == stored_pin:
        # Success: reset failed attempts
        _set_setting_val(db, "failed_attempts", "0")
        
        # Generate persistent token for this device
        new_token = secrets.token_hex(24)
        device = DeviceToken(
            token=new_token,
            device_name=req.device_name or "מכשיר מורשה",
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        db.add(device)
        db.commit()

        return {
            "success": True,
            "token": new_token,
            "message": "הסיסמה נכונה, המכשיר אומת ונשמר לצמיתות!"
        }
    else:
        # Failure: increment counter
        failed_count = int(_get_setting_val(db, "failed_attempts", "0") or "0") + 1
        _set_setting_val(db, "failed_attempts", str(failed_count))

        if failed_count >= 3:
            _set_setting_val(db, "is_locked", "true")
            return {
                "success": False,
                "is_locked": True,
                "attempts_left": 0,
                "message": "הקשת סיסמה שגויה 3 פעמים! המערכת ננעלה. יש לשחרר נעילה מקומית מפורט 8889."
            }
        else:
            attempts_left = 3 - failed_count
            return {
                "success": False,
                "is_locked": False,
                "attempts_left": attempts_left,
                "message": f"קוד שגוי. נותרו {attempts_left} ניסיונות."
            }

@router.post("/change-pin")
def change_pin(req: ChangePinRequest, db: Session = Depends(get_db)):
    """
    Changes PIN code. Must be 4-6 digits.
    """
    new_pin = req.new_pin.strip()
    if not (new_pin.isdigit() and 4 <= len(new_pin) <= 6):
        raise HTTPException(status_code=400, detail="קוד ה-PIN חייב להכיל בין 4 ל-6 ספרות בלבד")

    _set_setting_val(db, "pin_code", new_pin)
    return {
        "success": True,
        "message": "קוד ה-PIN שונה בהצלחה",
        "pin_length": len(new_pin)
    }

@router.post("/unlock")
def unlock_system(db: Session = Depends(get_db)):
    """
    Unlocks system and resets failed attempts. Used by the local recovery portal on port 8889.
    """
    _set_setting_val(db, "is_locked", "false")
    _set_setting_val(db, "failed_attempts", "0")
    return {
        "success": True,
        "message": "נעילת המערכת שוחררה בהצלחה! האתר פתוח לשימוש."
    }

@router.get("/recovery-info")
def get_recovery_info(db: Session = Depends(get_db)):
    """
    Status information specifically for the local recovery dashboard (port 8889).
    """
    is_locked = _get_setting_val(db, "is_locked", "false").lower() == "true"
    failed_attempts = int(_get_setting_val(db, "failed_attempts", "0") or "0")
    pin = _get_setting_val(db, "pin_code", "1234").strip() or "1234"
    devices_count = db.query(DeviceToken).count()

    return {
        "is_locked": is_locked,
        "failed_attempts": failed_attempts,
        "current_pin": pin,
        "devices_count": devices_count
    }
