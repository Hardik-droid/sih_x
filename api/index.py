import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("TRACE_DATA", "/tmp/data")

from app import app as fastapi_app


class PrefixMiddleware:
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if not path.startswith("/api"):
                scope["path"] = "/api" + ("" if path == "/" else path)
        await self.inner_app(scope, receive, send)


app = PrefixMiddleware(fastapi_app)
