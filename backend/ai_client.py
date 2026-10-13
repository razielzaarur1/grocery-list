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

# Standard verified models supported by Google Gemini
STANDARD_MODELS = [
    ("models/gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview"),
    ("models/gemini-3-flash-preview", "Gemini 3 Flash Preview"),
    ("models/gemini-flash-latest", "Gemini Flash Latest"),
    ("models/gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("models/gemini-3.5-flash", "Gemini 3.5 Flash"),
    ("models/gemini-3.8-flash", "Gemini 3.8 Flash"),
    ("models/gemini-flash-lite-latest", "Gemini Flash-Lite Latest"),
    ("models/gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
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

async def test_single_model(client: httpx.AsyncClient, model_id: str, api_key: str) -> Tuple[Optional[float], bool]:
    """
    Tests if a model responds and measures its latency.
    Returns (latency_seconds, is_active).
    - 200 OK: Returns (dt, True)
    - 429 Rate Limit / 503 Overloaded: Returns (2.5, True) because the model exists and is valid on the account!
    - 404 Not Found (e.g. discontinued model): Returns (None, False)
    - 400 Bad Request: Retries without thinkingConfig, returns (None, False) if still fails.
    """
    clean_id = model_id if model_id.startswith("models/") else f"models/{model_id}"
    url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"
    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": "1"}]}],
        "generationConfig": {
            "maxOutputTokens": 2
        }
    }
    if should_disable_thinking(clean_id):
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    t0 = asyncio.get_event_loop().time()
    try:
        resp = await client.post(url, json=payload, timeout=5.0)
        dt = asyncio.get_event_loop().time() - t0
        if resp.status_code == 200:
            logger.info(f"Model {clean_id} verified OK in {dt:.2f}s")
            return dt, True
        elif resp.status_code in (429, 503):
            # Model exists and is available for this key, but currently throttled or busy
            logger.info(f"Model {clean_id} is active (status {resp.status_code})")
            return 2.5, True
        elif resp.status_code == 400 and "thinkingConfig" in payload.get("generationConfig", {}):
            del payload["generationConfig"]["thinkingConfig"]
            resp2 = await client.post(url, json=payload, timeout=5.0)
            dt2 = asyncio.get_event_loop().time() - t0
            if resp2.status_code == 200:
                return dt2, True
            elif resp2.status_code in (429, 503):
                return 2.5, True
            return None, False
        elif resp.status_code == 404:
            logger.warning(f"Model {clean_id} returned 404 (unavailable)")
            return None, False
        else:
            logger.warning(f"Model {clean_id} returned status {resp.status_code}")
            return None, False
    except httpx.TimeoutException:
        logger.warning(f"Model {clean_id} timed out during test, keeping as active")
        return 3.0, True
    except Exception as e:
        logger.warning(f"Model {clean_id} error: {e}")
        return 3.0, True

async def scan_and_verify_gemini_models(api_key: str, db: Session) -> List[Dict[str, Any]]:
    """
    Scans and benchmarks available Gemini models using the provided API key.
    Fetches the full model list from Google API, filters valid chat models,
    tests them, and persists all active models to the database ranked by latency.
    NEVER wipes models to leave only 1 model if temporary rate limits occur.
    """
    if not api_key:
        return []

    available_map: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        # 1. Fetch available models list from Google API
        list_url = f"{GEMINI_BASE_URL}/models?key={api_key}"
        try:
            resp = await client.get(list_url)
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("models", [])
                for m in models_list:
                    name = m.get("name", "")
                    disp = m.get("displayName", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        # Skip specialized non-chat / media models
                        if not any(x in name.lower() for x in [
                            "tts", "image", "clip", "robotics", "computer-use",
                            "aqa", "embed", "transcribe", "banana", "lyria", "argon", "deep-research", "gemma"
                        ]):
                            available_map[name] = disp or name.replace("models/", "")
            else:
                logger.error(f"Failed to list Gemini models: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Error querying Gemini /models endpoint: {e}")

        # If available_map is empty (e.g. list API failed or was throttled), fall back to standard models
        if not available_map:
            available_map = {m_id: name for m_id, name in STANDARD_MODELS}

        # Build candidate list: prioritize our standard curated models
        candidates_to_check: List[str] = []
        for m_id, _ in STANDARD_MODELS:
            if m_id in available_map and m_id not in candidates_to_check:
                candidates_to_check.append(m_id)

        if not candidates_to_check:
            candidates_to_check = [m_id for m_id, _ in STANDARD_MODELS]

        # 2. Test candidates concurrently with 5s timeout
        tasks = [test_single_model(client, c, api_key) for c in candidates_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified_models: List[Dict[str, Any]] = []
        for cand, res in zip(candidates_to_check, results):
            if isinstance(res, tuple):
                lat, is_active = res
                if is_active:
                    disp = available_map.get(cand, cand.replace("models/", ""))
                    verified_models.append({
                        "model_id": cand,
                        "display_name": disp,
                        "latency": float(lat) if lat is not None else 2.5,
                        "is_active": True
                    })

    # Ensure all core standard models that exist in available_map are retained
    existing_ids = {m["model_id"] for m in verified_models}
    for m_id, disp in STANDARD_MODELS:
        if m_id in available_map and m_id not in existing_ids:
            verified_models.append({
                "model_id": m_id,
                "display_name": disp,
                "latency": 3.0,
                "is_active": True
            })

    # If completely empty, seed standard models
    if not verified_models:
        for m_id, disp in STANDARD_MODELS:
            verified_models.append({
                "model_id": m_id,
                "display_name": disp,
                "latency": 2.0,
                "is_active": True
            })

    # Sort by latency (lowest first)
    verified_models.sort(key=lambda x: x["latency"])

    # 3. Save all verified models into DB with updated ranks
    db.query(GeminiModel).delete()
    for idx, vm in enumerate(verified_models):
        model_record = GeminiModel(
            model_id=vm["model_id"],
            display_name=vm["display_name"],
            rank=idx + 1,
            is_active=True,
            last_tested_at=datetime.utcnow()
        )
        db.add(model_record)
    db.commit()

    return verified_models

async def call_gemini_with_fallback(
    prompt: str,
    db: Session,
    system_instruction: Optional[str] = None,
    json_mode: bool = True
) -> tuple[Optional[str], Optional[str]]:
    """
    Calls Gemini API using active models in rank order.
    Disables thinking tokens (thinkingBudget=0) on supported models for instant response.
    Automatically falls back across all available models if any model is rate-limited (429) or busy (503).
    Returns (result_text, error_message).
    """
    api_key = get_api_key(db)
    if not api_key:
        logger.warning("No Gemini API key configured.")
        return None, "לא הוגדר מפתח Gemini API בהגדרות"

    # Fetch active models ordered by rank
    models = db.query(GeminiModel).filter(GeminiModel.is_active == True).order_by(GeminiModel.rank.asc()).all()

    model_ids = [m.model_id for m in models] if models else []
    # Always include all standard models in sequence as fallbacks
    for m_id, _ in STANDARD_MODELS:
        if m_id not in model_ids:
            model_ids.append(m_id)

    last_error_msg: Optional[str] = None

    async with httpx.AsyncClient(timeout=4.5) as client:
        for idx, m_id in enumerate(model_ids):
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

            # Only disable thinking tokens on models that support thinkingBudget
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
                    # In case a model rejected thinkingConfig, retry immediately without it
                    del payload["generationConfig"]["thinkingConfig"]
                    resp2 = await client.post(url, json=payload)
                    if resp2.status_code == 200:
                        data = resp2.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", ""), None
                    logger.warning(f"Model {clean_id} failed with 400: {resp2.text[:120]}")
                elif resp.status_code == 429:
                    last_error_msg = "התקבלה שגיאת הגבלת קצב או חריגה ממכסה מה-AI (שגיאה 429). אנא המתן מספר שניות ונסה שוב."
                    logger.warning(f"Gemini 429 Rate Limit on {clean_id}: {resp.text[:120]}. Falling back to next model...")
                elif resp.status_code == 503:
                    last_error_msg = "שרתי ה-AI של גוגל עמוסים זמנית (שגיאה 503). אנא נסה שוב בעוד מספר רגעים."
                    logger.warning(f"Gemini 503 on {clean_id}: {resp.text[:120]}. Falling back to next model...")
                else:
                    last_error_msg = f"שגיאת AI משרת גוגל (קוד {resp.status_code})."
                    logger.warning(f"Gemini call to {clean_id} returned {resp.status_code}: {resp.text[:120]}.")
            except httpx.TimeoutException:
                last_error_msg = "זמן ההמתנה לשרת ה-AI פג (Timeout)."
                logger.warning(f"Timeout calling Gemini model {clean_id}.")
            except Exception as e:
                last_error_msg = f"שגיאת תקשורת עם ה-AI: {str(e)}"
                logger.warning(f"Error calling Gemini model {clean_id}: {e}.")

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
