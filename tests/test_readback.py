"""Spoken descriptions use added atom numbers and words for bond types."""

import pytest

from builder import Builder
from readback import detail, summary


def molecule(additions):
    builder = Builder()
    for symbol, order in additions:
        assert builder.add_atom(symbol, order)[0]
    return builder


def test_empty():
    builder = Builder()
    assert summary(builder) == "The molecule is empty."
    assert detail(builder) == "The molecule is empty."


def test_single_carbon():
    builder = molecule([("C", 1)])
    assert summary(builder) == "1 carbon, 1 atom in total, 4 hydrogens."
    assert detail(builder) == (
        "Atom 1, carbon, with 4 hydrogens, not bonded to anything yet. "
        "The current atom is atom 1, carbon."
    )


def test_ethanol():
    builder = molecule([("C", 1), ("C", 1), ("O", 1)])
    assert summary(builder) == "2 carbons and 1 oxygen, 3 atoms in total, 6 hydrogens."
    assert detail(builder) == (
        "Atom 1, carbon, with 3 hydrogens, bonded to atom 2 by a single bond. "
        "Atom 2, carbon, with 2 hydrogens, bonded to atom 1 by a single bond "
        "and to atom 3 by a single bond. "
        "Atom 3, oxygen, with 1 hydrogen, bonded to atom 2 by a single bond. "
        "The current atom is atom 3, oxygen."
    )


def test_acetone():
    builder = molecule([("C", 1), ("C", 1), ("C", 1)])
    assert builder.go_to(2)[0]
    assert builder.add_atom("O", 2)[0]
    assert summary(builder) == "3 carbons and 1 oxygen, 4 atoms in total, 6 hydrogens."
    assert detail(builder) == (
        "Atom 1, carbon, with 3 hydrogens, bonded to atom 2 by a single bond. "
        "Atom 2, carbon, with no hydrogens, bonded to atom 1 by a single bond, "
        "to atom 3 by a single bond, and to atom 4 by a double bond. "
        "Atom 3, carbon, with 3 hydrogens, bonded to atom 2 by a single bond. "
        "Atom 4, oxygen, with no hydrogens, bonded to atom 2 by a double bond. "
        "The current atom is atom 4, oxygen."
    )
    # Cursor moves and undo must be reflected without changing atom order.
    assert builder.go_to(1)[0]
    assert detail(builder).endswith("The current atom is atom 1, carbon.")
    assert builder.undo()[0]
    assert detail(builder).endswith("The current atom is atom 4, oxygen.")


@pytest.mark.parametrize("order, word, middle_hydrogens, last_hydrogens, total", [
    (2, "double", "1 hydrogen", "2 hydrogens", 6),
    (3, "triple", "no hydrogens", "1 hydrogen", 4),
])
def test_propene_and_propyne(order, word, middle_hydrogens, last_hydrogens, total):
    builder = molecule([("C", 1), ("C", 1), ("C", order)])
    assert summary(builder) == "3 carbons, 3 atoms in total, {} hydrogens.".format(total)
    assert detail(builder) == (
        "Atom 1, carbon, with 3 hydrogens, bonded to atom 2 by a single bond. "
        "Atom 2, carbon, with {}, bonded to atom 1 by a single bond "
        "and to atom 3 by a {} bond. "
        "Atom 3, carbon, with {}, bonded to atom 2 by a {} bond. "
        "The current atom is atom 3, carbon."
    ).format(middle_hydrogens, word, last_hydrogens, word)


def test_singular_and_plural_oxygen():
    builder = molecule([("O", 1)])
    assert summary(builder) == "1 oxygen, 1 atom in total, 2 hydrogens."
    assert builder.add_atom("O")[0]
    assert summary(builder) == "2 oxygens, 2 atoms in total, 2 hydrogens."
    assert detail(builder) == (
        "Atom 1, oxygen, with 1 hydrogen, bonded to atom 2 by a single bond. "
        "Atom 2, oxygen, with 1 hydrogen, bonded to atom 1 by a single bond. "
        "The current atom is atom 2, oxygen."
    )
