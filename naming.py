"""Look up a molecule's name from PubChem using its SMILES.

This is the one place the program reaches the internet. It is strictly a
read-only name lookup against PubChem's public REST API (PUG-REST); it never
sends anything but the structure and never makes chemistry decisions. Every
failure mode -- offline, timeout, unknown structure, bad response -- returns a
plain-language message instead of raising, so naming can never crash or hang the
app. RDKit still owns the chemistry; this only asks "what is this called?".
"""

import json
from typing import Optional, Tuple
from urllib import error, parse, request

# PubChem is the only network call in the program. Keep the timeout short so a
# slow or missing connection fails fast instead of hanging the session.
TIMEOUT_SECONDS = 10
_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{}/property/IUPACName,Title/JSON"

def _request_json(url: str) -> Optional[dict]:
    """Fetch and parse JSON, or return None on any network or decode error."""
    try:
        with request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, ValueError, OSError):
        # Offline, timeout, HTTP error, or unparseable body: treat as no result.
        return None

def lookup_name(smiles: str) -> Tuple[Optional[str], Optional[str], str]:
    """Return (common_name, iupac_name, message) for a SMILES via PubChem.

    common_name and iupac_name are None when unavailable. message is always a
    plain-language, speakable string describing the outcome (found names, not
    found, or a network problem), so the caller can simply speak it.
    """
    if not isinstance(smiles, str) or not smiles:
        return None, None, "There is no molecule to name."

    # SMILES contains characters like # ( ) / = that must be URL-encoded.
    url = _BASE.format(parse.quote(smiles, safe=""))
    data = _request_json(url)
    if data is None:
        return None, None, ("I couldn't reach the naming service. "
                            "Check your internet connection and try again.")

    try:
        props = data["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, TypeError):
        return None, None, "I couldn't find a name for this molecule."

    # CID 0 (or missing) means PubChem did not recognize the structure.
    if not props.get("CID"):
        return None, None, "I couldn't find a name for this molecule."

    common = props.get("Title")
    iupac = props.get("IUPACName")
    if not common and not iupac:
        return None, None, "I couldn't find a name for this molecule."

    return common, iupac, _describe(common, iupac)

def _describe(common: Optional[str], iupac: Optional[str]) -> str:
    """Build a spoken sentence from whichever names PubChem returned."""
    if common and iupac:
        # Avoid saying the same word twice when the names match (e.g. ethanol).
        if common.lower() == iupac.lower():
            return "This molecule is {}.".format(common)
        return "This molecule is {}. Its systematic name is {}.".format(common, iupac)
    if common:
        return "This molecule is {}.".format(common)
    return "Its systematic name is {}.".format(iupac)
