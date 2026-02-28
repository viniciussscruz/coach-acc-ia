from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Optional
from urllib.parse import unquote, urlparse

from ai_driving_coach.dashboard.state import DashboardState

_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "web" / "dashboard" / "dist"
_BUILD_MISSING_HTML = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard Build Ausente</title>
  <style>
    body { font-family: Segoe UI, sans-serif; background:#0b1020; color:#eaf0ff; margin:0; padding:24px; }
    .card { max-width:920px; margin:0 auto; border:1px solid #29355d; border-radius:12px; padding:18px; background:#121a33; }
    h1 { margin-top:0; font-size:24px; }
    pre { background:#091029; border:1px solid #2d3c70; border-radius:8px; padding:12px; overflow:auto; }
    code { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Dashboard React nao encontrado</h1>
    <p>O backend subiu, mas o build do frontend nao existe em <code>web/dashboard/dist</code>.</p>
    <p>Rode no terminal:</p>
    <pre>cd web/dashboard
npm install
npm run build</pre>
  </div>
</body>
</html>
"""


class DashboardServer:
    def __init__(
        self,
        state: DashboardState,
        host: str,
        port: int,
        static_dir: Path | None = None,
    ) -> None:
        self.state = state
        self.host = host
        self.port = port
        self.static_dir = (static_dir or _FRONTEND_DIST).resolve()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[Thread] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self._server is not None:
            return

        state = self.state
        static_dir = self.static_dir

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/api/state":
                    self._serve_json(state.snapshot())
                    return

                if static_dir.exists():
                    target = self._resolve_target(path)
                    if target is not None and target.is_file():
                        self._serve_file(target)
                        return

                    # SPA fallback for client-side routing.
                    index_file = static_dir / "index.html"
                    if index_file.exists():
                        self._serve_file(index_file, force_no_cache=True)
                        return
                self._serve_missing_frontend()

            def _resolve_target(self, request_path: str) -> Path | None:
                relative = unquote(request_path.lstrip("/"))
                if not relative:
                    relative = "index.html"
                candidate = (static_dir / relative).resolve()
                if static_dir == candidate or static_dir in candidate.parents:
                    return candidate
                return None

            def _serve_json(self, payload_obj: dict) -> None:
                payload = json.dumps(payload_obj, ensure_ascii=True).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _serve_file(self, file_path: Path, force_no_cache: bool = False) -> None:
                try:
                    payload = file_path.read_bytes()
                except OSError:
                    self.send_response(HTTPStatus.NOT_FOUND)
                    self.end_headers()
                    return

                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    content_type = "application/octet-stream"
                if content_type.startswith("text/"):
                    content_type = f"{content_type}; charset=utf-8"

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                if force_no_cache or file_path.name == "index.html":
                    self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def _serve_missing_frontend(self) -> None:
                payload = _BUILD_MISSING_HTML.encode("utf-8")
                self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
