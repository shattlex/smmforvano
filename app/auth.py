import base64
import hashlib
import hmac
import os
import time
from typing import Optional


def hash_password(password: str, salt: Optional[str] = None, iterations: int = 200_000) -> str:
  if salt is None:
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
  digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
  hash_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
  return f"pbkdf2_sha256${iterations}${salt}${hash_b64}"


def verify_password(password: str, encoded: str) -> bool:
  try:
    algo, iter_str, salt, hash_b64 = encoded.split("$")
    if algo != "pbkdf2_sha256":
      return False
    expected = hash_password(password, salt=salt, iterations=int(iter_str))
    return hmac.compare_digest(expected, encoded)
  except Exception:
    return False


def create_session_token(email: str, secret: str) -> str:
  ts = str(int(time.time()))
  payload = f"{email}|{ts}".encode("utf-8")
  payload_b64 = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
  sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
  return f"{payload_b64}.{sig}"


def verify_session_token(token: str, secret: str, max_age_seconds: int) -> Optional[str]:
  try:
    payload_b64, sig = token.split(".", 1)
    expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
      return None

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    email, ts_str = payload.split("|", 1)
    if (int(time.time()) - int(ts_str)) > max_age_seconds:
      return None
    return email
  except Exception:
    return None
