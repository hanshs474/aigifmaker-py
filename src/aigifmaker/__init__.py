"""Official Python SDK for AI GIF Maker (https://aigifmaker.ai): turn text into
animated GIFs.

    from aigifmaker import generate
    url = generate("a corgi wearing sunglasses, dancing on a beach")

Create a key at https://aigifmaker.ai/settings/apikeys and pass it as
``api_key=`` or set ``AIGIFMAKER_API_KEY``. Each GIF costs 1 credit on your
AI GIF Maker account, the same as on the website.

Standard library only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

__version__ = "0.1.0"
__all__ = [
    "Client",
    "generate",
    "submit",
    "status",
    "credits",
    "AigifmakerError",
    "AuthError",
    "QuotaError",
    "RejectedError",
    "GenerationFailed",
    "BASE_URL",
]

BASE_URL = "https://aigifmaker.ai"
KEYS_URL = "https://aigifmaker.ai/settings/apikeys"
PRICING_URL = "https://aigifmaker.ai/pricing"

DEFAULT_TIMEOUT = 300.0
POLL_EVERY = 3.0


class AigifmakerError(RuntimeError):
    """Base class. Catch a subclass to decide what to do next."""

    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


class AuthError(AigifmakerError):
    """No API key, or the key is invalid or deleted."""


class QuotaError(AigifmakerError):
    """The account is out of credits."""


class RejectedError(AigifmakerError):
    """The content filter refused the prompt, or a cooldown is active. Reword it."""


class GenerationFailed(AigifmakerError):
    """The GIF was accepted but the run ended as failed or canceled."""


Transport = Callable[[str, str, Optional[dict], dict], Tuple[int, dict]]


def _http(method: str, url: str, body: Optional[dict], headers: dict) -> Tuple[int, dict]:
    headers = {**headers, "User-Agent": f"aigifmaker-python/{__version__}", "Content-Type": "application/json"}
    data = json.dumps(body if body is not None else {}).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw = e.read() or b""
        code = e.code
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        parsed = {"code": -1, "message": raw[:200].decode("utf-8", "replace") or f"HTTP {code}"}
    return code, parsed if isinstance(parsed, dict) else {"code": -1, "message": str(parsed)}


def _unwrap(http_status: int, env: dict) -> Dict[str, Any]:
    """Return ``data`` for ``code: 0``; otherwise raise the error that says what to do next.

    Every response is HTTP 200; the JSON ``code`` tells success from refusal.
    """
    code = env.get("code")
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    if code == 0:
        if data.get("wall"):
            raise AuthError(f"an API key is required; create one at {KEYS_URL} and set AIGIFMAKER_API_KEY", code)
        return data
    msg = str(env.get("message") or env.get("error") or f"HTTP {http_status}")
    low = msg.lower()
    if "invalid api key" in low or "no auth" in low or http_status == 401:
        raise AuthError(msg, code if isinstance(code, int) else None)
    if "insufficient credits" in low:
        raise QuotaError(f"{msg}. Top up at {PRICING_URL}", code if isinstance(code, int) else None)
    if isinstance(code, int) and code not in (0, -1):
        raise RejectedError(msg, code)
    raise AigifmakerError(msg, code if isinstance(code, int) else None)


class Client:
    """One connection to AI GIF Maker.

    ``api_key`` defaults to ``AIGIFMAKER_API_KEY``; ``timeout`` (seconds) bounds
    how long :meth:`generate` waits for a GIF.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        poll_every: float = POLL_EVERY,
        transport: Optional[Transport] = None,
    ):
        self.api_key = api_key or os.environ.get("AIGIFMAKER_API_KEY") or None
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_every = poll_every
        self._http = transport or _http

    def _post(self, path: str, body: Optional[dict]) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        st, env = self._http("POST", self.base_url + path, body, headers)
        return _unwrap(st, env)

    def submit(self, prompt: str) -> str:
        """Start one GIF and return its task id without waiting."""
        if not str(prompt or "").strip():
            raise ValueError("prompt is required")
        data = self._post(
            "/api/ai/generate",
            {
                "provider": "openlux",
                "mediaType": "image",
                "model": "gif-maker-v1",
                "scene": "text-to-image",
                "prompt": prompt,
                "options": {"output_format": "gif"},
            },
        )
        task_id = data.get("id")
        if not task_id:
            raise AigifmakerError("the service returned no task id")
        return str(task_id)

    def status(self, task_id: str) -> Dict[str, Any]:
        """Return the task record: ``status`` is pending, processing, success or
        failed; ``images[0]`` holds the GIF URL when it succeeds."""
        return self._post("/api/ai/query", {"taskId": task_id})

    def wait(self, task_id: str, timeout: Optional[float] = None) -> str:
        """Poll a task every 3 seconds until it finishes and return the GIF URL."""
        limit = self.timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        while True:
            try:
                data = self.status(task_id)
            except OSError:
                data = {}  # a dropped poll is not a failed generation
            state = str(data.get("status") or "").lower()
            images = data.get("images") or []
            if state == "success" and images:
                return str(images[0])
            if state in ("failed", "canceled"):
                msg = str(data.get("errorMessage") or f"the GIF {state}")
                if data.get("failureKind") == "moderation":
                    raise RejectedError(msg)
                raise GenerationFailed(msg)
            if time.monotonic() >= deadline:
                raise AigifmakerError(f"still running after {limit:g}s; task {task_id} may finish later in your AI GIF Maker history")
            time.sleep(self.poll_every)

    def generate(self, prompt: str) -> str:
        """Generate one animated GIF and return its URL."""
        return self.wait(self.submit(prompt))

    def credits(self) -> int:
        """Return the remaining credits on the account. Free to call."""
        return int(self._post("/api/user/get-user-credits", None).get("remainingCredits") or 0)


def generate(prompt: str, *, api_key: Optional[str] = None, **kw: Any) -> str:
    """Generate one animated GIF and return its URL."""
    return Client(api_key, **kw).generate(prompt)


def submit(prompt: str, *, api_key: Optional[str] = None, **kw: Any) -> str:
    """Start one GIF and return its task id."""
    return Client(api_key, **kw).submit(prompt)


def status(task_id: str, *, api_key: Optional[str] = None, **kw: Any) -> Dict[str, Any]:
    """Return the task record for ``task_id``."""
    return Client(api_key, **kw).status(task_id)


def credits(*, api_key: Optional[str] = None, **kw: Any) -> int:
    """Return the remaining credits on the account."""
    return Client(api_key, **kw).credits()
