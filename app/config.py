import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("SEED_MONITOR_DB", DATA_DIR / "seed_monitor.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
HOST = os.getenv("SEED_MONITOR_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("SEED_MONITOR_PORT", "8080")))
WINDOW_HOURS_DEFAULT = int(os.getenv("WINDOW_HOURS_DEFAULT", "48"))
MAX_WORKERS = int(os.getenv("SEED_MONITOR_WORKERS", "8"))

SESSION_SECRET = os.getenv("SESSION_SECRET", "change_me_seed_monitor_secret")
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "43200"))

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me_admin_password")

# Gmail folder aliases to be robust to locale differences.
INBOX_FOLDERS = ["INBOX"]
SPAM_FOLDERS = ["[Gmail]/Spam", "[Google Mail]/Spam", "Spam", "Junk"]
ALL_MAIL_FOLDERS = ["[Gmail]/All Mail", "[Google Mail]/All Mail", "All Mail"]
