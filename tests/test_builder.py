"""Exercise the builder through its public API (Python 3.9 compatible)."""

import pytest
from rdkit import Chem

from builder import Builder


def assert_success(result):
    ok, message = result
    assert ok is True
    assert isinstance(message, str) and message.strip()


def assert_rejected(builder, action, *args):
    before = builder.smiles()
    atoms_before = builder.describe_atoms()
    ok, message = action(*args)
    assert ok is False
    assert isinstance(message, str) and message.strip()
    assert builder.smiles() == before
    assert builder.describe_atoms() == atoms_before


def build(actions):
    builder = Builder()
    for method, args in actions:
        assert_success(getattr(builder, method)(*args))
    return builder


@pytest.mark.parametrize(
    "expected, actions",
    [
        ("C=CC", [("add_atom", ("C",)), ("add_atom", ("C", 2)),
                   ("add_atom", ("C",))]),
        ("C#CC", [("add_atom", ("C",)), ("add_atom", ("C", 3)),
                   ("add_atom", ("C",))]),
        ("CCO", [("add_atom", ("C",)), ("add_atom", ("C",)),
                  ("add_atom", ("O",))]),
        ("CC(C)=O", [("add_atom", ("C",)), ("add_atom", ("C",)),
                      ("add_atom", ("O", 2)), ("go_to", (2,)),
                      ("add_atom", ("C",))]),
        ("CCC(=O)O", [("add_atom", ("C",)), ("add_atom", ("C",)),
                       ("add_atom", ("C",)), ("add_atom", ("O", 2)),
                       ("go_to", (3,)), ("add_atom", ("O",))]),
        ("COC", [("add_atom", ("C",)), ("add_atom", ("O",)),
                  ("add_atom", ("C",))]),
        ("CC(C)C", [("add_atom", ("C",)), ("add_atom", ("C",)),
                     ("add_atom", ("C",)), ("go_to", (2,)),
                     ("add_atom", ("C",))]),
    ],
    ids=["propene", "propyne", "ethanol", "acetone", "propanoic-acid",
         "dimethyl-ether", "isobutane"],
)
def test_build_molecules(expected, actions):
    builder = build(actions)
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)


def test_carbon_rejects_fifth_bond():
    builder = Builder()
    assert_success(builder.add_atom("C"))
    for _ in range(4):
        assert_success(builder.go_to(1))
        assert_success(builder.add_atom("C"))
    assert_success(builder.go_to(1))
    assert_rejected(builder, builder.add_atom, "C")


@pytest.mark.parametrize("oxygen_bonds", ["two-single", "one-double"])
def test_saturated_oxygen_rejects_another_atom(oxygen_bonds):
    builder = Builder()
    assert_success(builder.add_atom("O"))
    if oxygen_bonds == "two-single":
        assert_success(builder.add_atom("C"))
        assert_success(builder.go_to(1))
        assert_success(builder.add_atom("C"))
    else:
        assert_success(builder.add_atom("C", 2))
    assert_success(builder.go_to(1))
    assert_rejected(builder, builder.add_atom, "C")


@pytest.mark.parametrize("number", [0, -1, 3])
def test_go_to_rejects_missing_atom(number):
    builder = build([("add_atom", ("C",)), ("add_atom", ("O",))])
    assert_rejected(builder, builder.go_to, number)
    # The failed move must preserve the oxygen cursor and add no undo entry.
    assert_success(builder.undo())
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("C")


@pytest.mark.parametrize("bond_order", [1, 2, 3])
def test_first_atom_has_no_bond(bond_order):
    # Stage 2 defines initial bond orders as ignored: no separate bonded-add API.
    builder = Builder()
    assert_success(builder.add_atom("O", bond_order))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("O")
    assert builder.describe_atoms()[0]["bonds"] == []


def test_undo_empty_molecule():
    builder = Builder()
    assert_rejected(builder, builder.undo)


@pytest.mark.parametrize("symbol", ["N", "H", "Cl", "", "carbon"])
@pytest.mark.parametrize("populated", [False, True])
def test_rejects_unsupported_elements(symbol, populated):
    builder = Builder()
    if populated:
        assert_success(builder.add_atom("C"))
    assert_rejected(builder, builder.add_atom, symbol)


def test_undo_add_restores_molecule_and_cursor():
    builder = build([("add_atom", ("C",)), ("add_atom", ("O",))])
    before = builder.smiles()
    assert_success(builder.add_atom("C"))
    assert_success(builder.undo())
    assert builder.smiles() == before
    assert_success(builder.add_atom("C"))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("COC")


def test_undo_first_add_returns_to_empty():
    builder = build([("add_atom", ("C",))])
    assert_success(builder.undo())
    assert builder.smiles() == ""
    assert builder.describe_atoms() == []
    assert_rejected(builder, builder.undo)


def test_undo_go_to_restores_cursor():
    builder = build([("add_atom", ("C",)), ("add_atom", ("O",))])
    before = builder.smiles()
    assert_success(builder.go_to(1))
    assert_success(builder.undo())
    assert builder.smiles() == before
    assert_success(builder.add_atom("C"))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("COC")


def test_atoms_are_numbered_in_added_order():
    builder = build([
        ("add_atom", ("O",)), ("add_atom", ("C",)),
        ("add_atom", ("C",)), ("go_to", (2,)), ("add_atom", ("O",)),
    ])
    atoms = builder.describe_atoms()
    assert [(atom["number"], atom["symbol"]) for atom in atoms] == [
        (1, "O"), (2, "C"), (3, "C"), (4, "O"),
    ]
    assert [atom["bonds"] for atom in atoms] == [
        [{"atom": 2, "order": 1}],
        [{"atom": 1, "order": 1}, {"atom": 3, "order": 1},
         {"atom": 4, "order": 1}],
        [{"atom": 2, "order": 1}],
        [{"atom": 2, "order": 1}],
    ]


MOLECULES = [
    ("cyclohexane", "C1CCCCC1"), ("benzene", "c1ccccc1"),
    ("toluene", "Cc1ccccc1"), ("phenol", "Oc1ccccc1"),
    ("cyclohexanol", "OC1CCCCC1"), ("benzoic acid", "O=C(O)c1ccccc1"),
    ("acetic acid", "CC(=O)O"), ("ethyl acetate", "CC(=O)OCC"),
    ("diethyl ether", "CCOCC"), ("tetrahydrofuran", "C1CCOC1"),
    ("ethylene glycol", "OCCO"), ("glycerol", "OCC(O)CO"),
    ("naphthalene", "c1ccc2ccccc2c1"),
    ("aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
    ("menthol", "CC(C)C1CCC(C)CC1O"),
    ("glucose", "OCC1OC(O)C(O)C(O)C1O"),
]


@pytest.mark.parametrize("name, expected", MOLECULES, ids=[m[0] for m in MOLECULES])
def test_complex_molecules_through_public_edits(name, expected):
    # Use a reference graph only to describe the construction recipe. All actual
    # molecule construction goes through add_atom/connect, including fused rings.
    reference = Chem.MolFromSmiles(expected)
    Chem.Kekulize(reference, clearAromaticFlags=True)
    builder = Builder()
    for atom in reference.GetAtoms():
        earlier = [b for b in atom.GetBonds()
                   if b.GetOtherAtomIdx(atom.GetIdx()) < atom.GetIdx()]
        if not earlier:
            assert_success(builder.add_atom(atom.GetSymbol()))
        else:
            first, *remaining = earlier
            target = first.GetOtherAtomIdx(atom.GetIdx()) + 1
            assert_success(builder.add_atom(atom.GetSymbol(), int(first.GetBondTypeAsDouble()), target))
            for bond in remaining:
                assert_success(builder.connect(atom.GetIdx() + 1,
                    bond.GetOtherAtomIdx(atom.GetIdx()) + 1, int(bond.GetBondTypeAsDouble())))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)
    assert all(b["order"] in (1, 2, 3) for a in builder.describe_atoms() for b in a["bonds"])


@pytest.mark.parametrize("kind, expected", [
    ("cyclopropane", "C1CC1"), ("cyclobutane", "C1CCC1"),
    ("cyclopentane", "C1CCCC1"), ("cyclohexane", "C1CCCCC1"),
    ("benzene", "c1ccccc1"),
])
@pytest.mark.parametrize("attached", [False, True])
def test_ring_templates(kind, expected, attached):
    builder = Builder()
    if attached:
        assert_success(builder.add_atom("C"))
    before = state(builder)
    assert_success(builder.add_ring(kind))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(("C" if attached else "") + expected)
    assert_success(builder.undo())
    assert state(builder) == before


def state(builder):
    return builder.smiles(), builder.describe_atoms(), builder.current_atom


@pytest.mark.parametrize("group, expected", [
    ("methyl", "CC"), ("ethyl", "CCC"), ("hydroxyl", "CO"),
    ("methoxy", "COC"), ("aldehyde", "CC=O"),
    ("carboxylic_acid", "CC(=O)O"),
])
def test_group_shortcuts_and_undo(group, expected):
    builder = build([("add_atom", ("C",))])
    before = state(builder)
    assert_success(builder.add_group(group, to_atom=1))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)
    assert_success(builder.undo())
    assert state(builder) == before


@pytest.mark.parametrize("method, args", [
    ("connect", (1, 3)), ("set_bond_order", (1, 2, 2)),
    ("delete_atom", (2,)), ("reset", ()), ("add_chain", (5,)),
    ("add_atom", ("O", 1, 1)),
])
def test_each_edit_is_one_undo_step(method, args):
    builder = build([("add_chain", (3,))])
    before = state(builder)
    assert_success(getattr(builder, method)(*args))
    assert_success(builder.undo())
    assert state(builder) == before
    assert_success(builder.undo())
    assert state(builder) == ("", [], None)


@pytest.mark.parametrize("method, args", [
    ("connect", (1, 2)), ("connect", (1, 1)), ("connect", (1, 99)),
    ("connect", (1, 3, 4)), ("set_bond_order", (1, 2, 3)),
    ("set_bond_order", (1, 3, 1)), ("set_bond_order", (1, 2, True)),
    ("delete_atom", (0,)), ("delete_atom", (99,)), ("delete_atom", (True,)),
    ("add_atom", ("C", 1, 99)), ("add_atom", ("C", 1, False)),
    ("add_chain", (31,)), ("add_chain", (0,)), ("add_chain", (True,)),
    ("add_chain", (3, 3)), ("add_group", ("unknown",)),
    ("add_group", ("ethyl", 99)), ("add_ring", ("unknown",)),
])
def test_failed_edits_preserve_cursor_and_history(method, args):
    builder = build([("add_atom", ("C",)), ("add_atom", ("O",)), ("add_atom", ("C",))])
    before = state(builder)
    assert_rejected(builder, getattr(builder, method), *args)
    assert state(builder) == before
    assert_success(builder.undo())
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("CO")


@pytest.mark.parametrize("method, args", [
    ("add_chain", (3, 3)), ("add_group", ("methoxy",)),
    ("add_group", ("carboxylic_acid",)), ("add_ring", ("benzene",)),
])
def test_compound_failure_rolls_back_everything(method, args):
    # Oxygen has one remaining valence: methoxy/acid/ring fail on attachment
    # when saturated; a triple-bond chain fails after its second carbon.
    builder = build([("add_atom", ("O",)), ("add_atom", ("C",)),
                     ("add_atom", ("C", 1, 1)), ("go_to", (1,))])
    if method == "add_chain":
        assert_success(builder.reset())
    before = state(builder)
    history_length = len(builder._history)
    assert_rejected(builder, getattr(builder, method), *args)
    assert state(builder) == before
    assert len(builder._history) == history_length


@pytest.mark.parametrize("symbol", ["N", "S", "F", "Cl", "Br", "I", "H", None, 6])
def test_element_rejection_message(symbol):
    builder = Builder()
    assert builder.add_atom(symbol) == (False, "Only carbon and oxygen can be added. Hydrogens are added automatically.")


@pytest.mark.parametrize("cursor, deleted, expected_cursor", [(3, 1, 2), (2, 2, 1), (1, 1, 1), (1, 3, 1)])
def test_delete_renumbers_and_repairs_cursor(cursor, deleted, expected_cursor):
    builder = build([("add_chain", (3,)), ("go_to", (cursor,))])
    before = state(builder)
    assert_success(builder.delete_atom(deleted))
    assert builder.current_atom == expected_cursor
    assert [a["number"] for a in builder.describe_atoms()] == [1, 2]
    assert_success(builder.undo())
    assert state(builder) == before


def test_delete_last_atom_and_reset_empty_are_undoable():
    builder = build([("add_atom", ("O",))])
    assert_success(builder.delete_atom(1))
    assert state(builder) == ("", [], None)
    assert_success(builder.reset())
    assert_success(builder.undo())
    assert state(builder) == ("", [], None)
    assert_success(builder.undo())
    assert builder.smiles() == "O"


def test_explicit_group_target_ignores_cursor():
    builder = build([("add_chain", (2,))])
    assert_success(builder.add_group("carboxylic_acid", to_atom=1))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("CCC(=O)O")


@pytest.mark.parametrize("actions, expected", [
    ([("add_atom", ("C",)), ("add_ring", ("benzene",))], "Cc1ccccc1"),
    ([("add_ring", ("benzene",)), ("add_group", ("hydroxyl", 1))], "Oc1ccccc1"),
    ([("add_ring", ("benzene",)), ("add_group", ("carboxylic_acid", 1))], "O=C(O)c1ccccc1"),
    ([("add_ring", ("cyclohexane",)), ("add_group", ("hydroxyl",))], "OC1CCCCC1"),
    ([("add_atom", ("C",)), ("add_group", ("carboxylic_acid",)),
      ("add_group", ("ethyl",))], "CC(=O)OCC"),
    ([("add_group", ("ethyl",)), ("add_group", ("methoxy",)),
      ("add_atom", ("C",))], "CCOCC"),
])
def test_hand_written_shortcut_recipes(actions, expected):
    builder = build(actions)
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)


def test_connect_valence_overflow_is_atomic():
    builder = build([("add_atom", ("O",)), ("add_chain", (3,))])
    before = state(builder)
    assert_rejected(builder, builder.connect, 1, 4, 2)
    assert state(builder) == before
    assert_success(builder.undo())
    assert builder.smiles() == "O"


def test_aromatic_edit_delete_and_undo():
    builder = build([("add_ring", ("benzene",))])
    before = state(builder)
    assert_success(builder.delete_atom(1))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("C=CC=CC")
    assert_success(builder.undo())
    assert state(builder) == before
    assert_success(builder.set_bond_order(1, 2, 1))
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("C1CC=CC=C1")
    assert_success(builder.undo())
    assert state(builder) == before
