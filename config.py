import os

# ── Flask ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("TOTP_SECRET_KEY", "this-will-be-my-super-secret-key-but-i-need-to-update-it-still")

# ── Database ───────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("TOTP_DB_PATH", "./data/totp_quotes.db")

# ── Google Form ────────────────────────────────────────────────────────────
# Paste your Google Form share URL here once you've created it.
GOOGLE_FORM_URL = os.environ.get("TOTP_FORM_URL", "https://docs.google.com/forms/d/e/1FAIpQLSeZiJLI3ijx8bwndgQ87xVdlS1ZRsQh943WSRomFEXdPyqm1A/viewform?usp=publish-editor")
