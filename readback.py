"""Turn public Builder descriptions into text suitable for speaking aloud."""

from builder import Builder, ELEMENT_NAMES


_NAMES = ELEMENT_NAMES
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
    """Name the cursor first, then describe every atom, stating each bond once."""
    atoms = builder.describe_atoms()
    if not atoms:
        return "The molecule is empty."
    current = next(atom for atom in atoms if atom["number"] == builder.current_atom)
    sentences = ["The current atom is atom {}, {}.".format(
        current["number"], _NAMES[current["symbol"]],
    )]
    for atom in atoms:
        hydrogens = atom["implicit_hydrogens"]
        hydrogen_text = _count(hydrogens, "hydrogen") if hydrogens else "no hydrogens"
        # State each bond once, from the lower-numbered atom only, so a bond is
        # not repeated from both ends. Bonds to lower numbers were already named.
        forward = [bond for bond in atom["bonds"] if bond["atom"] > atom["number"]]
        bonds = [
            "to atom {} by a {}".format(bond["atom"], _BONDS[bond["order"]])
            for bond in forward
        ]
        if bonds:
            bond_text = ", bonded " + _join(bonds)
        elif not atom["bonds"]:
            bond_text = ", not bonded to anything yet"
        else:
            # Every bond was already stated by a lower-numbered atom.
            bond_text = ""
        sentences.append("Atom {}, {}, with {}{}.".format(
            atom["number"], _NAMES[atom["symbol"]], hydrogen_text, bond_text,
        ))
    return " ".join(sentences)


def detail_segments(builder: Builder) -> list:
    """Structured readback for synced highlighting.

    Returns a list of segments, each a dict with:
      - text: the phrase to speak for this segment
      - highlight: {"atom": n} or {"bond": [a, b]} or None

    Concatenating the segment texts with single spaces reproduces detail().
    """
    atoms = builder.describe_atoms()
    if not atoms:
        return [{"text": "The molecule is empty.", "highlight": None}]
    current = next(atom for atom in atoms if atom["number"] == builder.current_atom)
    segments = [{
        "text": "The current atom is atom {}, {}.".format(
            current["number"], _NAMES[current["symbol"]]),
        "highlight": {"atom": current["number"]},
    }]
    for atom in atoms:
        hydrogens = atom["implicit_hydrogens"]
        hydrogen_text = _count(hydrogens, "hydrogen") if hydrogens else "no hydrogens"
        forward = [bond for bond in atom["bonds"] if bond["atom"] > atom["number"]]
        # The atom clause. If it has no forward bonds, the sentence ends here;
        # otherwise it continues into bond segments, so end with "bonded".
        if forward:
            atom_text = "Atom {}, {}, with {}, bonded".format(
                atom["number"], _NAMES[atom["symbol"]], hydrogen_text)
        elif not atom["bonds"]:
            atom_text = "Atom {}, {}, with {}, not bonded to anything yet.".format(
                atom["number"], _NAMES[atom["symbol"]], hydrogen_text)
        else:
            atom_text = "Atom {}, {}, with {}.".format(
                atom["number"], _NAMES[atom["symbol"]], hydrogen_text)
        segments.append({"text": atom_text, "highlight": {"atom": atom["number"]}})
        # One segment per forward bond, highlighting that bond.
        for index, bond in enumerate(forward):
            connector = "to atom {} by a {}".format(bond["atom"], _BONDS[bond["order"]])
            # Join wording: "A and B." for the final bond when there are two,
            # commas otherwise, matching _join used by detail().
            if len(forward) == 1:
                text = connector + "."
            elif index < len(forward) - 1:
                text = connector + ("," if len(forward) > 2 else "")
            else:
                text = "and " + connector + "."
            segments.append({
                "text": text,
                "highlight": {"bond": [atom["number"], bond["atom"]]},
            })
    return segments
