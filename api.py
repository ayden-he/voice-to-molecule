"""HTTP API that exposes the molecule engine for the website.

This is a second frontend onto the same engine the terminal app (main.py) uses:
it receives a command as JSON, runs the deterministic parser + RDKit Builder,
and returns the result as JSON. Chemistry lives only in builder.py; this layer
never decides chemistry. See API.md for the contract.
"""

from flask import Flask, jsonify, request, Response

import export

from command_engine import CommandEngine, ELEMENT_MESSAGE, UNKNOWN_MESSAGE, OPTIONS_TEXT, HELP_TEXT

_engine = CommandEngine()


def _snapshot():
    return _engine.snapshot()


def run_command(text):
    return _engine.run_command(text)


def _svg():
    return _engine.svg()


def create_app() -> Flask:
    """Build the Flask app. Kept as a factory so tests get a fresh client."""
    app = Flask(__name__)

    @app.after_request
    def allow_cross_origin(response):
        # The frontend may run on a different port during development.
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.route("/command", methods=["POST", "OPTIONS"])
    def command():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        if not isinstance(text, str):
            text = ""
        return jsonify(run_command(text))

    @app.route("/state", methods=["GET"])
    def state():
        return jsonify(dict(ok=True, message="", **_snapshot()))

    @app.route("/image", methods=["GET"])
    def image():
        fmt = request.args.get("fmt", "svg").lower()
        if fmt == "png":
            molecule = _engine.builder.molecule_copy()
            if molecule.GetNumAtoms() == 0:
                return ("", 204)
            ok, _ = export.save_image(_engine.builder, export.CURRENT_IMAGE)
            if not ok:
                return ("", 204)
            return Response(export.CURRENT_IMAGE.read_bytes(), mimetype="image/png")
        svg = _svg()
        if svg is None:
            return ("", 204)  # Empty molecule: nothing to draw.
        return Response(svg, mimetype="image/svg+xml")

    return app

def reset_state() -> None:
    """Reset the module-level molecule and version (used by tests)."""
    global _engine
    _engine = CommandEngine()

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
