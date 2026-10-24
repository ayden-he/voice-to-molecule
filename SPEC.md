# Voice-to-Molecule Builder

Environment: Python 3.9.6, macOS, VS Code, virtual environment, pytest.
Use Python 3.9.6-compatible syntax: no `X | Y` type unions and no `match`
statements.

Hard rules:
- ALL chemistry uses RDKit. Gemini interprets natural language into the existing
  command vocabulary; deterministic pattern matching validates those commands
  before Builder executes them. The model never edits molecular state directly.
  This replaces the original no-AI-parsing rule by explicit user decision.
- Goal: let the user build complex organic molecules using only C, O, and H.
- Elements: the user places carbon and oxygen. Hydrogens are implicit and
  filled in automatically. Max valence: C 4, O 2. Any other element is
  rejected with a clear message ("Only carbon and oxygen can be added.
  Hydrogens are added automatically.").
- Bonds: single, double, triple.
- Rings: close a ring by bonding any two existing atoms; ring templates
  (cyclopropane through cyclohexane, benzene). Fused and multiple rings must
  work (e.g., naphthalene, glucose).
- Group shortcuts: methyl, ethyl, hydroxyl, methoxy, aldehyde, carboxylic
  acid.
- Commands may name a target atom ("to atom N") so the cursor doesn't have
  to move. Chains ("add five carbons"), delete atom N, change bond, start
  over, where am I, what can I add, help.
- Numbers: digits or words up to 30.
- Every action is undoable; every failure leaves the molecule unchanged.
- A live preview of the structure is always visible and updates after every
  change.
- Out of scope: other elements, stereochemistry, charges, radicals,
  mechanisms/arrows, name-to-structure.

State and validation rules:
- A "current atom" cursor exists. New atoms bond to it by default, then become
  current. An explicit target does not require a separate cursor move.
- Atoms are numbered 1-based in the order added. Readback always uses these.
- Bond orders and ring closures must respect the C 4 / O 2 valence limits.
- Failed commands return clear, plain-language messages. Nothing should crash.
- Every state-changing action, including cursor moves, chains, templates,
  shortcuts, deletion, bond changes, and start over, is undoable. Compound
  commands succeed as a whole or leave molecule, cursor, and history unchanged.
- The live preview includes an empty-state view and updates after undo and
  start over as well as other edits. A manually opened image is not sufficient.

Commands:
- Add carbon or oxygen with a single, double, or triple bond, subject to
  valence limits; optionally name a target with "to atom N".
- Add chains, for example "add five carbons", optionally "to atom N".
- Close a ring between two existing atoms; add ring templates and functional
  group shortcuts, optionally naming an attachment target.
- "delete atom N"; "change bond" between named atoms; "start over".
- "go to atom N"; "where am I"; "what can I add"; "help".
- Existing commands remain available: undo; read it back; summary; save; show;
  faster; slower; quit.

Numbers: accept digits or number words from one through thirty (1–30) wherever
commands take numbers, including atom references and chain lengths. Reject
invalid or out-of-range numbers with clear feedback. Chemistry and existing-atom
validation still apply. Read-only commands do not change molecule state.

Modules: builder.py, parser.py, readback.py, speech.py, export.py, main.py,
tests/.

Working rules for you:
- Work one stage at a time. After each stage: run the tests, summarize what
  you did in 3-5 lines, list any decisions you made, then STOP and wait.
- Append each decision to DECISIONS.md (what, why, alternatives).
- Keep code simple and commented. I'm a beginner and need to understand it.
