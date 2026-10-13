import sqlite3
import time
import httpx

conn = sqlite3.connect('data/grocery.db')
c = conn.cursor()
c.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
key = c.fetchone()[0]

candidates = [
    "models/gemini-flash-latest",
    "models/gemini-2.5-flash",
    "models/gemini-3.5-flash",
    "models/gemini-3.6-flash",
    "models/gemini-3.7-flash",
    "models/gemini-3.8-flash",
    "models/gemini-3-flash-preview",
    "models/gemini-pro-latest"
]

print("Benchmarking candidate models:")
for m in candidates:
    url = f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "סווג 'חלב' לקטגוריה"}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 30}
    }
    t0 = time.time()
    try:
        resp = httpx.post(url, json=payload, timeout=5.0)
        elapsed = time.time() - t0
        print(f"Model {m}: status={resp.status_code}, time={elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"Model {m}: {e}, time={elapsed:.2f}s")
