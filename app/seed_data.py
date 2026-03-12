from datetime import datetime, timezone

from app.auth import hash_password
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
from app.db import execute, fetch_one


def ensure_seed_data() -> None:
  has_seed = fetch_one("SELECT id FROM seeds LIMIT 1")
  has_campaign = fetch_one("SELECT id FROM campaigns LIMIT 1")
  has_user = fetch_one("SELECT id FROM users LIMIT 1")

  if not has_user:
    execute(
      "INSERT INTO users(email, password_hash, is_active) VALUES (?, ?, 1)",
      (ADMIN_EMAIL.lower(), hash_password(ADMIN_PASSWORD)),
    )

  if not has_seed:
    execute(
      """
      INSERT INTO seeds(seed_name, email, app_password, is_active)
      VALUES
        ('seed_1', 'seed1@gmail.com', 'replace_me_app_password_1', 0),
        ('seed_2', 'seed2@gmail.com', 'replace_me_app_password_2', 0),
        ('seed_3', 'seed3@gmail.com', 'replace_me_app_password_3', 0)
      """
    )

  if not has_campaign:
    today = datetime.now(timezone.utc).date().isoformat()
    execute(
      """
      INSERT INTO campaigns(campaign_name, cid_token, subject, date_from, date_to, window_hours, is_active)
      VALUES
        (?, ?, ?, ?, ?, 48, 1),
        (?, ?, ?, ?, ?, 48, 1)
      """,
      (
        "Campaign Demo 1",
        "[CID:20260312-001]",
        "[CID:20260312-001] Welcome bonus",
        today,
        today,
        "Campaign Demo 2",
        "[CID:20260312-002]",
        "[CID:20260312-002] Reactivation",
        today,
        today,
      ),
    )
