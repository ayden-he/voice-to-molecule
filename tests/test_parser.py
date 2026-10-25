"""Explicit command recognition and conservative speech normalization."""

import pytest

from parser import parse


@pytest.mark.parametrize("phrase, action", [
    ("undo", "undo"), ("read it back", "read_back"),
    ("read back", "read_back"), ("describe", "read_back"),
    ("summary", "summary"), ("save", "save"), ("help", "help"),
    ("quit", "quit"), ("show", "show"), ("faster", "faster"), ("slower", "slower"),
])
def test_simple_commands(phrase, action):
    assert parse(phrase) == {"action": action}


@pytest.mark.parametrize("element, symbol", [("carbon", "C"), ("oxygen", "O")])
@pytest.mark.parametrize("suffix, order", [
    ("", 1), (" double bond", 2), (" double", 2),
    (" double-bond", 2), (" doubled", 2),
])
def test_add_atom(element, symbol, suffix, order):
    assert parse("add " + element + suffix) == {
        "action": "add_atom", "symbol": symbol, "bond_order": order,
    }


@pytest.mark.parametrize("suffix", ["triple bond", "triple", "triple-bond", "tripled"])
def test_carbon_triple_bond(suffix):
    assert parse("add carbon " + suffix) == {
        "action": "add_atom", "symbol": "C", "bond_order": 3,
    }


@pytest.mark.parametrize("word, number", [
    ("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5),
    ("six", 6), ("seven", 7), ("eight", 8), ("nine", 9), ("ten", 10),
    ("to", 2), ("too", 2), ("for", 4), ("fore", 4), ("won", 1),
    ("ate", 8), ("1", 1), ("3", 3), ("10", 10), ("30", 30),
])
@pytest.mark.parametrize("atom_word", ["atom", "atoms", "adam"])
def test_go_to_variants(word, number, atom_word):
    assert parse("go to " + atom_word + " " + word) == {
        "action": "go_to", "atom_number": number,
    }


@pytest.mark.parametrize("text, expected", [
    ("UM, please ADD CARBON DOUBLE-BOND! okay.",
     {"action": "add_atom", "symbol": "C", "bond_order": 2}),
    ("Uh... GO TO ADAM THREE, PLEASE!", {"action": "go_to", "atom_number": 3}),
    ("  READ\tIT\nBACK?!  ", {"action": "read_back"}),
    ("please undo okay", {"action": "undo"}),
    ("uh SUMMARY!", {"action": "summary"}),
    ("SAVE.", {"action": "save"}),
    ("okay, help please", {"action": "help"}),
    ("QUIT!", {"action": "quit"}),
])
def test_normalization(text, expected):
    assert parse(text) == expected


@pytest.mark.parametrize("text", [
    "", "  ", "um uh okay please", "hello", "add", "add unobtainium",
    "add C", "add oxygen triple bond", "add oxygen tripled", "add carbon four",
    "add carbon quadruple bond", "do not add carbon", "don't add carbon",
    "add carbon and oxygen", "add carbon double triple bond", "undo save",
    "save my molecule", "describe everything", "go to carbon 2", "go to atom",
    "go to atom thirty one", "go to atom zero", "go to atom 0", "go to atom -1",
    "go to atom +2", "go to atom 1.5", "go to atom 1,000", "go to atom 2 3",
    "go to atom three or four", "go too atom three", "add carbonyl",
    None, 3,
])
def test_unrecognized_inputs(text):
    assert parse(text) is None


@pytest.mark.parametrize("phrase, expected", [
    ("add oxygen double bond to atom two", {"action": "add_atom", "symbol": "O", "bond_order": 2, "to_atom": 2}),
    ("add five carbons", {"action": "add_chain", "count": 5}),
    ("add methyl", {"action": "add_group", "name": "methyl"}),
    ("add methyl to atom three", {"action": "add_group", "name": "methyl", "to_atom": 3}),
    ("add ethyl", {"action": "add_group", "name": "ethyl"}),
    ("add hydroxyl", {"action": "add_group", "name": "hydroxyl"}),
    ("add methoxy", {"action": "add_group", "name": "methoxy"}),
    ("add aldehyde", {"action": "add_group", "name": "aldehyde"}),
    ("add carboxylic acid", {"action": "add_group", "name": "carboxylic_acid"}),
    ("add acetoxy", {"action": "add_group", "name": "acetoxy"}),
    ("add benzene ring", {"action": "add_ring", "kind": "benzene"}),
    ("add cyclohexane", {"action": "add_ring", "kind": "cyclohexane"}),
    ("bond atom six to atom one", {"action": "connect", "a": 6, "b": 1, "bond_order": 1}),
    ("close the ring", {"action": "close_ring"}),
    ("change the bond between two and three to double", {"action": "set_bond_order", "a": 2, "b": 3, "order": 2}),
    ("delete atom five", {"action": "delete_atom", "atom_number": 5}),
    ("start over", {"action": "reset"}),
    ("where am I", {"action": "where_am_i"}),
    ("what can I add", {"action": "what_can_i_add"}),
    ("UM, please ADD OXYGEN DOUBLED TO ADAM TOO!", {"action": "add_atom", "symbol": "O", "bond_order": 2, "to_atom": 2}),
    ("add carboxylic-acid to atoms twenty-one", {"action": "add_group", "name": "carboxylic_acid", "to_atom": 21}),
    ("BOND ADAM ATE TO ATOMS WON!", {"action": "connect", "a": 8, "b": 1, "bond_order": 1}),
    ("change bond between atom for and adam too to tripled", {"action": "set_bond_order", "a": 4, "b": 2, "order": 3}),
    ("add carbon single bond", {"action": "add_atom", "symbol": "C", "bond_order": 1}),
])
def test_extended_commands(phrase, expected):
    assert parse(phrase) == expected


NUMBER_WORDS = ("one two three four five six seven eight nine ten eleven twelve thirteen "
                "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()
NUMBER_WORDS += ["twenty " + word for word in NUMBER_WORDS[:9]] + ["thirty"]


@pytest.mark.parametrize("number, word", list(enumerate(NUMBER_WORDS, 1)))
def test_numbers_through_thirty_across_commands(number, word):
    for text in (word, str(number)):
        assert parse("add " + text + " carbons") == {"action": "add_chain", "count": number}
        assert parse("delete atom " + text) == {"action": "delete_atom", "atom_number": number}
        assert parse("go to atom " + text) == {"action": "go_to", "atom_number": number}
        assert parse("add methyl to atom " + text)["to_atom"] == number
        assert parse("bond atom " + text + " to atom one")["a"] == number
        assert parse("change bond between one and " + text + " to single")["b"] == number


@pytest.mark.parametrize("name", ["nitrogen", "hydrogen", "sulfur", "phosphorus",
    "sodium", "gold", "uranium", "N", "H", "S", "P"])
def test_unsupported_element_action(name):
    for suffix in ("", " double bond", " to atom twenty two"):
        assert parse("add " + name + suffix) == {"action": "unsupported_element"}

@pytest.mark.parametrize("name, symbol", [
    ("fluorine", "F"), ("chlorine", "Cl"), ("bromine", "Br"), ("iodine", "I"),
])
def test_halogens_parse_as_add_atom(name, symbol):
    # Halogens are supported, single-bond only.
    assert parse("add " + name) == {"action": "add_atom", "symbol": symbol, "bond_order": 1}
    assert parse("add " + name + " single bond") == {"action": "add_atom", "symbol": symbol, "bond_order": 1}
    assert parse("add " + name + " to atom two") == {"action": "add_atom", "symbol": symbol, "bond_order": 1, "to_atom": 2}
    assert parse("add " + name + " double bond") is None
    assert parse("add " + name + " triple bond") is None


@pytest.mark.parametrize("kind", ["cyclopropane", "cyclobutane", "cyclopentane", "cyclohexane", "benzene"])
def test_all_ring_commands(kind):
    assert parse("add " + kind) == {"action": "add_ring", "kind": kind}
    assert parse("add " + kind + " ring") == {"action": "add_ring", "kind": kind}


@pytest.mark.parametrize("text", [
    "add thirty one carbons", "add 31 carbons", "go to atom 42", "delete atom zero",
    "delete atom -5", "add methyl to atom 2.5", "add oxygen to atom +2",
    "bond atom one to atom 0", "change bond between one and 31 to double",
    "add banana", "add chlorine maybe", "add nitrogen and carbon", "add carboxylic",
    "add methoxy double bond", "add benzene double ring", "close a thing",
    "bond six one", "delete five", "change bond to double", "start over now",
    "add methyl to atom two or three", "add five carbons then undo",
])
def test_extended_unrecognized_inputs(text):
    assert parse(text) is None


@pytest.mark.parametrize("phrase, expected", [
    ("add five carbons to atom two", {"action": "add_chain", "count": 5, "to_atom": 2}),
    ("add benzene ring to atom three", {"action": "add_ring", "kind": "benzene", "to_atom": 3}),
])
def test_chain_and_ring_targets(phrase, expected):
    assert parse(phrase) == expected

@pytest.mark.parametrize("phrase", ["skip", "stop", "stop talking", "be quiet",
                                     "shush", "SKIP!", "  please stop  "])
def test_skip_variants_parse_to_skip(phrase):
    assert parse(phrase) == {"action": "skip"}

@pytest.mark.parametrize("phrase", ["name", "name it", "what is this",
                                     "what am I building", "what did I make",
                                     "NAME!", "  what is this?  "])
def test_name_variants_parse_to_name(phrase):
    assert parse(phrase) == {"action": "name"}


@pytest.mark.parametrize('phrase', [
    "what's the name of this molecule?", "What’s the name of this molecule?",
    'what is the name of this molecule', 'what is this molecule called?',
    "what's this molecule called?", 'name this molecule',
    'identify this molecule', 'tell me the name of this molecule please',
])
def test_conversational_molecule_name_requests(phrase):
    assert parse(phrase) == {'action': 'name'}
