"""The named-molecule library: every entry is C/H/O and loads correctly."""

import pytest
from rdkit import Chem

import library
from builder import Builder
from parser import parse

@pytest.mark.parametrize("name", library.names())
def test_every_entry_loads_and_matches(name):
    smiles = library.lookup(name)
    builder = Builder()
    ok, message = builder.load_molecule(smiles)
    assert ok, message
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(smiles)

@pytest.mark.parametrize("name", library.names())
def test_every_entry_is_a_supported_element_only(name):
    # Every library structure must contain only elements the tool supports
    # (carbon, oxygen, and the halogens); hydrogens are implicit.
    from builder import ELEMENT_NAMES
    molecule = Chem.MolFromSmiles(library.lookup(name))
    assert molecule is not None
    assert all(a.GetSymbol() in ELEMENT_NAMES for a in molecule.GetAtoms())

@pytest.mark.parametrize("spelling", [
    "aspirin", "Aspirin", "  ASPIRIN  ", "acetylsalicylic acid",
])
def test_synonyms_and_normalization_resolve_to_same_structure(spelling):
    assert library.lookup(spelling) == library.lookup("aspirin")

@pytest.mark.parametrize("spelling", ["propan-2-ol", "propan 2 ol", "isopropanol",
                                       "rubbing alcohol", "isopropyl alcohol"])
def test_punctuation_insensitive_lookup(spelling):
    assert library.lookup(spelling) == "CC(O)C"

@pytest.mark.parametrize("name", ["", "   ", "unobtainium", "water", "ammonia",
                                   "glucose phosphate", None])
def test_unknown_names_return_none_never_guess(name):
    assert library.lookup(name) is None

def test_load_molecule_rejects_unsupported_elements():
    from builder import UNSUPPORTED_ELEMENT_MESSAGE
    builder = Builder()
    ok, message = builder.load_molecule("CCN")        # nitrogen: still unsupported
    assert ok is False
    assert message == UNSUPPORTED_ELEMENT_MESSAGE
    assert builder.smiles() == ""                      # unchanged

def test_load_molecule_accepts_halogen():
    builder = Builder()
    ok, message = builder.load_molecule("CCl")        # chloromethane: now supported
    assert ok is True
    assert builder.smiles() == "CCl"

@pytest.mark.parametrize("bad", ["", "not a smiles", "C(C", None, 5])
def test_load_molecule_handles_bad_input(bad):
    builder = Builder()
    ok, message = builder.load_molecule(bad)
    assert ok is False
    assert isinstance(message, str) and message.strip()
    assert builder.smiles() == ""

def test_load_molecule_is_one_undo_step():
    builder = Builder()
    builder.add_atom("C")
    assert builder.load_molecule("c1ccccc1")[0]
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("c1ccccc1")
    assert builder.undo()[0]
    assert builder.smiles() == "C"                     # back to the single carbon

def test_naphthalene_fused_rings_load():
    # Fused aromatic rings were the tricky case: valence must be checked after
    # kekulization, not on the raw aromatic bonds.
    builder = Builder()
    assert builder.load_molecule(library.lookup("naphthalene"))[0]
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("c1ccc2ccccc2c1")

@pytest.mark.parametrize("verb", ["build", "load", "make"])
def test_parser_recognizes_named_commands(verb):
    assert parse(verb + " aspirin") == {"action": "load_named", "name": "aspirin"}
    assert parse(verb + " acetic acid") == {"action": "load_named", "name": "acetic acid"}

def test_parser_named_command_tolerates_punctuation_and_case():
    assert parse("BUILD Glucose!") == {"action": "load_named", "name": "glucose"}
    assert parse("make propan-2-ol") == {"action": "load_named", "name": "propan 2 ol"}

def test_names_list_is_nonempty_and_sorted():
    names = library.names()
    assert len(names) > 20
    assert names == sorted(names)
