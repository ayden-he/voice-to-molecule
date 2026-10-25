"""Text interface for building a molecule one command at a time."""

import argparse
from typing import List, Optional

import export
import library
import naming
import speech
from builder import Builder, ELEMENT_NAMES
from parser import parse
from readback import detail, summary


OPTIONS_TEXT = """Elements: carbon, oxygen, and the halogens fluorine, chlorine,
bromine, and iodine. Hydrogens are added automatically.
Groups: methyl, ethyl, hydroxyl, methoxy, aldehyde, carboxylic acid, acetoxy.
Rings: cyclopropane, cyclobutane, cyclopentane, cyclohexane, benzene."""

HELP_TEXT = """You build molecules from carbon, oxygen, and the halogens
(fluorine, chlorine, bromine, iodine). Hydrogens are added for you, and each new
atom attaches to your current atom.
To add an atom, say "add carbon", "add oxygen", or "add chlorine".
To add a double or triple bond, say it in the command, like "add oxygen double bond".
To attach to a specific atom, end with its number, like "add carbon to atom two".
To add several atoms at once, say "add five carbons".
To add a group, name it, like "add methyl". Say "what can I add" for the full list of groups.
To add a ring, name it, like "add benzene ring". Say "what can I add" for the full list of rings.
To build a known molecule, say "build" and its name, like "build aspirin".
To connect two atoms into a ring, say "bond atom six to atom one".
To change a bond, say "change the bond between two and three to double".
To move to another atom, say "go to atom two".
To remove an atom, say "delete atom five".
To undo your last step, say "undo". To clear everything, say "start over".
To hear your molecule, say "read it back" for the full details, or "summary" for the totals.
To check where you are, say "where am I".
To change the voice, say "faster" or "slower". To stop the voice, say "skip".
To finish, say "quit"."""

from builder import UNSUPPORTED_ELEMENT_MESSAGE as ELEMENT_MESSAGE


def _report(text: str) -> None:
    """Print and speak feedback, keeping SMILES on its separate print path."""
    print(text)
    speech.speak(text)


def handle_line(text: str, builder: Builder) -> bool:
    """Handle one line using the shared builder; return False only to quit."""
    command = parse(text)
    if command is None:
        _report("I didn't understand that.\n"
                "Try: add carbon; add oxygen double bond; go to atom 3.")
        return True

    action = command["action"]
    if action == "quit":
        speech.stop_speaking()
        return False
    if action == "skip":
        # Stop the current readback. Print only (do not speak) so this command
        # produces silence rather than more speech to interrupt.
        speech.stop_speaking()
        print("Stopped.")
        return True
    if action in ("faster", "slower"):
        rate = speech.set_rate(speech.RATE + (40 if action == "faster" else -40))
        _report("Speech rate is now {} words per minute.".format(rate))
        return True
    if action in ("read_back", "summary"):
        _report(detail(builder) if action == "read_back" else summary(builder))
        return True
    if action == "name":
        if builder.current_atom is None:
            _report("The molecule is empty.")
        else:
            _report("Looking up the name...")
            _, _, message = naming.lookup_name(builder.smiles())
            _report(message)
        return True
    if action == "unsupported_element":
        _report(ELEMENT_MESSAGE)
        return True
    if action == "where_am_i":
        if builder.current_atom is None:
            _report("The molecule is empty. There is no current atom.")
        else:
            atom = builder.describe_atoms()[builder.current_atom - 1]
            name = ELEMENT_NAMES[atom["symbol"]]
            _report("You are at atom {}, {}.".format(builder.current_atom, name))
        return True
    if action == "what_can_i_add":
        _report(OPTIONS_TEXT)
        return True
    if action == "show":
        success, message = export.show_image(builder, export.CURRENT_IMAGE)
        _report(message)
        return True
    if action == "save":
        _report("Not built yet.")
        return True

    if action == "help":
        _report(HELP_TEXT)
        success = True
    else:
        if action == "load_named":
            smiles = library.lookup(command["name"])
            if smiles is None:
                success, message = False, (
                    "I don't have that molecule in the library. You can build it "
                    "step by step, or try: aspirin, glucose, acetic acid.")
            else:
                success, message = builder.load_molecule(smiles)
        elif action == "add_atom":
            success, message = builder.add_atom(command["symbol"], command["bond_order"], command.get("to_atom"))
        elif action == "add_chain":
            success, message = builder.add_chain(command["count"], to_atom=command.get("to_atom"))
        elif action == "add_group":
            success, message = builder.add_group(command["name"], command.get("to_atom"))
        elif action == "add_ring":
            success, message = builder.add_ring(command["kind"], to_atom=command.get("to_atom"))
        elif action == "connect":
            success, message = builder.connect(command["a"], command["b"], command["bond_order"])
        elif action == "close_ring":
            success, message = builder.connect(builder.current_atom, 1)
        elif action == "set_bond_order":
            success, message = builder.set_bond_order(command["a"], command["b"], command["order"])
        elif action == "delete_atom":
            success, message = builder.delete_atom(command["atom_number"])
        elif action == "reset":
            success, message = builder.reset()
        elif action == "go_to":
            success, message = builder.go_to(command["atom_number"])
        elif action == "undo":
            success, message = builder.undo()
        else:
            # Keep an unexpected parser result inside the loop's error boundary.
            raise ValueError("Unknown command action")
        if success:
            if builder.current_atom is None:
                # Undo to empty must not leave a drawing of the previous state.
                try:
                    export.CURRENT_IMAGE.unlink(missing_ok=True)
                except OSError:
                    message += " Could not remove the previous molecule image."
            else:
                saved, image_message = export.save_image(builder, export.CURRENT_IMAGE)
                if not saved:
                    message += " " + image_message
        _report(message)

    if success:
        print("SMILES: " + (builder.smiles() or "empty"))
    return True


def main(argv: Optional[List[str]] = None) -> None:
    """Run the interactive text loop with one molecule for the session."""
    arguments = argparse.ArgumentParser(description="Build carbon/oxygen molecules.")
    arguments.add_argument("--quiet", action="store_true", help="Disable spoken output")
    options = arguments.parse_args(argv)
    speech.set_quiet(options.quiet)
    _report("Welcome to the molecule builder. Type help for commands.")
    builder = Builder()
    while True:
        try:
            if not handle_line(input("> "), builder):
                break
        except (EOFError, KeyboardInterrupt):
            speech.stop_speaking()
            print("\nGoodbye.")
            break
        except Exception:
            # A failed command should not end the user's session.
            _report("Something went wrong while handling that command. Please try again.")


if __name__ == "__main__":
    main()
