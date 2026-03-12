from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.db import init_db
from app.seed_data import ensure_seed_data


if __name__ == "__main__":
  init_db()
  ensure_seed_data()
  print("DB initialized with demo data.")
