# Voice-to-Molecule Builder

See SPEC.md for the project scope and working rules.

## macOS setup

Open Terminal (or the VS Code terminal), then run:

```bash
cd "/Users/aydenhe/Documents/Demon TIme"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
```

Each time you open a new terminal, activate the existing environment and run tests:

```bash
cd "/Users/aydenhe/Documents/Demon TIme"
source .venv/bin/activate
python -m pytest
```

In VS Code, use **Python: Select Interpreter** in the Command Palette and
select `.venv/bin/python`.

To leave the virtual environment, run `deactivate`.

## Project files

- `builder.py`: molecule state and edits (empty for now).
- `parser.py`: pattern-matched commands (empty for now).
- `readback.py`: plain-language molecule descriptions (empty for now).
- `speech.py`: speech input and output (empty for now).
- `export.py`: saving molecules (empty for now).
- `main.py`: application entry point (empty for now).
- `tests/`: pytest tests, starting with an RDKit installation check.

Speech uses the built-in macOS `say` command at 180 words per minute. Type
`faster` or `slower` to change the rate by 40 (limited to 100–400). New feedback
interrupts earlier speech. SMILES is printed only.

For a silent session, run:

```sh
.venv/bin/python main.py --quiet
```

If speech is unavailable, the app warns once and continues with text output.

The numbered skeletal drawing automatically refreshes at `outputs/current.png`
after additions, cursor moves, and undo. The current atom is highlighted.
Type `show` to open the current drawing with macOS `open`. Undoing to an empty
molecule removes the previous drawing.
