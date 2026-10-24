"""Recognize explicit molecule commands without changing any molecule state."""

import re
from typing import Any, Dict, Optional


_FILLERS = {"please", "um", "uh", "okay"}
_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30,
    "to": 2, "too": 2, "for": 4, "fore": 4, "won": 1, "ate": 8,
}
for _word, _value in list(_NUMBERS.items()):
    if 1 <= _value <= 9 and _word not in {"to", "too", "for", "fore", "won", "ate"}:
        _NUMBERS["twenty " + _word] = 20 + _value

_GROUPS = {"methyl", "ethyl", "hydroxyl", "methoxy", "aldehyde", "carboxylic acid"}
_RINGS = {"cyclopropane", "cyclobutane", "cyclopentane", "cyclohexane", "benzene"}
# Recognize actual element names for clear rejection; unknown nouns stay unknown.
_OTHER_ELEMENTS = set("""hydrogen helium lithium beryllium boron nitrogen fluorine
neon sodium magnesium aluminium aluminum silicon phosphorus sulfur sulphur chlorine
argon potassium calcium scandium titanium vanadium chromium manganese iron cobalt
nickel copper zinc gallium germanium arsenic selenium bromine krypton rubidium
strontium yttrium zirconium niobium molybdenum technetium ruthenium rhodium palladium
silver cadmium indium tin antimony tellurium iodine xenon caesium cesium barium
lanthanum cerium praseodymium neodymium promethium samarium europium gadolinium
terbium dysprosium holmium erbium thulium ytterbium lutetium hafnium tantalum tungsten
rhenium osmium iridium platinum gold mercury thallium lead bismuth polonium astatine
radon francium radium actinium thorium protactinium uranium neptunium plutonium
americium curium berkelium californium einsteinium fermium mendelevium nobelium
lawrencium rutherfordium dubnium seaborgium bohrium hassium meitnerium darmstadtium
roentgenium copernicium nihonium flerovium moscovium livermorium tennessine oganesson
h he li be b n f ne na mg al si p s cl ar k ca sc ti v cr mn fe co ni cu zn ga ge as
se br kr rb sr y zr nb mo tc ru rh pd ag cd in sn sb te i xe cs ba la ce pr nd pm sm
eu gd tb dy ho er tm yb lu hf ta w re os ir pt au hg tl pb bi po at rn fr ra ac th pa
u np pu am cm bk cf es fm md no lr rf db sg bh hs mt ds rg cn nh fl mc lv ts og""".split())
_ATOM = r"(?:atom|atoms|adam)"
_NUMBER = r"([a-z]+(?: [a-z]+)?|[0-9]+)"
_ORDER = r"(single|double|doubled|triple|tripled)"
_ORDERS = {None: 1, "single": 1, "double": 2, "doubled": 2,
           "triple": 3, "tripled": 3}


def _number(text):
    if text in _NUMBERS:
        return _NUMBERS[text]
    if text.isascii() and text.isdigit() and len(text) <= 2:
        value = int(text)
        if 1 <= value <= 30:
            return value
    return None


_SIMPLE_COMMANDS = {
    "undo": "undo", "read it back": "read_back", "summary": "summary",
    "read back": "read_back", "describe": "read_back",
    "show": "show", "faster": "faster", "slower": "slower",
    "save": "save", "help": "help", "quit": "quit",
    "start over": "reset", "where am i": "where_am_i",
    "what can i add": "what_can_i_add", "close the ring": "close_ring",
}


def parse(text: str) -> Optional[Dict[str, Any]]:
    """Return an action dictionary, or None for an unrecognized sentence.

    go_to uses the key atom_number. Only complete commands are accepted;
    unknown words are never discarded as guesses.
    """
    if not isinstance(text, str):
        return None

    # Do not turn negative, signed, or decimal numbers into valid atom numbers
    # when removing punctuation. Hyphens in double-bond remain supported.
    if re.search(r"[+\-−]\s*[0-9]|[0-9][.,][0-9]", text):
        return None
    normalized = re.sub(r"[^\w\s]", " ", text.lower())
    words = [word for word in normalized.split() if word not in _FILLERS]
    normalized = " ".join(words)

    if normalized in _SIMPLE_COMMANDS:
        return {"action": _SIMPLE_COMMANDS[normalized]}

    # Strip only an explicit trailing target, then match the entire addition.
    target = None
    target_match = re.fullmatch(r"(add .+) to " + _ATOM + " " + _NUMBER, normalized)
    base = normalized
    if target_match:
        base, number_text = target_match.groups()
        target = _number(number_text)
        if target is None:
            return None

    addition = re.fullmatch(r"add ([a-z]+)(?: " + _ORDER + r"(?: bond)?)?", base)
    if addition:
        element, bond = addition.groups()
        order = _ORDERS[bond]
        if element in _OTHER_ELEMENTS:
            return {"action": "unsupported_element"}
        if element in ("carbon", "oxygen"):
            if element == "oxygen" and order == 3:
                return None
            result = {"action": "add_atom", "symbol": "C" if element == "carbon" else "O",
                      "bond_order": order}
            if target is not None:
                result["to_atom"] = target
            return result

    if base.startswith("add ") and base[4:] in _GROUPS:
        result = {"action": "add_group", "name": base[4:].replace(" ", "_")}
        if target is not None:
            result["to_atom"] = target
        return result

    ring = re.fullmatch(r"add ([a-z]+)(?: ring)?", base)
    if ring and ring.group(1) in _RINGS:
        result = {"action": "add_ring", "kind": ring.group(1)}
        if target is not None:
            result["to_atom"] = target
        return result
    chain = re.fullmatch(r"add " + _NUMBER + r" carbons", base)
    if chain:
        count = _number(chain.group(1))
        if count is None:
            return None
        result = {"action": "add_chain", "count": count}
        if target is not None:
            result["to_atom"] = target
        return result
    if target is not None:
        return None

    for prefix, action in (("go to", "go_to"), ("delete", "delete_atom")):
        match = re.fullmatch(prefix + " " + _ATOM + " " + _NUMBER, normalized)
        if match:
            number = _number(match.group(1))
            return {"action": action, "atom_number": number} if number is not None else None

    connection = re.fullmatch(r"bond " + _ATOM + " " + _NUMBER + r" to " + _ATOM + " " + _NUMBER,
                              normalized)
    if connection:
        a, b = (_number(word) for word in connection.groups())
        if a is not None and b is not None:
            return {"action": "connect", "a": a, "b": b, "bond_order": 1}
    change = re.fullmatch(r"change (?:the )?bond between (?:" + _ATOM + " )?" + _NUMBER
                          + r" and (?:" + _ATOM + " )?" + _NUMBER + r" to " + _ORDER + r"(?: bond)?",
                          normalized)
    if change:
        first, second, order = change.groups()
        a, b = _number(first), _number(second)
        if a is not None and b is not None:
            return {"action": "set_bond_order", "a": a, "b": b, "order": _ORDERS[order]}
    return None
