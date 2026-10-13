import json
import logging
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from models import GeminiModel, Setting

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

def get_api_key(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
    return setting.value.strip() if setting and setting.value else ""

async def test_single_model(client: httpx.AsyncClient, model_id: str, api_key: str) -> Optional[float]:
    """
    Tests if a model responds with 200 OK and measures its latency.
    Only attaches thinkingConfig for models that support it (gemini-3, gemini-2.5).
    Returns latency in seconds if 200 OK, None otherwise.
    """
    clean_id = model_id if model_id.startswith("models/") else f"models/{model_id}"
    url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"
    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": "hi"}]}],
        "generationConfig": {
            "maxOutputTokens": 5
        }
    }
    if "gemini-3" in clean_id or "gemini-2.5" in clean_id:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    t0 = asyncio.get_event_loop().time()
    try:
        resp = await client.post(url, json=payload, timeout=3.5)
        dt = asyncio.get_event_loop().time() - t0
        if resp.status_code == 200:
            logger.info(f"Model {clean_id} verified OK in {dt:.2f}s")
            return dt
        else:
            logger.warning(f"Model {clean_id} failed with status {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Model {clean_id} failed: {e}")
        return None

async def scan_and_verify_gemini_models(api_key: str, db: Session) -> List[Dict[str, Any]]:
    """
    Scans and benchmarks available Gemini models using the provided API key.
    Runs fast concurrent checks.
    Only models that successfully respond with 200 OK are saved.
    Models are ranked by their actual response latency (fastest first).
    """
    if not api_key:
        return []

    verified_models: List[Dict[str, Any]] = []

    preferred_candidates = [
        "models/gemini-3-flash-preview",
        "models/gemini-3.1-flash-lite-preview",
        "models/gemini-flash-latest",
        "models/gemini-flash-lite-latest",
        "models/gemini-3.5-flash",
        "models/gemini-3.5-flash-lite",
        "models/gemini-2.5-flash",
        "models/gemini-3.1-flash-lite",
    ]

    async with httpx.AsyncClient(timeout=6.0) as client:
        # 1. Fetch available models list from Google API
        list_url = f"{GEMINI_BASE_URL}/models?key={api_key}"
        try:
            resp = await client.get(list_url)
            if resp.status_code != 200:
                logger.error(f"Failed to list Gemini models: {resp.status_code} {resp.text}")
                return []
            data = resp.json()
            models_list = data.get("models", [])
        except Exception as e:
            logger.error(f"Error connecting to Gemini API: {e}")
            return []

        available_map = {
            m["name"]: m.get("displayName", "")
            for m in models_list
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and not any(x in m["name"].lower() for x in ["tts", "image", "clip", "robotics", "computer-use", "aqa", "embed"])
        }

        # Filter candidates that actually exist in the user's account
        cands_to_check = [m for m in preferred_candidates if m in available_map]
        if not cands_to_check:
            cands_to_check = list(available_map.keys())[:5]

        # 2. Run concurrent checks across candidates (runs in ~2-3 seconds total)
        tasks = [test_single_model(client, c, api_key) for c in cands_to_check]
        latencies = await asyncio.gather(*tasks, return_exceptions=True)

        for cand, res in zip(cands_to_check, latencies):
            if isinstance(res, (int, float)) and res is not None:
                disp = available_map.get(cand, cand.replace("models/", ""))
                verified_models.append({
                    "model_id": cand,
                    "display_name": disp,
                    "latency": float(res),
                    "is_active": True
                })

    # Default fallback if no candidate passed the ping
    if not verified_models:
        logger.warning("No candidate model passed check, setting default fallback")
        verified_models = [
            {
                "model_id": "models/gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash Preview",
                "latency": 1.5,
                "is_active": True
            }
        ]

    # Sort by latency (lowest first)
    verified_models.sort(key=lambda x: x["latency"])

    # 3. Save only verified models into DB
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
    Calls Gemini API using verified active models in rank order.
    Disables thinking tokens (thinkingBudget=0) for instant 1-2s response on Gemini 3.
    Automatically falls back to secondary model if primary fails.
    Returns (result_text, error_message).
    """
    api_key = get_api_key(db)
    if not api_key:
        logger.warning("No Gemini API key configured.")
        return None, "לא הוגדר מפתח Gemini API בהגדרות"

    # Fetch active models ordered by rank
    models = db.query(GeminiModel).filter(GeminiModel.is_active == True).order_by(GeminiModel.rank.asc()).all()

    # If no models cached yet, perform a quick scan
    if not models:
        await scan_and_verify_gemini_models(api_key, db)
        models = db.query(GeminiModel).filter(GeminiModel.is_active == True).order_by(GeminiModel.rank.asc()).all()

    model_ids = [m.model_id for m in models] if models else [
        "models/gemini-3-flash-preview"
    ]

    last_error_msg: Optional[str] = None

    async with httpx.AsyncClient(timeout=6.0) as client:
        for m_id in model_ids:
            clean_id = m_id if m_id.startswith("models/") else f"models/{m_id}"
            url = f"{GEMINI_BASE_URL}/{clean_id}:generateContent?key={api_key}"

            payload: Dict[str, Any] = {
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1000
                }
            }

            # Disable thinking reasoning tokens on Gemini 3 / 2.5 models
            if "gemini-3" in clean_id or "gemini-2.5" in clean_id:
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
                elif resp.status_code == 429:
                    last_error_msg = "התקבלה שגיאת הגבלת קצב או חריגה ממכסה מה-AI (שגיאה 429). אנא נסה שוב בעוד מספר רגעים או בדוק את מפתח ה-API."
                    logger.warning(f"Gemini 429 Rate Limit on {clean_id}: {resp.text[:120]}")
                elif resp.status_code == 503:
                    last_error_msg = "שרתי ה-AI של גוגל עמוסים זמנית (שגיאה 503). אנא נסה שוב בעוד מספר רגעים."
                    logger.warning(f"Gemini 503 on {clean_id}: {resp.text[:120]}")
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
