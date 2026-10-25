"""Draw numbered skeletal structures and open them with the platform viewer."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Tuple, Union

from rdkit.Chem.Draw import rdMolDraw2D

from builder import Builder


WHITE = (1.0, 1.0, 1.0, 1.0)


CURRENT_IMAGE = Path("outputs/current.png")
PLATFORM = sys.platform


def _open_file(path):
    if PLATFORM == "win32":
        os.startfile(str(path))
    else:
        command = "open" if PLATFORM == "darwin" else "xdg-open"
        subprocess.run([command, str(path)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def save_image(builder: Builder, path: Union[str, Path]) -> Tuple[bool, str]:
    """Save a PNG; return success and a plain-language message on every path."""
    molecule = builder.molecule_copy()
    if molecule.GetNumAtoms() == 0:
        return False, "The molecule is empty. Add an atom before drawing it."
    try:
        destination = Path(path)
        if destination.suffix.lower() != ".png":
            return False, "Choose an image path ending in .png."
        destination.parent.mkdir(parents=True, exist_ok=True)
        for atom in molecule.GetAtoms():
            # Notes preserve the usual skeletal carbon and oxygen rendering.
            atom.SetProp("atomNote", str(atom.GetIdx() + 1))
        highlighted = [] if builder.current_atom is None else [builder.current_atom - 1]
        drawer = rdMolDraw2D.MolDraw2DCairo(800, 600)
        options = drawer.drawOptions()
        # CPK symbols with white carbon/bonds so they read on the dark backdrop.
        options.setAtomPalette({
            -1: WHITE, 1: (1.0, 1.0, 1.0), 6: (1.0, 1.0, 1.0),
            8: (1.0, 0.2, 0.2), 9: (0.56, 0.88, 0.31), 17: (0.12, 0.94, 0.12),
            35: (0.8, 0.33, 0.2), 53: (0.62, 0.21, 0.62),
        })
        options.annotationColour = WHITE          # white atom numbers
        options.setBackgroundColour((0.11, 0.30, 0.20, 1.0))  # dark green so white reads
        rdMolDraw2D.PrepareAndDrawMolecule(
            drawer, molecule, highlightAtoms=highlighted,
            highlightAtomColors={index: (0.949, 0.694, 0.204, 1.0) for index in highlighted},
        )
        drawer.FinishDrawing()
        destination.write_bytes(drawer.GetDrawingText())
        return True, "Saved molecule image to {}.".format(destination)
    except Exception:
        # Drawing and filesystem failures must not interrupt molecule building.
        return False, "Could not save the molecule image. Check the output path and permissions."


def show_image(builder: Builder, path: Union[str, Path] = CURRENT_IMAGE) -> Tuple[bool, str]:
    """Refresh before opening so a previous session's image is never shown."""
    success, message = save_image(builder, path)
    if not success:
        return False, message
    try:
        _open_file(Path(path).resolve())
        return True, "Opened the current molecule image."
    except (OSError, subprocess.SubprocessError):
        return False, "Could not open the molecule image. It is still saved on disk."
