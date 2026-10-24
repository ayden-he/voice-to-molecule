"""HTTP API that exposes the molecule engine for the website.

This is a second frontend onto the same engine the terminal app (main.py) uses:
it receives a command as JSON, runs the deterministic parser + RDKit Builder,
and returns the result as JSON. Chemistry lives only in builder.py; this layer
never decides chemistry. See API.md for the contract.
"""

import io
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, request, Response
from rdkit.Chem.Draw import rdMolDraw2D

import export
import library
import naming
from builder import Builder, ELEMENT_NAMES
from parser import parse
from readback import detail, summary

# One molecule per server process (single-session, as agreed for the hackathon).
_builder = Builder()
# Bumped on every successful change so the browser can cache-bust the image.
_version = 0

from builder import UNSUPPORTED_ELEMENT_MESSAGE as ELEMENT_MESSAGE
UNKNOWN_MESSAGE = ("I didn't understand that. "
                   "Try: add carbon; add oxygen double bond; go to atom 3.")
OPTIONS_TEXT = ("Elements: carbon, oxygen, and the halogens fluorine, chlorine, "
                "bromine, and iodine. Hydrogens are added automatically. "
                "Groups: methyl, ethyl, hydroxyl, methoxy, aldehyde, carboxylic acid. "
                "Rings: cyclopropane, cyclobutane, cyclopentane, cyclohexane, benzene.")
HELP_TEXT = ("Build: add carbon; add oxygen double bond; add five carbons; "
             "groups like add methyl; rings like add benzene ring. "
             "Edit: change the bond between two and three to double; delete atom five; "
             "start over; undo. Navigate: go to atom N; where am I; what can I add. "
             "Read: read it back; summary.")

def _snapshot() -> Dict[str, Any]:
    """Return the current molecule as the shared JSON shape (no 'ok'/'message')."""
    atoms = _builder.describe_atoms()
    return {
        "smiles": _builder.smiles() or "",
        "summary": summary(_builder),
        "detail": detail(_builder),
        "current_atom": _builder.current_atom,
        "atoms": atoms,
        "image_url": "/image?v={}".format(_version),
    }

def run_command(text: str) -> Dict[str, Any]:
    """Run one command string and return the full API response dict.

    Pure data in, data out: no printing, no speech, no image files. The web
    layer and any test can call this directly.
    """
    global _version
    command = parse(text)
    if command is None:
        return dict(ok=False, message=UNKNOWN_MESSAGE, **_snapshot())

    action = command["action"]

    # Read-only / informational actions: never change the molecule.
    if action in ("read_back", "summary"):
        message = detail(_builder) if action == "read_back" else summary(_builder)
        return dict(ok=True, message=message, **_snapshot())
    if action == "name":
        if _builder.current_atom is None:
            return dict(ok=True, message="The molecule is empty.", **_snapshot())
        common, iupac, message = naming.lookup_name(_builder.smiles())
        result = dict(ok=True, message=message, **_snapshot())
        result["common_name"] = common
        result["iupac_name"] = iupac
        return result
    if action == "unsupported_element":
        return dict(ok=False, message=ELEMENT_MESSAGE, **_snapshot())
    if action == "help":
        return dict(ok=True, message=HELP_TEXT, **_snapshot())
    if action == "what_can_i_add":
        return dict(ok=True, message=OPTIONS_TEXT, **_snapshot())
    if action == "where_am_i":
        if _builder.current_atom is None:
            message = "The molecule is empty. There is no current atom."
        else:
            atom = _builder.describe_atoms()[_builder.current_atom - 1]
            name = ELEMENT_NAMES[atom["symbol"]]
            message = "You are at atom {}, {}.".format(_builder.current_atom, name)
        return dict(ok=True, message=message, **_snapshot())
    # "skip" stops speech. Over HTTP the browser owns playback, so just
    # acknowledge it; the frontend stops its own speech on seeing this.
    if action == "skip":
        return dict(ok=True, message="Stopped.", **_snapshot())
    # Terminal-only actions have no meaning over HTTP; report them politely
    # rather than erroring. The website drives speech/saving on its own side.
    if action in ("quit", "faster", "slower", "save", "show"):
        return dict(ok=True, message="That command is not used on the website.",
                    **_snapshot())

    # State-changing actions: dispatch to the Builder (RDKit validates).
    ok, message = _dispatch_edit(action, command)
    if ok:
        _version += 1
    return dict(ok=ok, message=message, **_snapshot())

def _dispatch_edit(action: str, command: Dict[str, Any]) -> Tuple[bool, str]:
    """Route a state-changing action to the matching Builder method."""
    if action == "load_named":
        smiles = library.lookup(command["name"])
        if smiles is None:
            return False, ("I don't have that molecule in the library. You can "
                           "build it step by step, or try: aspirin, glucose, "
                           "acetic acid.")
        return _builder.load_molecule(smiles)
    if action == "add_atom":
        return _builder.add_atom(command["symbol"], command["bond_order"], command.get("to_atom"))
    if action == "add_chain":
        return _builder.add_chain(command["count"], to_atom=command.get("to_atom"))
    if action == "add_group":
        return _builder.add_group(command["name"], command.get("to_atom"))
    if action == "add_ring":
        return _builder.add_ring(command["kind"], to_atom=command.get("to_atom"))
    if action == "connect":
        return _builder.connect(command["a"], command["b"], command["bond_order"])
    if action == "close_ring":
        return _builder.connect(_builder.current_atom, 1)
    if action == "set_bond_order":
        return _builder.set_bond_order(command["a"], command["b"], command["order"])
    if action == "delete_atom":
        return _builder.delete_atom(command["atom_number"])
    if action == "reset":
        return _builder.reset()
    if action == "go_to":
        return _builder.go_to(command["atom_number"])
    if action == "undo":
        return _builder.undo()
    # parse() only returns known actions, so this is defensive.
    return False, UNKNOWN_MESSAGE

def _svg() -> Optional[str]:
    """Draw the current molecule as numbered SVG, or None when empty."""
    molecule = _builder.molecule_copy()
    if molecule.GetNumAtoms() == 0:
        return None
    for atom in molecule.GetAtoms():
        atom.SetProp("atomNote", str(atom.GetIdx() + 1))
    highlighted = ([] if _builder.current_atom is None
                   else [_builder.current_atom - 1])
    drawer = rdMolDraw2D.MolDraw2DSVG(600, 450)
    rdMolDraw2D.PrepareAndDrawMolecule(
        drawer, molecule, highlightAtoms=highlighted,
        highlightAtomColors={i: (1.0, 0.8, 0.3) for i in highlighted},
    )
    drawer.FinishDrawing()
    return drawer.GetDrawingText()

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
            molecule = _builder.molecule_copy()
            if molecule.GetNumAtoms() == 0:
                return ("", 204)
            ok, _ = export.save_image(_builder, export.CURRENT_IMAGE)
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
    global _builder, _version
    _builder = Builder()
    _version = 0

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
