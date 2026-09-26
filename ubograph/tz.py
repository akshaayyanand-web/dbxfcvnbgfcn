"""UAE/Dubai time, used for every timestamp the platform displays or prints.

The UAE does not observe daylight saving, so "Gulf Standard Time" is a fixed
UTC+4 offset year-round — a plain `timezone(timedelta(hours=4))` is exact and
needs no tzdata package on the host, unlike `zoneinfo.ZoneInfo("Asia/Dubai")`,
which depends on a system tzdata install that a slim container image may not
have. Every backend-generated timestamp (report generation, PDF footers,
goAML drafts, the activity log) goes through here so they read consistently
no matter what timezone the server itself runs in.
"""
from datetime import datetime, timedelta, timezone

DUBAI = timezone(timedelta(hours=4), name="GST")


def now_dubai() -> datetime:
    return datetime.now(DUBAI)


def format_dubai(dt: datetime = None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a timestamp in Dubai time, always with the offset stated so a
    reader never has to guess which timezone a printed time is in."""
    moment = (dt or now_dubai())
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(DUBAI).strftime(fmt) + " GST"


def format_dubai_from_epoch(epoch_seconds: float, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Same as format_dubai(), for the epoch-seconds timestamps db.py stores."""
    return format_dubai(datetime.fromtimestamp(epoch_seconds, tz=timezone.utc), fmt)
