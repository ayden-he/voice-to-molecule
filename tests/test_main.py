"""Scripted commands use the same handler as the interactive loop."""

import pytest
from rdkit import Chem

import main as text_app
from builder import Builder


@pytest.fixture(autouse=True)
def silent_speech(monkeypatch, tmp_path):
    monkeypatch.setattr(text_app.export, "CURRENT_IMAGE", tmp_path / "outputs" / "current.png")
    from unittest.mock import Mock
    monkeypatch.setattr(text_app.speech, "speak", Mock())
    monkeypatch.setattr(text_app.speech, "stop_speaking", Mock())
    monkeypatch.setattr(text_app.speech, "RATE", 180)


def test_script_builds_acetone_and_rejects_extra_bond(capsys):
    builder = Builder()
    commands = [
        "add carbon", "add carbon", "add oxygen double bond",
        "go to atom 2", "add carbon",
    ]
    for command in commands:
        assert text_app.handle_line(command, builder) is True
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("CC(C)=O")
    assert capsys.readouterr().out.count("SMILES:") == len(commands)

    assert text_app.handle_line("go to atom 2", builder) is True
    before = builder.smiles()
    capsys.readouterr()
    assert text_app.handle_line("add carbon", builder) is True
    assert builder.smiles() == before
    output = capsys.readouterr().out
    assert "maximum valence" in output
    assert "SMILES:" not in output


def test_undo_and_empty_display(capsys):
    builder = Builder()
    text_app.handle_line("add carbon", builder)
    text_app.handle_line("undo", builder)
    assert builder.smiles() == ""
    assert "SMILES: empty" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["save"])
def test_placeholders(command, capsys):
    builder = Builder()
    assert text_app.handle_line(command, builder) is True
    assert capsys.readouterr().out == "Not built yet.\n"
    assert builder.smiles() == ""


def test_help_unknown_and_quit(capsys):
    builder = Builder()
    assert text_app.handle_line("help", builder) is True
    output = capsys.readouterr().out
    # Help teaches how to do each kind of thing with one example each. It no
    # longer advertises the unimplemented "save" placeholder or a redundant
    # "help" entry.
    for command in ("add carbon", "add oxygen", "go to atom", "undo",
                    "read it back", "summary", "quit"):
        assert command in output
    assert "SMILES: empty" in output
    assert text_app.handle_line("nonsense", builder) is True
    output = capsys.readouterr().out
    assert "I didn't understand that." in output
    assert "add carbon" in output and "go to atom 3" in output
    assert text_app.handle_line("quit", builder) is False
    assert builder.smiles() == ""


@pytest.mark.parametrize("ending", ["quit", EOFError(), KeyboardInterrupt()])
def test_loop_recovers_and_exits(ending, monkeypatch, capsys):
    script = iter([RuntimeError("unexpected input error"), "add carbon", ending])

    def scripted_input(prompt):
        item = next(script)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr("builtins.input", scripted_input)
    text_app.main([])
    output = capsys.readouterr().out
    assert "Type help for commands." in output
    assert "Something went wrong" in output
    assert "SMILES: C" in output


def test_loop_recovers_from_handler_error(monkeypatch, capsys):
    original_parse = text_app.parse
    script = iter(["broken", "add oxygen", "quit"])

    def failing_parse(text):
        if text == "broken":
            raise RuntimeError("unexpected parser error")
        return original_parse(text)

    monkeypatch.setattr("builtins.input", lambda prompt: next(script))
    monkeypatch.setattr(text_app, "parse", failing_parse)
    text_app.main([])
    output = capsys.readouterr().out
    assert "Something went wrong" in output
    assert "SMILES: O" in output


@pytest.mark.parametrize("command", ["read it back", "read back", "describe", "summary"])
def test_spoken_commands(command, capsys):
    builder = Builder()
    assert text_app.handle_line(command, builder) is True
    assert capsys.readouterr().out == "The molecule is empty.\n"
    builder.add_atom("C")
    expected = text_app.summary(builder) if command == "summary" else text_app.detail(builder)
    assert text_app.handle_line(command, builder) is True
    assert capsys.readouterr().out == expected + "\n"
    assert builder.current_atom == 1
    builder.undo()
    assert builder.current_atom is None


def test_feedback_is_spoken_without_smiles(capsys):
    builder = Builder()
    for command in ["add carbon", "go to atom 1", "undo", "read back", "summary",
                    "help", "save", "nonsense", "go to atom 99"]:
        text_app.speech.speak.reset_mock()
        text_app.handle_line(command, builder)
        output = capsys.readouterr().out
        spoken = text_app.speech.speak.call_args.args[0]
        assert spoken in output
        assert "SMILES:" not in spoken
    text_app.handle_line("quit", builder)
    text_app.speech.stop_speaking.assert_called()


def test_faster_and_slower(capsys):
    builder = Builder()
    for command, expected in [("faster", 220), ("slower", 180)]:
        assert text_app.handle_line(command, builder)
        message = "Speech rate is now {} words per minute.".format(expected)
        assert capsys.readouterr().out == message + "\n"
        text_app.speech.speak.assert_called_with(message)
        assert text_app.speech.RATE == expected


def test_quiet_flag(monkeypatch):
    from unittest.mock import Mock
    quiet = Mock()
    monkeypatch.setattr(text_app.speech, "set_quiet", quiet)
    monkeypatch.setattr("builtins.input", lambda prompt: "quit")
    text_app.main(["--quiet"])
    quiet.assert_called_once_with(True)
    text_app.speech.stop_speaking.assert_called()


def test_image_refresh_and_empty_cleanup(capsys):
    builder = Builder()
    path = text_app.export.CURRENT_IMAGE
    text_app.handle_line("add carbon", builder)
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    first = path.read_bytes()
    text_app.handle_line("add oxygen", builder)
    assert path.read_bytes() != first
    second = path.read_bytes()
    text_app.handle_line("go to atom 1", builder)
    assert path.read_bytes() != second
    text_app.handle_line("undo", builder)
    assert path.read_bytes() == second
    text_app.handle_line("undo", builder)
    assert path.read_bytes() == first
    text_app.handle_line("undo", builder)
    assert not path.exists()


def test_show_command(monkeypatch, capsys):
    from unittest.mock import Mock
    opener = Mock()
    monkeypatch.setattr(text_app.export.subprocess, "run", opener)
    builder = Builder()
    text_app.handle_line("show", builder)
    opener.assert_not_called()
    text_app.handle_line("add carbon", builder)
    text_app.handle_line("show", builder)
    opener.assert_called_once()
    assert "Opened the current molecule image." in capsys.readouterr().out


def test_failed_or_readonly_commands_do_not_refresh(monkeypatch):
    from unittest.mock import Mock
    save = Mock(return_value=(True, "Saved"))
    monkeypatch.setattr(text_app.export, "save_image", save)
    builder = Builder()
    for command in ["go to atom 9", "undo", "summary", "read back", "help", "faster"]:
        text_app.handle_line(command, builder)
    save.assert_not_called()


@pytest.mark.parametrize("commands, expected", [
    (["add five carbons"], "CCCCC"),
    (["add carbon", "add carbon", "add oxygen double bond to atom two"], "CC=O"),
    (["add five carbons", "add methyl to atom three"], "CCC(C)CC"),
    (["add carbon", "add methyl"], "CC"),
    (["add carbon", "add hydroxyl"], "CO"),
    (["add carbon", "add methoxy"], "COC"),
    (["add carbon", "add aldehyde"], "CC=O"),
    (["add carbon", "add carboxylic acid"], "CC(=O)O"),
    (["add benzene ring"], "c1ccccc1"),
    (["add cyclohexane"], "C1CCCCC1"),
    (["add six carbons", "bond atom six to atom one"], "C1CCCCC1"),
    (["add six carbons", "close the ring"], "C1CCCCC1"),
    (["add three carbons", "change the bond between two and three to double"], "CC=C"),
    (["add five carbons", "delete atom five"], "CCCC"),
    (["add benzene ring", "start over"], ""),
])
def test_extended_command_scripts(commands, expected, capsys):
    builder = Builder()
    for command in commands:
        assert text_app.handle_line(command, builder)
        output = capsys.readouterr().out
        assert "SMILES:" in output
        assert text_app.speech.speak.call_args.args[0] in output
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)
    assert text_app.export.CURRENT_IMAGE.exists() == bool(expected)


@pytest.mark.parametrize("command", ["add nitrogen", "add chlorine", "add N", "add hydrogen",
    "add sulfur to atom two", "ADD BROMINE DOUBLE-BOND!", "add sodium"])
def test_other_element_feedback_is_spoken_and_preserves_state(command, capsys):
    builder = Builder()
    builder.add_atom("C")
    before = builder.smiles(), builder.describe_atoms(), builder.current_atom
    assert text_app.handle_line(command, builder)
    message = "Only carbon and oxygen can be added. Hydrogens are added automatically."
    assert capsys.readouterr().out == message + "\n"
    text_app.speech.speak.assert_called_with(message)
    assert (builder.smiles(), builder.describe_atoms(), builder.current_atom) == before
    builder.undo()
    assert builder.smiles() == ""


def test_navigation_options_and_grouped_help_are_read_only(capsys, monkeypatch):
    from unittest.mock import Mock
    save = Mock()
    monkeypatch.setattr(text_app.export, "save_image", save)
    builder = Builder()
    text_app.handle_line("where am I", builder)
    assert "no current atom" in capsys.readouterr().out
    builder.add_atom("O")
    text_app.handle_line("where am I", builder)
    assert capsys.readouterr().out == "You are at atom 1, oxygen.\n"
    text_app.handle_line("what can I add", builder)
    output = capsys.readouterr().out
    for name in ("carbon", "oxygen", "methyl", "ethyl", "hydroxyl", "methoxy",
                 "aldehyde", "carboxylic acid", "cyclopropane", "cyclobutane",
                 "cyclopentane", "cyclohexane", "benzene"):
        assert name in output
    text_app.speech.speak.assert_called_with(text_app.OPTIONS_TEXT)
    text_app.handle_line("help", builder)
    output = capsys.readouterr().out
    # Help covers each kind of action with a worked example, and points to
    # "what can I add" for the full group/ring lists.
    for phrase in ("add carbon", "add oxygen double bond", "add methyl",
                   "add benzene ring", "what can I add", "undo", "read it back"):
        assert phrase in output
    save.assert_not_called()
    builder.undo()
    assert builder.current_atom is None


@pytest.mark.parametrize("command", ["add six carbons", "add methoxy", "add benzene ring",
    "bond atom three to atom one", "close the ring",
    "change the bond between two and three to double", "delete atom two", "start over"])
def test_new_commands_refresh_and_undo(command, capsys, monkeypatch):
    from unittest.mock import Mock
    save = Mock(return_value=(True, "Saved"))
    monkeypatch.setattr(text_app.export, "save_image", save)
    builder = Builder()
    builder.add_chain(3)
    before = builder.smiles(), builder.describe_atoms(), builder.current_atom
    text_app.handle_line(command, builder)
    assert "SMILES:" in capsys.readouterr().out
    if command != "start over":
        save.assert_called_once()
    text_app.handle_line("undo", builder)
    assert (builder.smiles(), builder.describe_atoms(), builder.current_atom) == before


@pytest.mark.parametrize("command", ["close the ring", "delete atom five",
    "change the bond between two and three to double", "bond atom six to atom one"])
def test_new_commands_fail_cleanly_when_empty(command, capsys):
    builder = Builder()
    text_app.handle_line(command, builder)
    output = capsys.readouterr().out
    assert output.strip() and "SMILES:" not in output
    text_app.speech.speak.assert_called_once()
    assert builder.smiles() == "" and builder.current_atom is None
    assert not builder.undo()[0]


@pytest.mark.parametrize("command", ["add banana", "add nitrogen maybe", "add methyl double bond",
    "bond six one", "delete five", "change bond to double", "start over now",
    "add carbon and oxygen", "add thirty one carbons", "where am I now"])
def test_unclear_inputs_report_unknown_and_preserve_state(command, capsys):
    builder = Builder()
    builder.add_atom("C")
    text_app.handle_line(command, builder)
    output = capsys.readouterr().out
    assert "I didn't understand that." in output
    assert "SMILES:" not in output
    assert builder.smiles() == "C" and builder.current_atom == 1
    builder.undo()
    assert builder.smiles() == ""


@pytest.mark.parametrize("command, expected", [
    ("add two carbons to atom one", "CCCC"),
    ("add benzene ring to atom one", "CCc1ccccc1"),
])
def test_targeted_chain_and_ring_are_atomic(command, expected, capsys):
    builder = Builder()
    builder.add_chain(2)
    before = builder.smiles(), builder.describe_atoms(), builder.current_atom
    text_app.handle_line(command, builder)
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)
    text_app.handle_line("undo", builder)
    assert (builder.smiles(), builder.describe_atoms(), builder.current_atom) == before
    text_app.handle_line(command.replace("atom one", "atom thirty"), builder)
    assert (builder.smiles(), builder.describe_atoms(), builder.current_atom) == before
    builder.undo()
    assert builder.smiles() == ""

@pytest.mark.parametrize("command, expected", [
    ("build aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
    ("load acetic acid", "CC(=O)O"),
    ("make glucose", "OCC1OC(O)C(O)C(O)C1O"),
])
def test_named_molecule_commands_build_structure(command, expected, capsys):
    builder = Builder()
    assert text_app.handle_line(command, builder) is True
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles(expected)
    assert "SMILES:" in capsys.readouterr().out

def test_unknown_named_molecule_is_reported_and_leaves_state(capsys):
    builder = Builder()
    builder.add_atom("C")
    assert text_app.handle_line("build unobtainium", builder) is True
    output = capsys.readouterr().out
    assert "don't have that molecule" in output
    assert "SMILES:" not in output          # failure prints no SMILES line
    assert builder.smiles() == "C"           # unchanged

def test_named_molecule_is_undoable(capsys):
    builder = Builder()
    text_app.handle_line("build benzene", builder)
    assert Chem.CanonSmiles(builder.smiles()) == Chem.CanonSmiles("c1ccccc1")
    builder.undo()
    assert builder.smiles() == ""

def test_skip_stops_speech_without_speaking(capsys):
    builder = Builder()
    text_app.speech.stop_speaking.reset_mock()
    text_app.speech.speak.reset_mock()
    assert text_app.handle_line("skip", builder) is True
    text_app.speech.stop_speaking.assert_called_once()
    text_app.speech.speak.assert_not_called()
    assert capsys.readouterr().out == "Stopped.\n"
    assert "SMILES:" not in capsys.readouterr().out

def test_skip_leaves_molecule_unchanged(capsys):
    builder = Builder()
    builder.add_atom("C")
    text_app.handle_line("skip", builder)
    assert builder.smiles() == "C"
    assert builder.current_atom == 1

def test_name_command_speaks_pubchem_result(capsys, monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(text_app.naming, "lookup_name",
                        Mock(return_value=("Aspirin", "2-acetyloxybenzoic acid",
                                           "This molecule is Aspirin. Its systematic name is 2-acetyloxybenzoic acid.")))
    builder = Builder()
    builder.add_atom("C")
    assert text_app.handle_line("name", builder) is True
    out = capsys.readouterr().out
    assert "Aspirin" in out and "2-acetyloxybenzoic acid" in out
    text_app.naming.lookup_name.assert_called_once()

def test_name_command_handles_network_failure(capsys, monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(text_app.naming, "lookup_name",
                        Mock(return_value=(None, None,
                                           "I couldn't reach the naming service. "
                                           "Check your internet connection and try again.")))
    builder = Builder()
    builder.add_atom("C")
    assert text_app.handle_line("name", builder) is True
    assert "couldn't reach the naming service" in capsys.readouterr().out

def test_name_command_empty_molecule_skips_lookup(capsys, monkeypatch):
    from unittest.mock import Mock
    lookup = Mock()
    monkeypatch.setattr(text_app.naming, "lookup_name", lookup)
    builder = Builder()
    assert text_app.handle_line("name", builder) is True
    assert "empty" in capsys.readouterr().out
    lookup.assert_not_called()
