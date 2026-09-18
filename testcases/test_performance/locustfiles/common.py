import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.config import config

BASE_URL = config.get("base_url")

RESPONSE_TIME_THRESHOLD = {
    "login_p95_ms": 500,
    "register_p95_ms": 800,
    "order_list_p95_ms": 300,
    "order_create_p95_ms": 1000,
    "profile_p95_ms": 200,
}

VALID_PHONE = "19118551234"
VALID_PASSWORD = "123456"
REGISTER_PASSWORD = "Test@123456"