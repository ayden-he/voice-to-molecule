"""Real PNG drawing with all macOS window-opening calls mocked."""

import subprocess
from unittest.mock import Mock

import pytest
from rdkit.Chem.Draw import rdMolDraw2D

import export
from builder import Builder


@pytest.fixture
def acetone():
    builder = Builder()
    for symbol, order in [("C", 1), ("C", 1), ("C", 1)]:
        assert builder.add_atom(symbol, order)[0]
    assert builder.go_to(2)[0]
    assert builder.add_atom("O", 2)[0]
    return builder


@pytest.fixture(autouse=True)
def no_windows(monkeypatch):
    opener = Mock()
    monkeypatch.setattr(export.subprocess, "run", opener)
    return opener


def test_acetone_png(acetone, tmp_path, no_windows):
    path = tmp_path / "outputs" / "current.png"
    before = acetone.describe_atoms()
    success, message = export.save_image(acetone, path)
    assert success, message
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data) > 8
    assert acetone.describe_atoms() == before
    assert acetone.current_atom == 4
    no_windows.assert_not_called()


def test_numbering_and_highlight(acetone, tmp_path, monkeypatch):
    original = rdMolDraw2D.PrepareAndDrawMolecule
    seen = []

    def inspect(drawer, molecule, **kwargs):
        seen.append(([atom.GetProp("atomNote") for atom in molecule.GetAtoms()],
                     [atom.GetSymbol() for atom in molecule.GetAtoms()], kwargs))
        return original(drawer, molecule, **kwargs)

    monkeypatch.setattr(rdMolDraw2D, "PrepareAndDrawMolecule", inspect)
    assert export.save_image(acetone, tmp_path / "numbered.png")[0]
    notes, symbols, options = seen[0]
    assert notes == ["1", "2", "3", "4"]
    assert symbols == ["C", "C", "C", "O"]
    assert options["highlightAtoms"] == [3]
    assert not acetone.molecule_copy().GetAtomWithIdx(0).HasProp("atomNote")


def test_empty_writes_nothing(tmp_path, no_windows):
    path = tmp_path / "outputs" / "current.png"
    success, message = export.save_image(Builder(), path)
    assert not success
    assert "empty" in message
    assert not path.parent.exists()
    assert not export.show_image(Builder(), path)[0]
    no_windows.assert_not_called()


@pytest.mark.parametrize("kind", ["blocked_parent", "directory", "wrong_suffix", "null"])
def test_invalid_path(acetone, tmp_path, kind):
    path = tmp_path / "image.png"
    if kind == "blocked_parent":
        blocker = tmp_path / "file"
        blocker.write_text("not a directory")
        path = blocker / "image.png"
    elif kind == "directory":
        path.mkdir()
    elif kind == "wrong_suffix":
        path = tmp_path / "image.txt"
    else:
        path = "bad\0.png"
    success, message = export.save_image(acetone, path)
    assert not success
    assert message


def test_show_uses_argument_list(acetone, tmp_path, no_windows):
    path = tmp_path / "with spaces" / "current.png"
    assert export.show_image(acetone, path)[0]
    no_windows.assert_called_once_with(
        ["open", str(path.resolve())], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.CalledProcessError(1, "open")])
def test_show_failure_is_graceful(acetone, tmp_path, no_windows, error):
    no_windows.side_effect = error
    path = tmp_path / "current.png"
    success, message = export.show_image(acetone, path)
    assert not success
    assert "Could not open" in message
    assert path.exists()
