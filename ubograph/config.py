"""Configuration loaded from the environment (and a .env file if present)."""
import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_dotenv(path: Path = _ENV_PATH) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

OPENSANCTIONS_API_KEY = os.environ.get("OPENSANCTIONS_API_KEY", "").strip()
OPENCORPORATES_API_TOKEN = os.environ.get("OPENCORPORATES_API_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Which adverse-media provider to use when more than one key is configured.
# "auto" (default) prefers Anthropic for backward compatibility, then Gemini.
ADVERSE_MEDIA_PROVIDER = os.environ.get("ADVERSE_MEDIA_PROVIDER", "auto").strip().lower()

# A /match candidate scoring below this is treated as noise, not a result — an
# unrelated same-ish-sounding name should never stand in for "we found them".
# The searched name still surfaces via the adverse-media open-web fallback instead.
MATCH_SCORE_THRESHOLD = float(os.environ.get("MATCH_SCORE_THRESHOLD", "0.5"))

OPENSANCTIONS_BASE_URL = os.environ.get(
    "OPENSANCTIONS_BASE_URL", "https://api.opensanctions.org"
).rstrip("/")
OPENCORPORATES_BASE_URL = os.environ.get(
    "OPENCORPORATES_BASE_URL", "https://api.opencorporates.com/v0.4"
).rstrip("/")

# Set this when the app is reachable from the internet. Blank locally.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
APP_USERNAME = os.environ.get("APP_USERNAME", "sanctionsplus").strip()

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "30"))
PORT = int(os.environ.get("PORT", "5000"))

# Jurisdictions that raise a flag during legal due diligence. Not an accusation:
# a hit means "ask where the money is actually from", not "this is laundering".
HIGH_RISK_JURISDICTIONS = {
    "vg": "British Virgin Islands",
    "ky": "Cayman Islands",
    "pa": "Panama",
    "sc": "Seychelles",
    "bz": "Belize",
    "mh": "Marshall Islands",
    "cy": "Cyprus",
    "mt": "Malta",
    "li": "Liechtenstein",
    "ws": "Samoa",
    "vu": "Vanuatu",
    "bs": "Bahamas",
    "cw": "Curacao",
    "gi": "Gibraltar",
    "je": "Jersey",
    "gg": "Guernsey",
    "im": "Isle of Man",
    "mu": "Mauritius",
    "ae": "United Arab Emirates (free zone structures)",
}


def redact(text: str) -> str:
    """Scrub credentials out of anything user-visible.

    OpenCorporates takes its token as a query parameter, so a request exception
    carries the full URL — and therefore the key — in its message.
    """
    if not text:
        return ""
    for secret in (OPENCORPORATES_API_TOKEN, OPENSANCTIONS_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY):
        if secret and len(secret) >= 6:
            text = text.replace(secret, "***redacted***")
    return text


def status() -> dict:
    """What the frontend header chips render."""
    return {
        "opensanctions": bool(OPENSANCTIONS_API_KEY),
        "opencorporates": bool(OPENCORPORATES_API_TOKEN),
        "adverse_media": bool(ANTHROPIC_API_KEY or GEMINI_API_KEY),
        "demo_mode": not (OPENSANCTIONS_API_KEY or OPENCORPORATES_API_TOKEN),
    }
