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

def get_all_api_keys(db: Session) -> List[str]:
    """Returns all configured Gemini API keys as a list of strings."""
    setting = db.query(Setting).filter(Setting.key == "gemini_api_keys").first()
    keys = []
    if setting and setting.value:
        try:
            parsed = json.loads(setting.value)
            if isinstance(parsed, list):
                keys = [str(k).strip() for k in parsed if str(k).strip()]
        except Exception:
            keys = [k.strip() for k in setting.value.split(",") if k.strip()]

    # Fallback to single gemini_api_key setting if list was empty
    if not keys:
        single = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        if single and single.value and single.value.strip():
            keys = [single.value.strip()]

    # Preserve order while removing duplicates
    seen = set()
    unique_keys = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique_keys.append(k)
    return unique_keys

def save_all_api_keys(keys: List[str], db: Session) -> List[str]:
    """Saves the list of API keys and updates primary gemini_api_key."""
    clean_keys = []
    seen = set()
    for k in keys:
        ck = str(k).strip()
        if ck and ck not in seen:
            seen.add(ck)
            clean_keys.append(ck)

    row = db.query(Setting).filter(Setting.key == "gemini_api_keys").first()
    if row:
        row.value = json.dumps(clean_keys)
    else:
        db.add(Setting(key="gemini_api_keys", value=json.dumps(clean_keys)))

    primary = clean_keys[0] if clean_keys else ""
    row_primary = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
    if row_primary:
        row_primary.value = primary
    else:
        db.add(Setting(key="gemini_api_key", value=primary))

    db.commit()
    return clean_keys

def get_api_key(db: Session) -> str:
    """Returns primary API key for backward compatibility."""
    keys = get_all_api_keys(db)
    return keys[0] if keys else ""

def get_thinking_config(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Minimizes internal thinking/reasoning latency for models that support it.
    Gemini 2.5, 3, and Flash Lite models spend dozens of seconds generating
    internal thoughts unless thinkingBudget is set.
    Setting thinkingBudget=1 reduces latency from 30-60s to 1-2s.
    Models that do not support thinkingConfig will return 400, which we catch
    and retry without thinkingConfig.
    """
    clean_id = model_id.lower()
    if any(k in clean_id for k in ["gemini-3", "gemini-2.5", "flash-lite", "thinking"]):
        return {"thinkingBudget": 1}
    return None

async def test_single_model(client: httpx.AsyncClient, model_id: str, api_key: str) -> Dict[str, Any]:
    """
    Tests if a model responds with a specific API key.
    Returns: model_id, status, status_message, latency, is_active
    """
    clean_id = model_id if model_id.startswith("models/") else f"models/{model_id}"
    url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"
    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": "1"}]}],
        "generationConfig": {"maxOutputTokens": 2}
    }
    tc = get_thinking_config(clean_id)
    if tc:
        payload["generationConfig"]["thinkingConfig"] = tc

    t0 = asyncio.get_event_loop().time()
    try:
        resp = await client.post(url, json=payload, timeout=4.0)
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
            resp2 = await client.post(url, json=payload, timeout=4.0)
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
            "status_message": "חריגת זמן תגובה (>4.0s)",
            "latency": 4.0,
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

async def test_model_across_keys(client: httpx.AsyncClient, model_id: str, api_keys: List[str]) -> Dict[str, Any]:
    """
    Tests a model across the provided API keys.
    If Key 1 hits 429, checks Key 2. If any key gives 200, the model is marked active!
    """
    last_res = None
    for k_idx, key in enumerate(api_keys):
        res = await test_single_model(client, model_id, key)
        if res.get("status") == "active":
            if len(api_keys) > 1:
                res["status_message"] = f"תקין ופעיל (במפתח #{k_idx + 1}, {res['latency']}s)"
            return res
        last_res = res
        # If it's 404 / unavailable, no key will change that
        if res.get("status") == "unavailable":
            return res

    return last_res or {
        "model_id": model_id,
        "status": "unavailable",
        "status_message": "לא הגיב",
        "latency": 0.0,
        "is_active": False
    }

async def scan_and_verify_gemini_models(db: Session, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Scans ALL available models returned by Google API (/models), tests each one across
    all configured API keys, classifies status, and stores all models in the database.
    """
    all_keys = get_all_api_keys(db)
    if api_key and api_key not in all_keys:
        all_keys.insert(0, api_key)

    if not all_keys:
        return []

    available_map: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Fetch available models list from Google API using first working key
        for key in all_keys:
            list_url = f"{GEMINI_BASE_URL}/models?key={key}"
            try:
                resp = await client.get(list_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        disp = m.get("displayName", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            if "gemini" in name.lower() and not any(x in name.lower() for x in [
                                "tts", "clip", "robotics", "computer-use", "aqa", "embed", "transcribe", "banana", "lyria", "argon", "gemma"
                            ]):
                                available_map[name] = disp or name.replace("models/", "")
                    if available_map:
                        break
            except Exception as e:
                logger.error(f"Error querying Gemini /models endpoint with key {key[:4]}...: {e}")

        if not available_map:
            for pm in PREFERRED_CORE_MODELS:
                available_map[pm] = pm.replace("models/", "").replace("-", " ").title()

        candidate_ids = list(available_map.keys())

        # 2. Test candidate models concurrently across available keys in batches
        results: List[Dict[str, Any]] = []
        batch_size = 8
        for i in range(0, len(candidate_ids), batch_size):
            batch = candidate_ids[i:i + batch_size]
            tasks = [test_model_across_keys(client, m_id, all_keys) for m_id in batch]
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
    Calls Gemini API routing across ALL configured API keys and fast Gemini Flash models.
    Supports dynamic generous timeout (25s - 60s) based on prompt complexity to prevent
    premature timeout failures on large grocery lists or complex instructions.
    Prioritizes models currently marked active in DB.
    If Key 1 hits 429 quota exhaustion, immediately fails over to Key 2, Key 3, etc.
    Returns (result_text, error_message).
    """
    api_keys = get_all_api_keys(db)
    if not api_keys:
        logger.warning("No Gemini API keys configured.")
        return None, "לא הוגדר אף מפתח Gemini API בהגדרות"

    # Compute generous dynamic timeout: minimum 25.0s, scaling up to 60.0s for long texts
    prompt_len = len(prompt)
    dynamic_timeout = max(25.0, min(60.0, 25.0 + (prompt_len / 40.0)))

    # Fetch models currently active in DB, ordered by lowest latency
    active_db_models: List[str] = []
    try:
        active_db_models = [
            m.model_id for m in db.query(GeminiModel).filter(
                GeminiModel.status == "active",
                GeminiModel.model_id.ilike("%gemini%")
            ).order_by(GeminiModel.latency.asc()).all()
        ]
    except Exception as e:
        logger.warning(f"Could not read active models from DB: {e}")

    # Build prioritized candidate models list
    candidate_model_ids: List[str] = list(active_db_models)
    for default_m in [
        "models/gemini-flash-lite-latest",
        "models/gemini-3-flash-preview",
        "models/gemini-2.5-flash",
        "models/gemini-flash-latest",
        "models/gemini-3.5-flash-lite",
        "models/gemini-3.5-flash",
        "models/gemini-3.8-flash",
        "models/gemini-3.1-flash-lite-preview",
    ]:
        if default_m not in candidate_model_ids:
            candidate_model_ids.append(default_m)

    exhausted_keys_count = 0
    last_error_msg: Optional[str] = None

    async with httpx.AsyncClient(timeout=dynamic_timeout) as client:
        # Loop across all configured API keys
        for key_idx, api_key in enumerate(api_keys):
            masked_key = (api_key[:4] + "..." + api_key[-4:]) if len(api_key) > 8 else api_key
            logger.info(f"Attempting prompt with API key #{key_idx + 1} ({masked_key}), timeout={dynamic_timeout:.1f}s...")
            key_had_quota_exhaustion = False
            consecutive_timeouts = 0

            for m_id in candidate_model_ids:
                clean_id = m_id if m_id.startswith("models/") else f"models/{m_id}"
                url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"

                payload: Dict[str, Any] = {
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]}
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 4096
                    }
                }

                tc = get_thinking_config(clean_id)
                if tc:
                    payload["generationConfig"]["thinkingConfig"] = tc

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
                                logger.info(f"Success with API key #{key_idx + 1} on model {clean_id}")
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
                                    logger.info(f"Success with API key #{key_idx + 1} on model {clean_id}")
                                    return parts[0].get("text", ""), None
                    elif resp.status_code == 429:
                        key_had_quota_exhaustion = True
                        logger.warning(f"API key #{key_idx + 1} hit 429 Rate Limit on {clean_id}. Advancing to next API key immediately...")
                        # This key is exhausted for today! Break immediately to the next key!
                        break
                    elif resp.status_code == 503:
                        last_error_msg = "שרתי ה-AI של גוגל עמוסים זמנית (שגיאה 503)."
                        logger.warning(f"Key #{key_idx + 1} 503 on {clean_id}. Trying next model...")
                    else:
                        last_error_msg = f"שגיאת AI משרת גוגל (קוד {resp.status_code})."
                        logger.warning(f"Key #{key_idx + 1} call to {clean_id} returned {resp.status_code}.")
                except httpx.TimeoutException:
                    consecutive_timeouts += 1
                    last_error_msg = f"זמן ההמתנה לשרת ה-AI פג (Timeout לאחר {dynamic_timeout:.0f} שניות)."
                    logger.warning(f"Timeout calling Gemini model {clean_id} with key #{key_idx + 1} after {dynamic_timeout:.1f}s.")
                    # If 2 models in a row time out after 25+ seconds each, don't hold the user indefinitely
                    if consecutive_timeouts >= 2:
                        logger.warning("Two consecutive models timed out. Skipping remaining models on this key.")
                        break
                except Exception as e:
                    last_error_msg = f"שגיאת תקשורת עם ה-AI: {str(e)}"
                    logger.warning(f"Error calling Gemini model {clean_id} with key #{key_idx + 1}: {e}.")

            if key_had_quota_exhaustion:
                exhausted_keys_count += 1
                last_error_msg = f"מפתח API #{key_idx + 1} הגיע למגבלת המכסה היומית (שגיאה 429)."

    # If all configured keys hit 429
    if exhausted_keys_count >= len(api_keys):
        return None, f"כל מפתחות ה-API שהוגדרו ({len(api_keys)} מפתחות) הגיעו למגבלת המכסה היומית (שגיאה 429 - Quota Exceeded). הטקסט נשמר בשורת הקלט. באפשרותך להוסיף מפתח נוסף בהגדרות."

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
