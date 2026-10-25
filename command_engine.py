"""Shared deterministic command engine for HTTP and AI voice frontends."""

from typing import Any, Dict, Optional, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D
import library
import naming
from builder import Builder, ELEMENT_NAMES, UNSUPPORTED_ELEMENT_MESSAGE
from parser import parse
from readback import detail, detail_segments, summary
from main import HELP_TEXT, OPTIONS_TEXT


WHITE = (1.0, 1.0, 1.0, 1.0)

# CPK element colours (RGB) for the elements this app places. Carbon and
# hydrogen are kept white so bonds and the skeleton read on the dark card;
# heteroatoms keep their standard CPK colours for quick recognition.
_CPK_PALETTE = {
    -1: WHITE,                      # default (covers carbon and anything else)
    1:  (1.00, 1.00, 1.00),         # H  white
    6:  (1.00, 1.00, 1.00),         # C  white (visible on dark green)
    8:  (1.00, 0.20, 0.20),         # O  red
    9:  (0.56, 0.88, 0.31),         # F  green
    17: (0.12, 0.94, 0.12),         # Cl green
    35: (0.80, 0.33, 0.20),         # Br orange-brown
    53: (0.62, 0.21, 0.62),         # I  purple
}


def _white_drawing(options):
    """Draw on the dark structure card: white carbon/bonds/numbers with CPK
    colours for heteroatoms, on a transparent background."""
    options.setAtomPalette(_CPK_PALETTE)  # CPK symbols; carbon/default white
    options.setAnnotationColour(WHITE)    # the 1-based atom numbers
    options.setAtomNoteColour(WHITE)
    options.setBondNoteColour(WHITE)
    options.clearBackground = False       # keep transparent; card shows through
    return options


ELEMENT_MESSAGE = UNSUPPORTED_ELEMENT_MESSAGE
UNKNOWN_MESSAGE = ("I didn't understand that. "
                   "Try: add carbon; add oxygen double bond; go to atom 3.")


class CommandEngine:
    def __init__(self):
        self.builder = Builder()
        self.version = 0

    def snapshot(self) -> Dict[str, Any]:
        """Return the current molecule as the shared JSON shape (no 'ok'/'message')."""
        atoms = self.builder.describe_atoms()
        return {
            "smiles": self.builder.smiles() or "",
            "summary": summary(self.builder),
            "detail": detail(self.builder),
            "readback_segments": detail_segments(self.builder),
            "current_atom": self.builder.current_atom,
            "atoms": atoms,
            "image_url": "/image?v={}".format(self.version),
        }

    def run_command(self, text: str) -> Dict[str, Any]:
        """Run one command string and return the full API response dict.

        Pure data in, data out: no printing, no speech, no image files. The web
        layer and any test can call this directly.
        """
        command = parse(text)
        if command is None:
            return dict(ok=False, message=UNKNOWN_MESSAGE, **self.snapshot())

        action = command["action"]

        # Read-only / informational actions: never change the molecule.
        if action in ("read_back", "summary"):
            message = detail(self.builder) if action == "read_back" else summary(self.builder)
            return dict(ok=True, message=message, **self.snapshot())
        if action == "name":
            if self.builder.current_atom is None:
                return dict(ok=True, message="The molecule is empty.", **self.snapshot())
            common, iupac, message = naming.lookup_name(self.builder.smiles())
            result = dict(ok=True, message=message, **self.snapshot())
            result["common_name"] = common
            result["iupac_name"] = iupac
            return result
        if action == "unsupported_element":
            return dict(ok=False, message=ELEMENT_MESSAGE, **self.snapshot())
        if action == "help":
            return dict(ok=True, message=HELP_TEXT, **self.snapshot())
        if action == "what_can_i_add":
            return dict(ok=True, message=OPTIONS_TEXT, **self.snapshot())
        if action == "where_am_i":
            if self.builder.current_atom is None:
                message = "The molecule is empty. There is no current atom."
            else:
                atom = self.builder.describe_atoms()[self.builder.current_atom - 1]
                name = ELEMENT_NAMES[atom["symbol"]]
                message = "You are at atom {}, {}.".format(self.builder.current_atom, name)
            return dict(ok=True, message=message, **self.snapshot())
        # "skip" stops speech. Over HTTP the browser owns playback, so just
        # acknowledge it; the frontend stops its own speech on seeing this.
        if action == "skip":
            return dict(ok=True, message="Stopped.", speech_action="stop", **self.snapshot())
        # Terminal-only actions have no meaning over HTTP; report them politely
        # rather than erroring. The website drives speech/saving on its own side.
        if action in ("quit", "faster", "slower", "save", "show"):
            return dict(ok=True, message="That command is not used on the website.",
                        **self.snapshot())

        # State-changing actions: dispatch to the Builder (RDKit validates).
        ok, message = self.dispatch_edit(action, command)
        if ok:
            self.version += 1
        return dict(ok=ok, message=message, **self.snapshot())

    def dispatch_edit(self, action: str, command: Dict[str, Any]) -> Tuple[bool, str]:
        """Route a state-changing action to the matching Builder method."""
        if action == "load_named":
            smiles = library.lookup(command["name"])
            if smiles is None:
                return False, ("I don't have that molecule in the library. You can "
                               "build it step by step, or try: aspirin, glucose, "
                               "acetic acid.")
            return self.builder.load_molecule(smiles)
        if action == "add_atom":
            return self.builder.add_atom(command["symbol"], command["bond_order"], command.get("to_atom"))
        if action == "add_chain":
            return self.builder.add_chain(command["count"], to_atom=command.get("to_atom"))
        if action == "add_group":
            return self.builder.add_group(command["name"], command.get("to_atom"))
        if action == "add_ring":
            return self.builder.add_ring(command["kind"], to_atom=command.get("to_atom"))
        if action == "connect":
            return self.builder.connect(command["a"], command["b"], command["bond_order"])
        if action == "close_ring":
            return self.builder.connect(self.builder.current_atom, 1)
        if action == "set_bond_order":
            return self.builder.set_bond_order(command["a"], command["b"], command["order"])
        if action == "delete_atom":
            return self.builder.delete_atom(command["atom_number"])
        if action == "reset":
            return self.builder.reset()
        if action == "go_to":
            return self.builder.go_to(command["atom_number"])
        if action == "undo":
            return self.builder.undo()
        # parse() only returns known actions, so this is defensive.
        return False, UNKNOWN_MESSAGE

    def svg(self, highlight_atom=None, highlight_bond=None) -> Optional[str]:
        """Draw the current molecule as numbered SVG, or None when empty.

        During readback, highlight_atom (1-based) or highlight_bond ([a, b],
        1-based) override the default current-atom highlight so the drawing can
        follow the spoken description one atom/bond at a time.
        """
        molecule = self.builder.molecule_copy()
        if molecule.GetNumAtoms() == 0:
            return None
        for atom in molecule.GetAtoms():
            atom.SetProp("atomNote", str(atom.GetIdx() + 1))
        amber = (0.949, 0.694, 0.204, 1.0)
        n = molecule.GetNumAtoms()
        highlight_atoms = []
        highlight_bonds = []
        atom_colors = {}
        bond_colors = {}
        if highlight_bond is not None:
            a, b = highlight_bond
            bond = molecule.GetBondBetweenAtoms(a - 1, b - 1)
            if bond is not None:
                highlight_bonds = [bond.GetIdx()]
                bond_colors = {bond.GetIdx(): amber}
                # Also highlight the two endpoint atoms for clarity.
                highlight_atoms = [i - 1 for i in (a, b) if 1 <= i <= n]
                atom_colors = {i: amber for i in highlight_atoms}
        elif highlight_atom is not None:
            if 1 <= highlight_atom <= n:
                highlight_atoms = [highlight_atom - 1]
                atom_colors = {highlight_atom - 1: amber}
        else:
            # Default: the builder's current atom.
            if self.builder.current_atom is not None:
                idx = self.builder.current_atom - 1
                highlight_atoms = [idx]
                atom_colors = {idx: amber}
        drawer = rdMolDraw2D.MolDraw2DSVG(600, 450)
        _white_drawing(drawer.drawOptions())
        rdMolDraw2D.PrepareAndDrawMolecule(
            drawer, molecule,
            highlightAtoms=highlight_atoms, highlightAtomColors=atom_colors,
            highlightBonds=highlight_bonds, highlightBondColors=bond_colors,
        )
        drawer.FinishDrawing()
        return drawer.GetDrawingText()

    def structure_3d(self) -> Optional[str]:
        """Return the current molecule as a 3D MolBlock, or None if unavailable.

        RDKit adds explicit hydrogens and computes a plausible 3D conformer; the
        browser (3Dmol.js) renders and spins it. This is a computed conformer,
        not experimental coordinates, and stereochemistry is not modeled -- it
        is a reasonable 3D shape of the structure the user built. Returns None
        for an empty molecule or if 3D embedding fails, so the caller degrades
        gracefully instead of raising.
        """
        molecule = self.builder.molecule_copy()
        if molecule.GetNumAtoms() == 0:
            return None
        try:
            molecule = Chem.AddHs(molecule)
            if AllChem.EmbedMolecule(molecule, randomSeed=42) != 0:
                return None
            try:
                AllChem.MMFFOptimizeMolecule(molecule)
            except Exception:
                pass
            return Chem.MolToMolBlock(molecule)
        except Exception:
            return None
