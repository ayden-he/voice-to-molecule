"""Build small carbon/oxygen molecules, one undoable action at a time."""

from typing import Any, Dict, List, Optional, Tuple

from rdkit import Chem


# The single source of truth for which elements the tool supports. Everything
# else (parser, readback, help, the add-atom check, the library's structure
# check) derives from these, so the supported set is defined in exactly one
# place. Hydrogens stay implicit and are never placed by the user.
ELEMENT_NAMES = {
    "C": "carbon", "O": "oxygen",
    "F": "fluorine", "Cl": "chlorine", "Br": "bromine", "I": "iodine",
}
# Maximum bond-order sum per element. Carbon 4, oxygen 2, halogens 1.
ELEMENT_VALENCE = {"C": 4, "O": 2, "F": 1, "Cl": 1, "Br": 1, "I": 1}

# The plain-language rejection for anything outside the supported set.
UNSUPPORTED_ELEMENT_MESSAGE = (
    "Only carbon, oxygen, and the halogens fluorine, chlorine, bromine, and "
    "iodine can be added. Hydrogens are added automatically."
)


class Builder:
    """Keep an RDKit molecule, a 1-based cursor, and previous states."""

    def __init__(self) -> None:
        self._mol = Chem.RWMol()
        self._current_atom: Optional[int] = None
        self._history: List[Tuple[Chem.RWMol, Optional[int]]] = []

    def _remember(self) -> None:
        # Copy the molecule so later edits cannot change the saved state.
        self._history.append((Chem.RWMol(self._mol), self._current_atom))

    _BONDS = {1: Chem.BondType.SINGLE, 2: Chem.BondType.DOUBLE,
              3: Chem.BondType.TRIPLE}

    def _valid_atom(self, n):
        return type(n) is int and 1 <= n <= self._mol.GetNumAtoms()

    def _commit(self, candidate, current, message):
        """Validate a private copy before saving one undo snapshot."""
        for atom in candidate.GetAtoms():
            used = sum(b.GetBondTypeAsDouble() for b in atom.GetBonds())
            if used > ELEMENT_VALENCE[atom.GetSymbol()]:
                return False, "That bond would exceed the maximum valence of atom {}.".format(atom.GetIdx() + 1)
        try:
            Chem.SanitizeMol(candidate)
            # Store explicit single/double bonds so edits and readback never
            # mistake an aromatic bond (1.5) for a single bond.
            Chem.Kekulize(candidate, clearAromaticFlags=True)
        except Exception:
            return False, "That change could not be made. The molecule has not changed."
        self._remember()
        self._mol, self._current_atom = candidate, current
        return True, message

    def add_atom(self, symbol: str, bond_order: int = 1,
                 to_atom: Optional[int] = None) -> Tuple[bool, str]:
        """Add carbon or oxygen at an explicit target or the current atom."""
        if not isinstance(symbol, str) or symbol not in ELEMENT_NAMES:
            return False, UNSUPPORTED_ELEMENT_MESSAGE
        if type(bond_order) is not int or bond_order not in self._BONDS:
            return False, "Choose a single, double, or triple bond."
        if to_atom is not None and not self._valid_atom(to_atom):
            return False, "Choose an existing atom number, starting at 1."
        target = self._current_atom if to_atom is None else to_atom
        candidate = Chem.RWMol(self._mol)
        index = candidate.AddAtom(Chem.Atom(symbol))
        if target is not None:
            candidate.AddBond(target - 1, index, self._BONDS[bond_order])
        name = ELEMENT_NAMES[symbol]
        return self._commit(candidate, index + 1,
                            "Added {} as atom {}.".format(name, index + 1))

    def _bond_edit(self, a, b, order, replace):
        if not self._valid_atom(a) or not self._valid_atom(b):
            return False, "Choose two existing atom numbers."
        if a == b:
            return False, "An atom cannot bond to itself."
        if type(order) is not int or order not in self._BONDS:
            return False, "Choose a single, double, or triple bond."
        bond = self._mol.GetBondBetweenAtoms(a - 1, b - 1)
        if replace and bond is None:
            return False, "Those atoms do not have a bond to change."
        if not replace and bond is not None:
            return False, "Those atoms already have a bond."
        candidate = Chem.RWMol(self._mol)
        if replace:
            candidate.GetBondBetweenAtoms(a - 1, b - 1).SetBondType(self._BONDS[order])
        else:
            candidate.AddBond(a - 1, b - 1, self._BONDS[order])
        # Changing a bond inside an aromatic ring (e.g. benzene) is a no-op:
        # RDKit re-perceives aromaticity and restores the original bonds. Reject
        # it with a clear message instead of claiming a change that did not
        # happen, which a non-visual user could not otherwise detect.
        if replace:
            before = Chem.MolToSmiles(self._mol)
            committed, message = self._commit(candidate, self._current_atom,
                                              "Changed the bond.")
            if committed and Chem.MolToSmiles(self._mol) == before:
                self._mol, self._current_atom = self._history.pop()
                return False, ("That bond is part of an aromatic ring and cannot "
                               "be changed on its own. The molecule has not changed.")
            return committed, message
        return self._commit(candidate, self._current_atom, "Connected the atoms.")

    def connect(self, a, b, bond_order=1):
        """Connect two existing atoms without moving the cursor."""
        return self._bond_edit(a, b, bond_order, False)

    def set_bond_order(self, a, b, order):
        return self._bond_edit(a, b, order, True)

    def delete_atom(self, n):
        """Renumber survivors; use the preceding atom if the cursor is deleted."""
        if not self._valid_atom(n):
            return False, "Choose an existing atom number, starting at 1."
        candidate = Chem.RWMol(self._mol)
        candidate.RemoveAtom(n - 1)
        current = self._current_atom
        if candidate.GetNumAtoms() == 0:
            current = None
        elif current == n:
            current = max(1, n - 1)
        elif current > n:
            current -= 1
        return self._commit(candidate, current, "Deleted atom {}.".format(n))

    def reset(self):
        return self._commit(Chem.RWMol(), None, "Started over with an empty molecule.")

    def load_molecule(self, smiles):
        """Replace the molecule from a SMILES string, as one undoable action.

        Used by the named-molecule library. The structure still goes through the
        same valence and sanitize checks as every other edit, and must contain
        only carbon and oxygen (hydrogens implicit); anything else is rejected so
        the C/O/H scope cannot be bypassed through the library.
        """
        if not isinstance(smiles, str) or not smiles:
            return False, "That molecule could not be loaded."
        parsed = Chem.MolFromSmiles(smiles)
        if parsed is None:
            return False, "That molecule could not be loaded."
        for atom in parsed.GetAtoms():
            if atom.GetSymbol() not in ELEMENT_NAMES:
                return False, UNSUPPORTED_ELEMENT_MESSAGE
        # Store explicit single/double bonds so the valence check in _commit does
        # not read aromatic bonds as 1.5 and wrongly flag fused rings (e.g.
        # naphthalene). _commit re-sanitizes and re-kekulizes the result.
        try:
            Chem.Kekulize(parsed, clearAromaticFlags=True)
        except Exception:
            return False, "That molecule could not be loaded."
        candidate = Chem.RWMol(parsed)
        # Cursor follows the last atom, matching how building leaves the cursor.
        last = candidate.GetNumAtoms()
        return self._commit(candidate, last if last else None,
                            "Loaded the molecule.")

    def _compound(self, actions, message):
        """Run ordinary edits on an isolated builder, then commit just once."""
        draft = Builder()
        draft._mol = Chem.RWMol(self._mol)
        draft._current_atom = self._current_atom
        for method, args in actions:
            ok, feedback = getattr(draft, method)(*args)
            if not ok:
                return False, feedback
        self._remember()
        self._mol, self._current_atom = draft._mol, draft._current_atom
        return True, message

    def add_chain(self, count, bond_order=1, to_atom=None):
        if type(count) is not int or not 1 <= count <= 30:
            return False, "Choose a chain length from one through thirty."
        actions = [("add_atom", ("C", bond_order, to_atom))]
        actions += [("add_atom", ("C", bond_order))] * (count - 1)
        return self._compound(actions, "Added a chain of {} carbons.".format(count))

    def add_group(self, name, to_atom=None):
        # Targets for branches refer to the first newly added atom.
        first = self._mol.GetNumAtoms() + 1
        groups = {
            "methyl": [("C", 1, to_atom)],
            "ethyl": [("C", 1, to_atom), ("C", 1)],
            "hydroxyl": [("O", 1, to_atom)],
            "methoxy": [("O", 1, to_atom), ("C", 1)],
            "aldehyde": [("C", 1, to_atom), ("O", 2)],
            "carboxylic_acid": [("C", 1, to_atom), ("O", 2), ("O", 1, first)],
        }
        if not isinstance(name, str) or name not in groups:
            return False, "Choose methyl, ethyl, hydroxyl, methoxy, aldehyde, or carboxylic acid."
        return self._compound([("add_atom", args) for args in groups[name]],
                              "Added {}.".format(name.replace("_", " ")))

    def add_ring(self, kind, to_atom=None):
        sizes = {"cyclopropane": 3, "cyclobutane": 4, "cyclopentane": 5,
                 "cyclohexane": 6, "benzene": 6}
        if not isinstance(kind, str) or kind not in sizes:
            return False, "Choose cyclopropane, cyclobutane, cyclopentane, cyclohexane, or benzene."
        first = self._mol.GetNumAtoms() + 1
        actions = [("add_atom", ("C", 1, to_atom))]
        for i in range(1, sizes[kind]):
            order = 2 if kind == "benzene" and i % 2 else 1
            actions.append(("add_atom", ("C", order)))
        actions.append(("connect", (first, first + sizes[kind] - 1, 1)))
        return self._compound(actions, "Added a {} ring.".format(kind))

    def go_to(self, n: int) -> Tuple[bool, str]:
        """Move the cursor to an existing 1-based atom number."""
        if type(n) is not int or not 1 <= n <= self._mol.GetNumAtoms():
            return False, "Choose an existing atom number, starting at 1."
        self._remember()
        self._current_atom = n
        return True, "Current atom is now {}.".format(n)

    def undo(self) -> Tuple[bool, str]:
        """Restore the state before the last successful action."""
        if not self._history:
            return False, "There is nothing to undo."
        self._mol, self._current_atom = self._history.pop()
        return True, "Undid the last action."

    @property
    def current_atom(self) -> Optional[int]:
        """Return the 1-based current atom number, or None when empty."""
        return self._current_atom

    def molecule_copy(self) -> Chem.Mol:
        """Return an independent RDKit molecule with added atom order intact."""
        return Chem.Mol(self._mol)

    def smiles(self) -> str:
        """Return canonical SMILES, or an empty string for an empty molecule."""
        return Chem.MolToSmiles(self._mol)

    def describe_atoms(self) -> List[Dict[str, Any]]:
        """Return atoms in added order; bonds contain neighbor numbers and orders.

        Each entry has number, symbol, implicit_hydrogens, and bonds keys.
        Each bond has atom (the neighbor's number) and order keys.
        """
        descriptions: List[Dict[str, Any]] = []
        for atom in self._mol.GetAtoms():
            bonds = [
                {
                    "atom": bond.GetOtherAtomIdx(atom.GetIdx()) + 1,
                    "order": int(bond.GetBondTypeAsDouble()),
                }
                for bond in atom.GetBonds()
            ]
            descriptions.append({
                "number": atom.GetIdx() + 1,
                "symbol": atom.GetSymbol(),
                "implicit_hydrogens": atom.GetNumImplicitHs(),
                "bonds": sorted(bonds, key=lambda bond: bond["atom"]),
            })
        return descriptions
