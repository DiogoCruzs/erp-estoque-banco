from pathlib import Path
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SERV_FESTA_DATA_DIR", BASE_DIR / "data"))
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "serv_festa.db"
SECRET_FILE = DATA_DIR / "session.secret"
if SECRET_FILE.exists():
    SECRET_KEY = SECRET_FILE.read_text(encoding="utf-8").strip()
else:
    SECRET_KEY = os.environ.get("SERV_FESTA_SECRET_KEY") or secrets.token_hex(32)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(SECRET_KEY, encoding="utf-8")
HOST = os.environ.get("SERV_FESTA_HOST", "127.0.0.1")
PORT = int(os.environ.get("SERV_FESTA_PORT", "5000"))

