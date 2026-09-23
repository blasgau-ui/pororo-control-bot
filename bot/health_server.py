"""Servidor HTTP mínimo, sólo para que Render (plan free, tipo "Web Service") detecte que
el proceso sigue vivo. Render no ofrece "Background Worker" gratis: el free tier únicamente
existe para servicios que escuchan en un puerto HTTP. El bot en sí sigue funcionando por
long polling (no necesita HTTP para nada); esto corre en un hilo aparte solo para satisfacer
ese requisito de Render y responder algo a quien visite la URL del servicio o a un ping
externo (por ejemplo UptimeRobot) que lo mantenga despierto.
"""

from __future__ import annotations

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (nombre requerido por BaseHTTPRequestHandler)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"pororo-control-bot: ok\n")

    def log_message(self, format: str, *args: object) -> None:  # silencia el log por request
        pass


def start_health_server_if_configured() -> None:
    """Arranca el servidor sólo si Render (u otro host tipo Web Service) definió PORT. En
    local, o en un worker real (Railway), esta variable no está seteada y no se hace nada."""
    port = os.environ.get("PORT")
    if not port:
        return
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health-server")
    thread.start()
    logger.info("Servidor de health-check escuchando en el puerto %s (requisito de Render free).", port)
