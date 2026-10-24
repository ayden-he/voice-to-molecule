"""Turn public Builder descriptions into text suitable for speaking aloud."""

from builder import Builder


_NAMES = {"C": "carbon", "O": "oxygen"}
_BONDS = {1: "single bond", 2: "double bond", 3: "triple bond"}


def _count(number: int, word: str) -> str:
    """Use a singular noun only for a count of one."""
    return "{} {}{}".format(number, word, "" if number == 1 else "s")


def _join(items: list) -> str:
    """Join spoken lists with an 'and' before the final item."""
    if len(items) < 3:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def summary(builder: Builder) -> str:
    """Report composition and RDKit's implicit hydrogen total."""
    atoms = builder.describe_atoms()
    if not atoms:
        return "The molecule is empty."
    composition = []
    for symbol, name in _NAMES.items():
        count = sum(atom["symbol"] == symbol for atom in atoms)
        if count:
            composition.append(_count(count, name))
    hydrogens = sum(atom["implicit_hydrogens"] for atom in atoms)
    return "{}.".format(_join(composition + [_count(hydrogens, "hydrogen")]))


def detail(builder: Builder) -> str:
    """Describe every atom and bond in added order, then name the cursor."""
    atoms = builder.describe_atoms()
    if not atoms:
        return "The molecule is empty."
    sentences = []
    for atom in atoms:
        hydrogens = atom["implicit_hydrogens"]
        hydrogen_text = _count(hydrogens, "hydrogen") if hydrogens else "no hydrogens"
        bonds = [
            "to atom {} by a {}".format(bond["atom"], _BONDS[bond["order"]])
            for bond in atom["bonds"]
        ]
        bond_text = "bonded " + _join(bonds) if bonds else "not bonded to anything yet"
        sentences.append("Atom {}, {}, with {}, {}.".format(
            atom["number"], _NAMES[atom["symbol"]], hydrogen_text, bond_text,
        ))
    current = next(atom for atom in atoms if atom["number"] == builder.current_atom)
    sentences.append("The current atom is atom {}, {}.".format(
        current["number"], _NAMES[current["symbol"]],
    ))
    return " ".join(sentences)
