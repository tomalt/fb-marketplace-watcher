import json
from pathlib import Path

DATA_DIR = Path("/app/data")
SEEN_PATH = DATA_DIR / "seen.json"
STATUS_PATH = DATA_DIR / "status.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_seen():
    if not SEEN_PATH.exists():
        return {}, True
    return json.loads(SEEN_PATH.read_text()), False


def save_seen(seen):
    SEEN_PATH.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")


def save_status(status):
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
