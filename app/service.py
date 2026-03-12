from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from app.config import MAX_WORKERS, WINDOW_HOURS_DEFAULT
from app.db import execute, executemany, fetch_all, fetch_one
from app.imap_checker import check_seed_campaign


def _active_seeds():
  return fetch_all(
    "SELECT id, seed_name, email, app_password FROM seeds WHERE is_active = 1 ORDER BY id"
  )


def _active_campaigns():
  return fetch_all(
    """
    SELECT id, campaign_name, cid_token, subject, date_from, date_to, COALESCE(window_hours, ?) AS window_hours
    FROM campaigns
    WHERE is_active = 1
    ORDER BY id
    """,
    (WINDOW_HOURS_DEFAULT,),
  )


def run_monitor() -> Dict:
  seeds = _active_seeds()
  campaigns = _active_campaigns()

  if not seeds:
    return {"ok": False, "error": "No active seeds configured", "run_id": None}
  if not campaigns:
    return {"ok": False, "error": "No active campaigns configured", "run_id": None}

  started = datetime.now(timezone.utc).isoformat()
  execute("INSERT INTO runs(started_at_utc, status) VALUES (?, ?)", (started, "RUNNING"))
  run_id = fetch_one("SELECT id FROM runs ORDER BY id DESC LIMIT 1")["id"]

  task_list: List[Tuple[int, int, Dict]] = []
  for c in campaigns:
    for s in seeds:
      task_list.append((c["id"], s["id"], {
        "seed_email": s["email"],
        "app_password": s["app_password"],
        "subject": c["subject"],
        "cid_token": c["cid_token"],
        "date_from": c["date_from"],
        "date_to": c["date_to"],
        "window_hours": int(c["window_hours"]),
      }))

  rows = []
  errors = 0

  with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(task_list))) as pool:
    futures = {
      pool.submit(check_seed_campaign, **payload): (campaign_id, seed_id)
      for campaign_id, seed_id, payload in task_list
    }

    for future in as_completed(futures):
      campaign_id, seed_id = futures[future]
      result = future.result()
      if result.get("status") in {"ERROR", "ERROR_AUTH"}:
        errors += 1

      rows.append((
        run_id,
        campaign_id,
        seed_id,
        result.get("status") or "ERROR",
        result.get("found_folder"),
        int(result.get("found_count") or 0),
        result.get("latest_message_utc"),
        result.get("error"),
      ))

  executemany(
    """
    INSERT INTO run_results(
      run_id, campaign_id, seed_id, status, found_folder, found_count, latest_message_utc, error
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (run_id, campaign_id, seed_id)
    DO UPDATE SET
      status = excluded.status,
      found_folder = excluded.found_folder,
      found_count = excluded.found_count,
      latest_message_utc = excluded.latest_message_utc,
      error = excluded.error
    """,
    rows,
  )

  finished = datetime.now(timezone.utc).isoformat()
  final_status = "DONE_WITH_ERRORS" if errors else "DONE"
  execute(
    "UPDATE runs SET finished_at_utc = ?, status = ?, error_message = ? WHERE id = ?",
    (finished, final_status, None if errors == 0 else f"{errors} checks failed", run_id),
  )

  return {
    "ok": True,
    "run_id": run_id,
    "status": final_status,
    "campaigns": len(campaigns),
    "seeds": len(seeds),
    "checks": len(rows),
    "errors": errors,
  }


def latest_summary(limit_runs: int = 10):
  rows = fetch_all(
    """
    SELECT r.id AS run_id, r.started_at_utc, r.finished_at_utc, r.status,
      SUM(CASE WHEN rr.status = 'INBOX' THEN 1 ELSE 0 END) AS inbox,
      SUM(CASE WHEN rr.status = 'SPAM' THEN 1 ELSE 0 END) AS spam,
      SUM(CASE WHEN rr.status = 'DELIVERED_NOT_INBOX' THEN 1 ELSE 0 END) AS delivered_not_inbox,
      SUM(CASE WHEN rr.status = 'NOT_DELIVERED' THEN 1 ELSE 0 END) AS not_delivered,
      SUM(CASE WHEN rr.status IN ('ERROR','ERROR_AUTH') THEN 1 ELSE 0 END) AS errors,
      COUNT(rr.id) AS total_checks
    FROM runs r
    LEFT JOIN run_results rr ON rr.run_id = r.id
    GROUP BY r.id
    ORDER BY r.id DESC
    LIMIT ?
    """,
    (limit_runs,),
  )
  return [dict(r) for r in rows]


def latest_results(limit_rows: int = 200):
  rows = fetch_all(
    """
    SELECT rr.id, rr.run_id, rr.status, rr.found_folder, rr.found_count, rr.latest_message_utc, rr.error,
      c.campaign_name, c.subject, c.cid_token,
      s.seed_name, s.email AS seed_email
    FROM run_results rr
    JOIN campaigns c ON c.id = rr.campaign_id
    JOIN seeds s ON s.id = rr.seed_id
    ORDER BY rr.id DESC
    LIMIT ?
    """,
    (limit_rows,),
  )
  return [dict(r) for r in rows]


def dashboard_kpi():
  row = fetch_one(
    """
    SELECT
      COUNT(*) AS total,
      SUM(CASE WHEN status = 'INBOX' THEN 1 ELSE 0 END) AS inbox,
      SUM(CASE WHEN status = 'SPAM' THEN 1 ELSE 0 END) AS spam,
      SUM(CASE WHEN status = 'DELIVERED_NOT_INBOX' THEN 1 ELSE 0 END) AS delivered_not_inbox,
      SUM(CASE WHEN status = 'NOT_DELIVERED' THEN 1 ELSE 0 END) AS not_delivered,
      SUM(CASE WHEN status IN ('ERROR','ERROR_AUTH') THEN 1 ELSE 0 END) AS errors
    FROM run_results
    """
  )
  total = int(row["total"] or 0)

  def pct(value: int) -> float:
    return round((value / total) * 100, 2) if total else 0.0

  inbox = int(row["inbox"] or 0)
  spam = int(row["spam"] or 0)
  delivered_not_inbox = int(row["delivered_not_inbox"] or 0)
  not_delivered = int(row["not_delivered"] or 0)
  errors = int(row["errors"] or 0)

  return {
    "total_checks": total,
    "inbox": inbox,
    "spam": spam,
    "delivered_not_inbox": delivered_not_inbox,
    "not_delivered": not_delivered,
    "errors": errors,
    "inbox_rate_pct": pct(inbox),
    "spam_rate_pct": pct(spam),
    "missing_rate_pct": pct(not_delivered),
  }
