"""A small, hand-curated library of common C/H/O molecules by name.

This is a fixed lookup table, not an algorithm and not an AI: every entry is a
human-verified SMILES string containing only carbon, oxygen, and implicit
hydrogen. Names and common synonyms map to the same structure. Looking a name up
never guesses; an unknown name returns None so the caller can ask the user to
build it step by step. RDKit still parses and validates the SMILES downstream,
so chemistry stays the authority.

Sugars (glucose, fructose, ribose) and menthol are stored as connectivity only;
stereochemistry is deliberately not modeled, consistent with the project scope.
"""

import re
from typing import Dict, List, Optional

# name or synonym (lowercase) -> SMILES. Keep every structure C/H/O only.
_LIBRARY: Dict[str, str] = {
    # Alcohols & polyols
    "methanol": "CO", "methyl alcohol": "CO",
    "ethanol": "CCO", "ethyl alcohol": "CCO",
    "isopropanol": "CC(O)C", "propan-2-ol": "CC(O)C",
    "isopropyl alcohol": "CC(O)C", "rubbing alcohol": "CC(O)C",
    "ethylene glycol": "OCCO", "ethane-1,2-diol": "OCCO",
    "glycerol": "OCC(O)CO", "glycerin": "OCC(O)CO",
    "glycerine": "OCC(O)CO", "propane-1,2,3-triol": "OCC(O)CO",
    # Aldehydes & ketones
    "formaldehyde": "C=O", "methanal": "C=O",
    "acetaldehyde": "CC=O", "ethanal": "CC=O",
    "acetone": "CC(C)=O", "propan-2-one": "CC(C)=O", "propanone": "CC(C)=O",
    # Carboxylic acids
    "formic acid": "C(=O)O", "methanoic acid": "C(=O)O",
    "acetic acid": "CC(=O)O", "ethanoic acid": "CC(=O)O",
    "propionic acid": "CCC(=O)O", "propanoic acid": "CCC(=O)O",
    "butyric acid": "CCCC(=O)O", "butanoic acid": "CCCC(=O)O",
    "oxalic acid": "OC(=O)C(=O)O", "ethanedioic acid": "OC(=O)C(=O)O",
    "lactic acid": "CC(O)C(=O)O", "2-hydroxypropanoic acid": "CC(O)C(=O)O",
    "citric acid": "OC(=O)CC(O)(C(=O)O)CC(=O)O",
    "maleic acid": "OC(=O)C=CC(=O)O",
    "succinic acid": "OC(=O)CCC(=O)O", "butanedioic acid": "OC(=O)CCC(=O)O",
    # Ethers & esters
    "diethyl ether": "CCOCC", "ether": "CCOCC",
    "dimethyl ether": "COC", "methoxymethane": "COC",
    "tetrahydrofuran": "C1CCOC1", "thf": "C1CCOC1", "oxolane": "C1CCOC1",
    "ethyl acetate": "CC(=O)OCC",
    "methyl acetate": "COC(C)=O",
    # Aromatics
    "benzene": "c1ccccc1",
    "toluene": "Cc1ccccc1", "methylbenzene": "Cc1ccccc1",
    "phenol": "Oc1ccccc1",
    "benzoic acid": "OC(=O)c1ccccc1",
    "benzaldehyde": "O=Cc1ccccc1",
    "anisole": "COc1ccccc1", "methoxybenzene": "COc1ccccc1",
    "catechol": "Oc1ccccc1O", "benzene-1,2-diol": "Oc1ccccc1O",
    "resorcinol": "Oc1cccc(O)c1", "benzene-1,3-diol": "Oc1cccc(O)c1",
    "hydroquinone": "Oc1ccc(O)cc1", "benzene-1,4-diol": "Oc1ccc(O)cc1",
    "salicylic acid": "OC(=O)c1ccccc1O",
    "2-hydroxybenzoic acid": "OC(=O)c1ccccc1O",
    "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "acetylsalicylic acid": "CC(=O)Oc1ccccc1C(=O)O",
    "vanillin": "O=Cc1ccc(O)c(OC)c1",
    "naphthalene": "c1ccc2ccccc2c1",
    # Rings & sugars (connectivity only; no stereochemistry)
    "cyclohexane": "C1CCCCC1",
    "cyclohexanol": "OC1CCCCC1",
    "glucose": "OCC1OC(O)C(O)C(O)C1O",
    "fructose": "OCC1(O)OC(CO)C(O)C1O",
    "ribose": "OCC1OC(O)C(O)C1O",
    # Terpene alcohol (connectivity only; no stereochemistry)
    "menthol": "CC(C)C1CCC(C)CC1O",
}

# Precompute a punctuation-insensitive index so "propan-2-ol", "propan 2 ol",
# and "Propan-2-OL" all resolve to the same entry. Spoken/typed names rarely
# carry exact punctuation, so lookups ignore it.
def _key(name: str) -> str:
    if not isinstance(name, str):
        return ""
    collapsed = re.sub(r"[^\w\s]", " ", name.lower())
    return " ".join(collapsed.split())

_INDEX: Dict[str, str] = {_key(name): smiles for name, smiles in _LIBRARY.items()}

def normalize(name: str) -> str:
    """Lowercase, drop punctuation, and collapse whitespace for lookup."""
    return _key(name)

def lookup(name: str) -> Optional[str]:
    """Return the SMILES for a known name or synonym, else None (never guess)."""
    return _INDEX.get(_key(name))

def names() -> List[str]:
    """Return the canonical/display names (sorted), for help and suggestions."""
    return sorted(set(_LIBRARY.keys()))
