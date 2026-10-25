"""Local browser app with ordered Gemini interpretation and RDKit execution."""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import socket
import mimetypes

from conversation import Conversation
from interpreter import GeminiInterpreter


ROOT = Path(__file__).resolve().parent / "web"
DIST = ROOT / "dist"


class LocalServer(ThreadingHTTPServer):
    # Windows otherwise permits multiple HTTPServer processes on one port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(port=8001, interpret=None):
    conversation = Conversation(interpret or GeminiInterpreter())
    command_lock = threading.Lock()
    snapshot_lock = threading.Lock()
    snapshot = {"state": conversation.state(), "image": conversation.image()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Do not write spoken requests to HTTP logs.

        def send(self, code, body, content_type="application/json"):
            if not isinstance(body, bytes):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path.startswith('/api/'):
                path = path[4:]
            if path == "/health":
                self.send(200, json.dumps({
                    "provider": "gemini", "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                    "api_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
                }))
                return
            if path in ("/state", "/image", "/structure3d"):
                with snapshot_lock:
                    if path == "/state":
                        body = json.dumps(snapshot["state"])
                        ct = "application/json"
                    elif path == "/image":
                        body = snapshot["image"]
                        ct = "image/svg+xml"
                    else:
                        block = conversation.engine.structure_3d()
                        if block is None:
                            self.send(204, b"")
                            return
                        body = block
                        ct = "chemical/x-mdl-molfile"
                self.send(200, body, ct)
                return
            # A built React frontend can run on the same Python server without Vite.
            if (DIST / 'index.html').is_file() and (path in ('/', '/notebook') or path.startswith('/assets/')):
                candidate = DIST / ('index.html' if path in ('/', '/notebook') else path.lstrip('/'))
                try:
                    candidate.resolve().relative_to(DIST.resolve())
                except ValueError:
                    self.send(404, '{}')
                    return
                if not candidate.is_file():
                    self.send(404, '{}')
                    return
                self.send(200, candidate.read_bytes(), mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream')
                return
            files = {"/": "voice-app.html", "/voice-app.html": "voice-app.html",
                     "/voice-app.mjs": "voice-app.mjs", "/session.mjs": "session.mjs",
                     "/startup.mjs": "startup.mjs"}
            if path not in files:
                self.send(404, '{}')
                return
            file = ROOT / files[path]
            self.send(200, file.read_bytes(), "text/html" if file.suffix == ".html" else "text/javascript")

        def do_POST(self):
            route = self.path.split('?', 1)[0]
            if route.startswith('/api/'):
                route = route[4:]
            # No CORS; reject cross-origin mutation of the shared local session.
            expected = "http://" + self.headers.get("Host", "")
            if self.headers.get("Origin", expected) != expected:
                self.send(403, '{"message":"Cross-origin request rejected."}')
                return
            if route not in ("/utterance", "/command"):
                self.send(404, '{}')
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16000:
                    raise ValueError()
                text = json.loads(self.rfile.read(size)).get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError()
            except (ValueError, AttributeError):
                self.send(400, '{"message":"Send a nonempty text string."}')
                return
            with command_lock:
                if route == "/command":
                    event = conversation.direct_command(text)
                    with snapshot_lock:
                        snapshot.update(state=event, image=conversation.image())
                    self.send(200, json.dumps(event))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                connected = [True]
                def emit(event):
                    with snapshot_lock:
                        snapshot.update(state=event, image=conversation.image())
                    if connected[0]:
                        try:
                            self.wfile.write((json.dumps(event) + "\n").encode("utf-8"))
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, OSError):
                            connected[0] = False
                # A disconnected/stopped mic does not cancel accepted work.
                conversation.accept(text, emit)

    return LocalServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--port", type=int, default=8001)
    options = arguments.parse_args()
    server = make_server(options.port)
    print("Voice app: http://127.0.0.1:{}/".format(server.server_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
