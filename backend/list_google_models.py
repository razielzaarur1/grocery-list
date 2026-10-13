import sqlite3
import httpx

conn = sqlite3.connect('data/grocery.db')
c = conn.cursor()
c.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
key = c.fetchone()[0]

resp = httpx.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=10.0)
data = resp.json()
print("All available models for this key:")
for m in data.get("models", []):
    methods = m.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        print(f"Name: {m['name']}, methods: {methods}")
