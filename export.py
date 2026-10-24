"""Draw numbered skeletal structures and open them with macOS."""

from pathlib import Path
import subprocess
from typing import Tuple, Union

from rdkit.Chem.Draw import rdMolDraw2D

from builder import Builder


CURRENT_IMAGE = Path("outputs/current.png")


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
        rdMolDraw2D.PrepareAndDrawMolecule(
            drawer, molecule, highlightAtoms=highlighted,
            highlightAtomColors={index: (1.0, 0.8, 0.3) for index in highlighted},
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
        subprocess.run(["open", str(Path(path).resolve())], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Opened the current molecule image."
    except (OSError, subprocess.SubprocessError):
        return False, "Could not open the molecule image. It is still saved on disk."
