import sqlite3
import time
import httpx

conn = sqlite3.connect('data/grocery.db')
c = conn.cursor()
c.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
key = c.fetchone()[0]

test_models = [
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-exp",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-flash-latest",
    "models/gemini-1.5-flash-8b",
    "models/gemini-1.5-pro",
    "models/gemini-2.5-flash"
]

print("Testing standard Gemini models:")
for m in test_models:
    url = f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "סווג מוצר 'חלב' לקטגוריה 'מוצרי חלב'"}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 30}
    }
    t0 = time.time()
    try:
        resp = httpx.post(url, json=payload, timeout=6.0)
        elapsed = time.time() - t0
        print(f"Model {m}: status={resp.status_code}, time={elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"Model {m}: ERROR {e}, time={elapsed:.2f}s")
