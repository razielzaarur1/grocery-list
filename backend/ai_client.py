import json
import logging
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from models import GeminiModel, Setting

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Standard core models preferred for fast Hebrew parsing
PREFERRED_CORE_MODELS = [
    "models/gemini-3-flash-preview",
    "models/gemini-flash-latest",
    "models/gemini-2.5-flash",
    "models/gemini-3.5-flash",
    "models/gemini-3.8-flash",
    "models/gemini-3.1-flash-lite-preview",
    "models/gemini-flash-lite-latest",
    "models/gemini-3.1-flash-lite",
    "models/gemini-3.5-flash-lite",
]

def get_api_key(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
    return setting.value.strip() if setting and setting.value else ""

def should_disable_thinking(model_id: str) -> bool:
    """
    Checks if model supports thinkingConfig with thinkingBudget=0.
    Lite models and standard flash models fail with 400 Bad Request if thinkingConfig is attached.
    Only gemini-3 non-lite models support thinkingBudget=0 safely.
    """
    clean_id = model_id.lower()
    return "gemini-3" in clean_id and "lite" not in clean_id

async def test_single_model(client: httpx.AsyncClient, model_id: str, api_key: str) -> Dict[str, Any]:
    """
    Tests if a model responds, measures latency, and determines exact status.
    Returns:
      model_id, status, status_message, latency, is_active
    """
    clean_id = model_id if model_id.startswith("models/") else f"models/{model_id}"
    url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"
    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": "1"}]}],
        "generationConfig": {"maxOutputTokens": 2}
    }
    if should_disable_thinking(clean_id):
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    t0 = asyncio.get_event_loop().time()
    try:
        resp = await client.post(url, json=payload, timeout=2.5)
        dt = asyncio.get_event_loop().time() - t0
        if resp.status_code == 200:
            return {
                "model_id": clean_id,
                "status": "active",
                "status_message": f"תקין וזמין ({dt:.2f}s)",
                "latency": round(dt, 2),
                "is_active": True
            }
        elif resp.status_code == 429:
            return {
                "model_id": clean_id,
                "status": "quota_exhausted",
                "status_message": "הגיע למגבלת מכסה יומית (שגיאה 429)",
                "latency": round(dt, 2),
                "is_active": False
            }
        elif resp.status_code == 503:
            return {
                "model_id": clean_id,
                "status": "overloaded",
                "status_message": "עומס זמני בשרתי גוגל (שגיאה 503)",
                "latency": round(dt, 2),
                "is_active": False
            }
        elif resp.status_code == 400 and "thinkingConfig" in payload.get("generationConfig", {}):
            del payload["generationConfig"]["thinkingConfig"]
            resp2 = await client.post(url, json=payload, timeout=2.5)
            dt2 = asyncio.get_event_loop().time() - t0
            if resp2.status_code == 200:
                return {
                    "model_id": clean_id,
                    "status": "active",
                    "status_message": f"תקין וזמין ({dt2:.2f}s)",
                    "latency": round(dt2, 2),
                    "is_active": True
                }
            elif resp2.status_code == 429:
                return {
                    "model_id": clean_id,
                    "status": "quota_exhausted",
                    "status_message": "הגיע למגבלת מכסה יומית (שגיאה 429)",
                    "latency": round(dt2, 2),
                    "is_active": False
                }
            return {
                "model_id": clean_id,
                "status": "unavailable",
                "status_message": f"שגיאה {resp2.status_code}",
                "latency": 0.0,
                "is_active": False
            }
        elif resp.status_code in (404, 400):
            return {
                "model_id": clean_id,
                "status": "unavailable",
                "status_message": "מודל אינו זמין לחשבון זה",
                "latency": 0.0,
                "is_active": False
            }
        else:
            return {
                "model_id": clean_id,
                "status": "unavailable",
                "status_message": f"קוד {resp.status_code}",
                "latency": 0.0,
                "is_active": False
            }
    except httpx.TimeoutException:
        return {
            "model_id": clean_id,
            "status": "timeout",
            "status_message": "חריגת זמן תגובה (>2.5s)",
            "latency": 3.0,
            "is_active": False
        }
    except Exception as e:
        return {
            "model_id": clean_id,
            "status": "unavailable",
            "status_message": str(e)[:40],
            "latency": 0.0,
            "is_active": False
        }

async def scan_and_verify_gemini_models(api_key: str, db: Session) -> List[Dict[str, Any]]:
    """
    Scans ALL available models returned by Google API (/models), tests each one,
    classifies its status (active, quota_exhausted, overloaded, timeout, unavailable),
    and stores all models in the database.
    """
    if not api_key:
        return []

    available_map: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Fetch available models list from Google API
        list_url = f"{GEMINI_BASE_URL}/models?key={api_key}"
        try:
            resp = await client.get(list_url)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    disp = m.get("displayName", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        # Skip purely non-text models
                        if not any(x in name.lower() for x in [
                            "tts", "clip", "robotics", "computer-use", "aqa", "embed", "transcribe", "banana", "lyria", "argon"
                        ]):
                            available_map[name] = disp or name.replace("models/", "")
            else:
                logger.error(f"Failed to list Gemini models: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Error querying Gemini /models endpoint: {e}")

        if not available_map:
            # Fallback map if listing failed
            for pm in PREFERRED_CORE_MODELS:
                available_map[pm] = pm.replace("models/", "").replace("-", " ").title()

        candidate_ids = list(available_map.keys())

        # 2. Test candidate models concurrently in small batches
        results: List[Dict[str, Any]] = []
        batch_size = 8
        for i in range(0, len(candidate_ids), batch_size):
            batch = candidate_ids[i:i + batch_size]
            tasks = [test_single_model(client, m_id, api_key) for m_id in batch]
            batch_res = await asyncio.gather(*tasks, return_exceptions=True)
            for m_id, r in zip(batch, batch_res):
                disp = available_map.get(m_id, m_id.replace("models/", ""))
                if isinstance(r, dict):
                    r["display_name"] = disp
                    results.append(r)
                else:
                    results.append({
                        "model_id": m_id,
                        "display_name": disp,
                        "status": "unavailable",
                        "status_message": "שגיאת בדיקה",
                        "latency": 0.0,
                        "is_active": False
                    })
            if i + batch_size < len(candidate_ids):
                await asyncio.sleep(0.2)

    # Sort priority:
    # 1. active (lowest latency)
    # 2. quota_exhausted (valid models currently throttled)
    # 3. overloaded (503)
    # 4. timeout
    # 5. unavailable
    def sort_key(item):
        st = item.get("status", "")
        order = {
            "active": 1,
            "quota_exhausted": 2,
            "overloaded": 3,
            "timeout": 4,
            "unavailable": 5
        }.get(st, 6)
        # Prioritize preferred core models inside same status group
        m_id = item.get("model_id", "")
        pref = 0 if m_id in PREFERRED_CORE_MODELS else 1
        lat = item.get("latency", 99.0) or 99.0
        return (order, pref, lat)

    results.sort(key=sort_key)

    # 3. Save all models into DB
    db.query(GeminiModel).delete()
    for idx, r in enumerate(results):
        model_record = GeminiModel(
            model_id=r["model_id"],
            display_name=r["display_name"],
            rank=idx + 1,
            is_active=(r["status"] in ("active", "quota_exhausted")),
            status=r["status"],
            status_message=r["status_message"],
            latency=r.get("latency", 0.0),
            last_tested_at=datetime.utcnow()
        )
        db.add(model_record)
    db.commit()

    return results

async def call_gemini_with_fallback(
    prompt: str,
    db: Session,
    system_instruction: Optional[str] = None,
    json_mode: bool = True
) -> tuple[Optional[str], Optional[str]]:
    """
    Calls Gemini API using the top fast Gemini Flash models in priority order.
    Disables thinking tokens (thinkingBudget=0) on supported models for instant response.
    Returns (result_text, error_message).
    """
    api_key = get_api_key(db)
    if not api_key:
        logger.warning("No Gemini API key configured.")
        return None, "לא הוגדר מפתח Gemini API בהגדרות"

    # Always use the top reliable fast Gemini Flash models
    candidate_model_ids = [
        "models/gemini-3-flash-preview",
        "models/gemini-flash-latest",
        "models/gemini-2.5-flash",
        "models/gemini-3.5-flash",
        "models/gemini-3.8-flash",
        "models/gemini-3.1-flash-lite-preview",
    ]

    quota_errors_count = 0
    last_error_msg: Optional[str] = None

    async with httpx.AsyncClient(timeout=3.5) as client:
        for idx, m_id in enumerate(candidate_model_ids):
            clean_id = m_id if m_id.startswith("models/") else f"models/{m_id}"
            url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"

            payload: Dict[str, Any] = {
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1500
                }
            }

            if should_disable_thinking(clean_id):
                payload["generationConfig"]["thinkingConfig"] = {
                    "thinkingBudget": 0
                }

            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"

            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", ""), None
                elif resp.status_code == 400 and "thinkingConfig" in payload.get("generationConfig", {}):
                    del payload["generationConfig"]["thinkingConfig"]
                    resp2 = await client.post(url, json=payload)
                    if resp2.status_code == 200:
                        data = resp2.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", ""), None
                elif resp.status_code == 429:
                    quota_errors_count += 1
                    last_error_msg = "שרתי Google Gemini החזירו שגיאת מכסה (429 Quota Exceeded) - המכסה היומית של מפתח ה-API מוצתה לחלוטין (20 בקשות). הטקסט נשמר בשורת הקלט."
                    logger.warning(f"Gemini 429 on {clean_id}: {resp.text[:120]}")
                    # If already 2 consecutive models returned 429, don't keep hanging
                    if quota_errors_count >= 2:
                        return None, last_error_msg
                elif resp.status_code == 503:
                    last_error_msg = "שרתי ה-AI של גוגל עמוסים זמנית (שגיאה 503). אנא נסה שוב בעוד מספר רגעים."
                    logger.warning(f"Gemini 503 on {clean_id}: {resp.text[:120]}")
                else:
                    last_error_msg = f"שגיאת AI משרת גוגל (קוד {resp.status_code})."
                    logger.warning(f"Gemini call to {clean_id} returned {resp.status_code}: {resp.text[:120]}.")
            except httpx.TimeoutException:
                if not last_error_msg:
                    last_error_msg = "זמן ההמתנה לשרת ה-AI פג (Timeout)."
                logger.warning(f"Timeout calling Gemini model {clean_id}.")
            except Exception as e:
                if not last_error_msg:
                    last_error_msg = f"שגיאת תקשורת עם ה-AI: {str(e)}"
                logger.warning(f"Error calling Gemini model {clean_id}: {e}.")

    # If any model gave 429, prioritize reporting 429 rather than timeout
    if quota_errors_count > 0:
        return None, "שרתי Google Gemini החזירו שגיאת מכסה (429 Quota Exceeded) - המכסה היומית של מפתח ה-API מוצתה לחלוטין (20 בקשות). הטקסט נשמר בשורת הקלט."

    return None, (last_error_msg or "שירות ה-AI אינו זמין כרגע. אנא נסה שוב מאוחר יותר.")

def extract_json(raw_text: str) -> Optional[Any]:
    """Robustly parses JSON from raw response text (handles markdown fences if present)."""
    if not raw_text:
        return None
    raw_text = raw_text.strip()

    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None
