import subprocess
import httpx
import sys

# 1. Retrieve GitHub token from Git Credential Manager
p = subprocess.Popen(["git", "credential", "fill"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
stdout, _ = p.communicate("protocol=https\nhost=github.com\n")
token = ""
user = ""
for line in stdout.splitlines():
    if line.startswith("username="):
        user = line.split("=", 1)[1].strip()
    elif line.startswith("password="):
        token = line.split("=", 1)[1].strip()

if not token or not user:
    print("Failed to get credentials from Git Credential Manager.")
    sys.exit(1)

print(f"Creating repository for user: {user}...")

# 2. Create GitHub repo via API
repo_name = "grocery-list"
payload = {
    "name": repo_name,
    "description": "🛒 אפליקציית רשימת קניות חכמה בעברית עם סיווג מקומי, AI, ובוט טלגרם ב-Docker",
    "private": True,
    "has_issues": True,
    "has_wiki": False
}

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json"
}

r = httpx.post("https://api.github.com/user/repos", json=payload, headers=headers)
print(f"GitHub API status: {r.status_code}")
if r.status_code in [201, 200]:
    repo_url = r.json().get("html_url")
    clone_url = r.json().get("clone_url")
    print(f"Repository created successfully at: {repo_url}")
elif r.status_code == 422: # Already exists
    print(f"Repository {repo_name} already exists. Using existing repo.")
    clone_url = f"https://github.com/{user}/{repo_name}.git"
    repo_url = f"https://github.com/{user}/{repo_name}"
else:
    print(f"Error creating repository: {r.text}")
    sys.exit(1)

# 3. Initialize git if needed
subprocess.run(["git", "init"], check=True)
subprocess.run(["git", "branch", "-M", "main"], check=True)

# 4. Check status and add files
subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", "Initial commit: Smart grocery list application with local caching, Gemini AI, and Telegram bot"], check=True)

# 5. Set remote origin
subprocess.run(["git", "remote", "remove", "origin"], stderr=subprocess.DEVNULL)
subprocess.run(["git", "remote", "add", "origin", clone_url], check=True)

# 6. Push to origin main
print("Pushing to GitHub...")
push_res = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True)
print("STDOUT:", push_res.stdout)
print("STDERR:", push_res.stderr)
if push_res.returncode == 0:
    print(f"SUCCESS: Pushed code to {repo_url}")
else:
    print("Push failed with code:", push_res.returncode)
