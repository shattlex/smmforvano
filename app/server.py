import json
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.auth import create_session_token, verify_password, verify_session_token
from app.config import HOST, PORT, SESSION_MAX_AGE_SECONDS, SESSION_SECRET
from app.db import fetch_one, init_db
from app.seed_data import ensure_seed_data
from app.service import dashboard_kpi, latest_results, latest_summary, run_monitor

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


class Handler(BaseHTTPRequestHandler):
  server_version = "SeedMonitor/1.1"

  def _json(self, payload, status=HTTPStatus.OK, extra_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    if extra_headers:
      for key, value in extra_headers.items():
        self.send_header(key, value)
    self.end_headers()
    self.wfile.write(body)

  def _text(self, text: str, status=HTTPStatus.OK):
    body = text.encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "text/plain; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _redirect(self, location: str):
    self.send_response(HTTPStatus.FOUND)
    self.send_header("Location", location)
    self.end_headers()

  def _serve_file(self, path: Path, content_type: str):
    if not path.exists() or not path.is_file():
      self._text("Not found", HTTPStatus.NOT_FOUND)
      return
    body = path.read_bytes()
    self.send_response(HTTPStatus.OK)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _parse_json_body(self):
    length = int(self.headers.get("Content-Length", "0"))
    if length <= 0:
      return {}
    raw = self.rfile.read(length)
    try:
      return json.loads(raw.decode("utf-8"))
    except Exception:
      return {}

  def _current_user_email(self):
    cookie_header = self.headers.get("Cookie")
    if not cookie_header:
      return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    session_cookie = cookie.get("seed_session")
    if not session_cookie:
      return None
    return verify_session_token(session_cookie.value, SESSION_SECRET, SESSION_MAX_AGE_SECONDS)

  def _is_public_path(self, path: str) -> bool:
    return path in {
      "/api/health",
      "/api/login",
      "/login",
      "/login.css",
      "/login.js",
    }

  def _is_authenticated(self) -> bool:
    return self._current_user_email() is not None

  def _require_auth_or_reject(self, path: str):
    if self._is_public_path(path) or self._is_authenticated():
      return True

    if path.startswith("/api/"):
      self._json({"ok": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
    else:
      self._redirect("/login")
    return False

  def do_GET(self):
    parsed = urlparse(self.path)
    path = parsed.path

    if path == "/api/health":
      return self._json({"ok": True})

    if path == "/login":
      if self._is_authenticated():
        return self._redirect("/")
      return self._serve_file(WEB_DIR / "login.html", "text/html; charset=utf-8")

    if path == "/login.css":
      return self._serve_file(WEB_DIR / "login.css", "text/css; charset=utf-8")

    if path == "/login.js":
      return self._serve_file(WEB_DIR / "login.js", "application/javascript; charset=utf-8")

    if not self._require_auth_or_reject(path):
      return

    if path == "/api/me":
      return self._json({"ok": True, "email": self._current_user_email()})

    if path == "/api/kpi":
      return self._json(dashboard_kpi())

    if path == "/api/runs":
      query = parse_qs(parsed.query)
      limit = int(query.get("limit", ["10"])[0])
      return self._json({"runs": latest_summary(limit_runs=limit)})

    if path == "/api/results":
      query = parse_qs(parsed.query)
      limit = int(query.get("limit", ["200"])[0])
      return self._json({"results": latest_results(limit_rows=limit)})

    if path in ("/", "/index.html"):
      return self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")

    if path == "/styles.css":
      return self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")

    if path == "/app.js":
      return self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")

    return self._text("Not found", HTTPStatus.NOT_FOUND)

  def do_POST(self):
    path = urlparse(self.path).path

    if path == "/api/login":
      payload = self._parse_json_body()
      email = str(payload.get("email", "")).strip().lower()
      password = str(payload.get("password", ""))
      if not email or not password:
        return self._json({"ok": False, "error": "Email and password are required"}, HTTPStatus.BAD_REQUEST)

      user = fetch_one("SELECT email, password_hash, is_active FROM users WHERE lower(email) = lower(?)", (email,))
      if not user or int(user["is_active"]) != 1 or not verify_password(password, user["password_hash"]):
        return self._json({"ok": False, "error": "Invalid credentials"}, HTTPStatus.UNAUTHORIZED)

      token = create_session_token(user["email"], SESSION_SECRET)
      cookie = f"seed_session={token}; Path=/; HttpOnly; Max-Age={SESSION_MAX_AGE_SECONDS}; SameSite=Lax"
      return self._json({"ok": True, "email": user["email"]}, HTTPStatus.OK, extra_headers={"Set-Cookie": cookie})

    if path == "/api/logout":
      cookie = "seed_session=; Path=/; HttpOnly; Max-Age=0; SameSite=Lax"
      return self._json({"ok": True}, HTTPStatus.OK, extra_headers={"Set-Cookie": cookie})

    if not self._require_auth_or_reject(path):
      return

    if path == "/api/run":
      result = run_monitor()
      if result.get("ok"):
        return self._json(result, HTTPStatus.OK)
      return self._json(result, HTTPStatus.BAD_REQUEST)

    return self._text("Not found", HTTPStatus.NOT_FOUND)


def run():
  init_db()
  ensure_seed_data()
  server = ThreadingHTTPServer((HOST, PORT), Handler)
  print(f"Seed Monitor API listening on http://{HOST}:{PORT}")
  server.serve_forever()


if __name__ == "__main__":
  run()
