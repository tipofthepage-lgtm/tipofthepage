import os
 
# ── Flask ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("TOTP_SECRET_KEY", "change-this-in-production")
 
# ── Database ───────────────────────────────────────────────────────────────
# Railway automatically sets DATABASE_URL when you add a Postgres plugin
DATABASE_URL = os.environ.get("DATABASE_URL", None)

# ── Google Form ────────────────────────────────────────────────────────────
# Paste your Google Form share URL here once you've created it.
GOOGLE_FORM_URL = os.environ.get("TOTP_FORM_URL", "https://docs.google.com/forms/d/e/1FAIpQLSeZiJLI3ijx8bwndgQ87xVdlS1ZRsQh943WSRomFEXdPyqm1A/viewform?usp=publish-editor")
