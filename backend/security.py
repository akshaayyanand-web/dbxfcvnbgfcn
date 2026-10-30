"""Upload validation, optional API-key authorisation and a simple rate limiter."""

from __future__ import annotations

import hmac
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile, status

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi"}
_CHUNK = 1 << 20


def sniff_video_container(head: bytes, ext: str) -> bool:
    """Check the file signature matches the claimed container (not just the extension)."""
    if ext in (".mp4", ".mov"):
        # ISO-BMFF / QuickTime: an atom type at bytes 4..8
        return len(head) >= 12 and head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot")
    if ext == ".avi":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"AVI "
    return False


async def save_upload(upload: UploadFile, dest_dir: Path, max_bytes: int) -> tuple[Path, str, int]:
    """Stream an upload to ``dest_dir/<random id><ext>`` enforcing type and size.

    The client file name is never used to build a path (only its extension, validated
    against an allow-list), so path traversal is impossible. Returns
    ``(path, original_name, size)``.
    """
    original = Path(upload.filename or "").name[:255]
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            f"Unsupported file type '{ext or '(none)'}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXT))}.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{uuid.uuid4().hex}{ext}"
    size = 0
    head = b""
    try:
        with open(path, "wb") as out:
            while chunk := await upload.read(_CHUNK):
                if not head:
                    head = chunk[:64]
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                        f"Upload exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Uploaded file is empty.")
        if not sniff_video_container(head, ext):
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                f"File content does not match a {ext} video container.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, original, size


def require_api_key(request: Request) -> None:
    """If FLAME_API_KEY is configured, require it in the X-API-Key header (constant-time comparison)."""
    key = request.app.state.settings.api_key
    if key is None:
        return
    supplied = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(supplied.encode(), key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key.")


class RateLimiter:
    """Sliding-window limiter per client address (in-memory; single-process deployments)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client: str) -> None:
        if self.per_minute <= 0:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits[client]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded; try again shortly.")
            q.append(now)
