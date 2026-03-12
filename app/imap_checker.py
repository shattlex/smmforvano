import email
import imaplib
import ssl
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple

from app.config import ALL_MAIL_FOLDERS, INBOX_FOLDERS, SPAM_FOLDERS


StatusResult = Dict[str, Optional[str]]


def _connect(email_addr: str, app_password: str) -> imaplib.IMAP4_SSL:
  context = ssl.create_default_context()
  imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=context)
  imap.login(email_addr, app_password.replace(" ", ""))
  return imap


def _search_ids(imap: imaplib.IMAP4_SSL, folder: str, subject: str) -> List[bytes]:
  status, _ = imap.select(folder, readonly=True)
  if status != "OK":
    return []

  safe_subject = subject.replace('"', "").strip()
  if not safe_subject:
    return []

  status, data = imap.search(None, "SUBJECT", f'"{safe_subject}"')
  if status != "OK" or not data or not data[0]:
    return []
  return data[0].split()


def _fetch_message_dt(imap: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[datetime]:
  status, data = imap.fetch(msg_id, "(RFC822)")
  if status != "OK" or not data or not data[0] or not data[0][1]:
    return None
  msg = email.message_from_bytes(data[0][1])
  dt_raw = msg.get("Date")
  if not dt_raw:
    return None
  try:
    dt = parsedate_to_datetime(dt_raw)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
  except Exception:
    return None


def _pick_latest(imap: imaplib.IMAP4_SSL, ids: List[bytes]) -> Optional[datetime]:
  latest = None
  # last 10 usually enough and avoids heavy fetch for large folders.
  for msg_id in ids[-10:]:
    dt = _fetch_message_dt(imap, msg_id)
    if dt and (latest is None or dt > latest):
      latest = dt
  return latest


def _in_window(dt: Optional[datetime], date_from: Optional[str], date_to: Optional[str], window_hours: int) -> bool:
  if dt is None:
    return False

  if date_from and date_to:
    try:
      start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
      end = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
      return start <= dt <= end
    except Exception:
      pass

  now_utc = datetime.now(timezone.utc)
  return dt >= now_utc - timedelta(hours=window_hours)


def check_seed_campaign(
  seed_email: str,
  app_password: str,
  subject: str,
  cid_token: Optional[str] = None,
  date_from: Optional[str] = None,
  date_to: Optional[str] = None,
  window_hours: int = 48,
) -> Dict[str, Optional[str]]:
  """
  Robust status detection:
  1) INBOX if matching message found in time window.
  2) SPAM if found only in spam.
  3) DELIVERED_NOT_INBOX if found in all-mail but not inbox/spam.
  4) NOT_DELIVERED otherwise.
  """
  imap = None
  try:
    imap = _connect(seed_email, app_password)

    # If cid token exists, prioritize exact campaign identifier to reduce false positives.
    subject_query = cid_token.strip() if cid_token else subject

    folder_hits: List[Tuple[str, str, int, Optional[datetime]]] = []

    for folder in INBOX_FOLDERS:
      ids = _search_ids(imap, folder, subject_query)
      if not ids:
        continue
      latest = _pick_latest(imap, ids)
      if _in_window(latest, date_from, date_to, window_hours):
        folder_hits.append(("INBOX", folder, len(ids), latest))

    for folder in SPAM_FOLDERS:
      ids = _search_ids(imap, folder, subject_query)
      if not ids:
        continue
      latest = _pick_latest(imap, ids)
      if _in_window(latest, date_from, date_to, window_hours):
        folder_hits.append(("SPAM", folder, len(ids), latest))

    # If both INBOX and SPAM found, choose latest timestamp status.
    if folder_hits:
      folder_hits.sort(key=lambda x: x[3] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
      status, folder, count, latest = folder_hits[0]
      return {
        "status": status,
        "found_folder": folder,
        "found_count": str(count),
        "latest_message_utc": latest.isoformat() if latest else None,
        "error": None,
      }

    for folder in ALL_MAIL_FOLDERS:
      ids = _search_ids(imap, folder, subject_query)
      if not ids:
        continue
      latest = _pick_latest(imap, ids)
      if _in_window(latest, date_from, date_to, window_hours):
        return {
          "status": "DELIVERED_NOT_INBOX",
          "found_folder": folder,
          "found_count": str(len(ids)),
          "latest_message_utc": latest.isoformat() if latest else None,
          "error": None,
        }

    return {
      "status": "NOT_DELIVERED",
      "found_folder": None,
      "found_count": "0",
      "latest_message_utc": None,
      "error": None,
    }
  except imaplib.IMAP4.error as exc:
    return {
      "status": "ERROR_AUTH",
      "found_folder": None,
      "found_count": "0",
      "latest_message_utc": None,
      "error": str(exc),
    }
  except Exception as exc:
    return {
      "status": "ERROR",
      "found_folder": None,
      "found_count": "0",
      "latest_message_utc": None,
      "error": str(exc),
    }
  finally:
    if imap is not None:
      try:
        imap.logout()
      except Exception:
        pass
