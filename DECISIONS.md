# Decisions

## Stage 1: Project setup

- **What:** Use a project-local `.venv` and `python -m pip` / `python -m pytest`.
  **Why:** Keep dependencies isolated and run tools with the selected Python.
  **Alternatives:** A global Python install or a Conda environment.
- **What:** List `rdkit` and `pytest` without version pins in `requirements.txt`.
  **Why:** Start with packages compatible with the installed Python, as requested.
  **Alternatives:** Pin exact versions for repeatable installs once dependencies stabilize.
- **What:** Keep the six application modules empty and place one ethanol smoke
  test in `tests/test_rdkit_install.py`.
  **Why:** Verify RDKit installation without starting later implementation stages.
  **Alternatives:** Implement builder behavior now or use only a manual import check.
- **What:** Document macOS setup in `README.md` and ignore virtual environment
  and Python test caches in `.gitignore`.
  **Why:** Make setup easy to repeat and keep generated files out of version control.
  **Alternatives:** Provide setup only in chat or track generated files.

## Stage 2: Molecule builder

- **What:** Store an RDKit `RWMol` and a 1-based current atom, with C/O and
  integer bond orders 1–3 validated before editing. The first atom has no bond,
  so a valid bond order is ignored for that initial addition.
  **Why:** Follow the command rules and give clear valence errors.
  **Alternatives:** Rely entirely on RDKit errors or reject non-single first additions.
- **What:** Sanitize additions on a copy, committing only after success; keep
  molecule/cursor snapshots for successful additions and all valid cursor moves.
  **Why:** Failures preserve the molecule, cursor, and undo history. Undo restores
  the previous state and consumes history; reads and failures do not add history.
  **Alternatives:** Reverse individual edits or make undo itself another saved action.
- **What:** Return canonical SMILES (empty string initially) and atom dictionaries
  with `number`, `symbol`, `implicit_hydrogens`, and `bonds`. Each bond dictionary
  has the neighbor's 1-based `atom` number and integer `order`, sorted by neighbor.
  **Why:** Give later readback code a predictable structure while preserving added
  atom numbering independently of canonical SMILES order.
  **Alternatives:** Return formatted prose, tuples, or RDKit objects directly.
- **What:** Use Python 3.9-compatible annotations and add no tests in this stage.
  **Why:** Respect the installed Python 3.9.6 and the Stage 2 instructions.
  **Alternatives:** Newer annotation syntax or adding builder tests now.

## Stage 3: Builder tests

- **What:** Add parameterized pytest cases for all seven requested molecules,
  using `go_to` for branches and `Chem.CanonSmiles` on actual and expected SMILES.
  **Why:** Verify chemical structure independently of atom serialization order.
  **Alternatives:** Compare literal SMILES strings or private RDKit objects.
- **What:** Check every rejected action returns `False` and a nonempty message,
  preserving both exact before/after SMILES and public atom descriptions.
  Cover carbon's fifth bond, saturated oxygen with two single bonds or one double
  bond, nonexistent atom numbers, empty undo, and unsupported elements.
  **Why:** Verify failures are atomic without depending on message wording.
  **Alternatives:** Assert only failure status or match complete error messages.
- **What:** Test the documented first-atom behavior for bond orders 1, 2, and 3,
  rather than require rejection of an initial bonded addition.
  **Why:** Stage 2 deliberately ignores initial bond order, and there is no
  separate operation that requires an existing atom.
  **Alternatives:** Change the builder API to reject initial multiple bonds.
- **What:** Verify undo restores additions and cursor moves through subsequent
  public operations, and verify added-order numbering and branch connectivity
  through `describe_atoms`.
  **Why:** Catch cursor and numbering regressions without inspecting private state.
  **Alternatives:** Assert private cursor/history fields directly.
- **What:** Leave `builder.py` unchanged; `.venv/bin/python -m pytest -q`
  passed all 32 tests on Python 3.9.6 (31 new builder cases and the existing smoke
  test).
  **Why:** No test or implementation failures were found.
  **Alternatives:** Make speculative builder changes without a failing case.

## Stage 4: Command parser

- **What:** Implement `parse(text)` with standard-library regex/string handling,
  returning dictionaries with `action`; additions include `symbol` and
  `bond_order`, and cursor moves include `atom_number`. Return `None` otherwise.
  **Why:** Keep parsing simple, independent of Builder, and compatible with
  Python 3.9.6. **Alternatives:** A command dataclass or calling Builder directly.
- **What:** Lowercase text, replace punctuation with spaces, remove only the
  filler words `please`, `um`, `uh`, and `okay`, and match whole commands.
  Accept the requested atom/bond mishearings and number words one through ten;
  positive digit numbers have no molecule-dependent upper bound.
  **Why:** Tolerate speech transcription without guessing or needing molecule
  state. **Alternatives:** Substring matching, broader synonyms, or restricting
  digit numbers to ten.
- **What:** Reject oxygen triple bonds, zero/signed/decimal atom numbers,
  combined commands, unsupported elements, and extra unknown words. Check signed
  and decimal forms before stripping punctuation.
  **Why:** Preserve clear command intent and avoid converting `-1` into `1`.
  **Alternatives:** Forward invalid syntax to Builder or discard unknown words.
- **What:** Add 121 parser test cases covering every action, requested speech
  variants, normalization, and unrecognized inputs; run the full suite with
  `.venv/bin/python -m pytest -q` on Python 3.9.6: **153 passed**.
  **Why:** Verify the parser while checking existing builder behavior still passes.
  **Alternatives:** Manual examples or running parser tests alone.

## Stage 5: Text command loop

- **What:** Add `handle_line(text, builder)` to parse and dispatch a single
  command; return `True` to continue and `False` for quit. `main()` owns one
  Builder for the entire session and is protected by the module entry guard.
  **Why:** Scripted tests exercise the same handling logic as typed input,
  and importing the module does not start a prompt.
  **Alternatives:** Put all dispatch inside the input loop or create a UI class.
- **What:** Print Builder messages and show `SMILES: ...` after successful
  additions, cursor moves, undo, and help; show `empty` for an empty molecule.
  Readback, summary, and save print only `Not built yet.`; quit exits directly.
  **Why:** Display the current state after completed commands while treating
  placeholders as unavailable operations rather than successful commands.
  **Alternatives:** Display SMILES after failures and placeholders as well.
- **What:** Print three concrete examples for unrecognized input. Catch unexpected
  exceptions around each input/handling iteration, print a plain message, and
  continue; EOF and Ctrl-C end the loop cleanly.
  **Why:** Keep ordinary bad input and unexpected command errors from ending
  the session, while permitting an intentional exit.
  **Alternatives:** Catch errors only in the parser or show tracebacks to users.
- **What:** Add ten test cases covering an acetone script, unchanged SMILES on
  valence failure, undo to empty, placeholders, help, unknown input, clean exits,
  and recovery after unexpected input/parser errors. Run
  `.venv/bin/python -m pytest -q` on Python 3.9.6: **163 passed in 0.90s**.
  **Why:** Verify the connected interface and existing suite without changing
  other application modules.
  **Alternatives:** Manual typing alone or tests that bypass command dispatch.

## Stage 6: Spoken readback

- **What:** Add a read-only `Builder.current_atom` property returning the 1-based
  cursor or `None` for an empty molecule.
  **Why:** Readback needs the current atom, which was not publicly exposed;
  this is the smallest accessor and does not expose mutable RDKit state.
  **Alternatives:** Access private state or add cursor metadata to every atom.
- **What:** Implement `summary(builder)` and `detail(builder)` using only
  `describe_atoms()` and the public cursor. Count implicit hydrogens supplied
  by RDKit, omit absent elements from composition, and report carbon before oxygen.
  Use singular/plural nouns, word-based bond names, and added-order atom numbers;
  join detail sentences into one text string suitable for speech.
  **Why:** Keep chemistry in Builder/RDKit and keep spoken output predictable
  without SMILES or chemical symbols.
  **Alternatives:** Recompute valence in readback, speak SMILES, or return a list.
- **What:** Dispatch readback and summary directly in the text loop, without
  appending SMILES; keep save as a placeholder. Accept `read back` and `describe`
  alongside `read it back`, and update help and parser tests.
  **Why:** Spoken commands should print only their requested descriptions.
  **Alternatives:** Append the ordinary successful-edit SMILES output.
- **What:** Add exact readback tests for empty, single carbon, ethanol, acetone,
  propene, propyne, and oxygen singular/plural cases; verify cursor moves/undo
  and all spoken command aliases through the text handler. Run the full suite
  with `.venv/bin/python -m pytest -q` on Python 3.9.6: **174 passed in 0.92s**.
  **Why:** Check wording, numbering, integration, and existing functionality.
  **Alternatives:** Manual speech checks or substring-only readback assertions.

## Stage 7: Interruptible text-to-speech

- **What:** Keep one module-level `Popen` process, start `say` asynchronously,
  and terminate/reap earlier speech before starting new speech. Use bounded
  0.2-second waits with a kill fallback; tolerate process-exit races.
  **Why:** Long readbacks must not block the next command or overlap new feedback.
  **Alternatives:** Blocking subprocess calls, queued speech, or unbounded waits.
- **What:** Expose `RATE` (default 180), `set_rate` clamped to 100–400, `QUIET`,
  and `set_quiet`; enabling quiet mode immediately stops existing speech.
  **Why:** Support rate controls and silent runs without extra libraries.
  **Alternatives:** Per-call options or allowing out-of-range rates.
- **What:** Replace non-word symbols with spaces while preserving natural
  punctuation, and pass cleaned text as one argument after `--` in a shell-free
  argument list. On launch OSError, warn once and retain text-only mode.
  **Why:** Avoid awkward symbol pronunciation, option interpretation, shell
  execution, and repeated failures when speech is unavailable.
  **Alternatives:** Shell interpolation, unfiltered text, or crashing on launch.
- **What:** Centralize printed/spoken feedback in `_report`, keep SMILES on a
  print-only path, add argparse `--quiet`, and recognize faster/slower commands
  that adjust the rate by 40 and speak the resulting rate. Stop speech on quit,
  EOF, and Ctrl-C. The quit path stops immediately without starting new speech.
  **Why:** Make feedback accessible and preserve prompt responsiveness on exit.
  **Alternatives:** Speaking every printed line, including SMILES, or leaving
  speech running after exit.
- **What:** Mock speech in command-loop tests and mock `Popen` in speech tests;
  check arguments, interruption order, quiet mode, clamping, cleaning, fallback,
  process cleanup, and command integration. Run
  `.venv/bin/python -m pytest -q` on Python 3.9.6: **194 passed in 0.85s**.
  **Why:** Verify behavior without producing audio during tests.
  **Alternatives:** Real audible subprocesses or manual-only verification.

## Stage 7b: Numbered skeletal image export

- **What:** Add `Builder.molecule_copy()` returning an independent RDKit Mol
  with added atom order intact. Draw that copy using RDKit's Cairo PNG drawer
  at 800 by 600 pixels, with 1-based atom notes and an amber current-atom highlight.
  **Why:** Match readback numbering, preserve standard skeletal rendering, and
  avoid modifying Builder or reordering atoms through canonical SMILES parsing.
  **Alternatives:** Reconstruct from descriptions or parse canonical SMILES,
  which would require extra bookkeeping to preserve added-order numbers.
- **What:** Return `(success, message)` from `save_image` and `show_image`.
  Create destination parents, require a .png suffix, and handle drawing/path
  failures gracefully. Empty molecules return a clear message before any writes.
  Generate PNG only; optional SVG is deferred.
  **Why:** Follow Builder's result convention and keep this stage small.
  **Alternatives:** Raise exceptions, require pre-created folders, or add SVG now.
- **What:** Refresh `outputs/current.png` after successful additions, cursor moves,
  and undo; remove the stale image when undo empties the molecule. Do not refresh
  for failed or read-only commands. Report export failures with command feedback.
  **Why:** Keep structure and cursor highlight synchronized without silently
  leaving an image of a previous molecule after undo to empty.
  **Alternatives:** Refresh only additions or keep a stale image after emptying.
- **What:** Add `show` to parser/help and refresh the current image before running
  macOS `open` with an absolute-path argument list and no shell. Handle missing
  open and nonzero exit status. Keep the existing save command placeholder.
  Ignore generated `outputs/` files.
  **Why:** Avoid displaying an old session's image and limit this stage to image
  export and viewing, without implementing the later full save workflow.
  **Alternatives:** Open whatever file already exists or implement full save now.
- **What:** Add real PNG signature/content tests, numbering/highlight checks,
  empty/invalid-path tests, mocked open success/failure tests, and command-loop
  refresh/cleanup checks. All speech and window opening remain mocked in tests.
  Run `.venv/bin/python -m pytest -q` on Python 3.9.6: **208 passed in 1.67s**.
  Visually inspect an acetone PNG: atom notes 1–4 are readable, skeletal bonds
  are clear, and current oxygen atom 4 is highlighted.
  **Why:** Verify actual rendering as well as integration without opening windows.
  **Alternatives:** Mock all drawing calls or rely only on manual checks.


## Scope revision: Complex C/O/H molecules (documentation only)

These requirements supersede conflicting scope and behavior choices in earlier
stage entries, which remain as a record of what was implemented at the time.
Implementation is deferred; this revision changes only SPEC.md and DECISIONS.md.

- **What:** Keep Python 3.9.6 as the runtime and require compatible syntax,
  including no `X | Y` type unions and no `match` statements.
  **Why:** Match the installed environment throughout future work.
  **Alternatives:** Upgrade Python or introduce syntax requiring Python 3.10.
- **What:** Limit molecules to C, O, and H. Users place only carbon and oxygen;
  RDKit fills hydrogens implicitly. Maximum bond-order sums are C 4 and O 2;
  single, double, and triple bonds remain supported subject to those limits.
  Reject other element additions with: "Only carbon and oxygen can be added.
  Hydrogens are added automatically." Keep deterministic command parsing.
  **Why:** Follow the corrected scope while supporting complex organic molecules.
  **Alternatives:** Expand the element set or require explicit hydrogen placement.
- **What:** Exclude other elements, stereochemistry, charges, radicals,
  mechanisms/arrows, and name-to-structure. The correction ended after "other
  elements," so retain the previously specified remaining exclusions.
  **Why:** Preserve established exclusions while applying the corrected elements.
  **Alternatives:** Treat the truncated bullet as removing the earlier exclusions.
- **What:** Allow ring closure between any two existing atoms, cyclopropane
  through cyclohexane and benzene templates, and fused and multiple rings
  (for example, naphthalene and glucose). Provide methyl, ethyl, hydroxyl,
  methoxy, aldehyde, and carboxylic acid shortcuts.
  **Why:** Support the requested C/O/H structures with convenient building blocks.
  **Alternatives:** Atom-by-atom construction only or isolated rings only.
- **What:** Support optional "to atom N" targets without a separate cursor move,
  chains such as "add five carbons", atom deletion, bond changes, start over,
  where am I, what can I add, and help, alongside existing commands. Accept
  digits and number words from 1 through 30 in numeric command arguments.
  **Why:** Reduce repetitive navigation and make spoken construction practical;
  this replaces the parser's earlier one-through-ten word limit and unbounded
  digit inputs.
  **Alternatives:** Require cursor movement before every edit or retain the
  earlier numeric grammar.
- **What:** Make every state-changing action undoable, including compound chain,
  ring, and shortcut edits, deletion, bond changes, cursor moves, and start over.
  Validate each complete command before committing; any failure leaves the
  molecule, cursor, and undo history unchanged. Read-only commands add no history.
  **Why:** Preserve predictable recovery as editing operations become broader.
  **Alternatives:** Partially commit compound commands or make reset irreversible.
- **What:** Require an always-visible live structure preview, refreshed after
  every state change and showing an empty state when appropriate.
  **Why:** The exported PNG and manually invoked show command from Stage 7b do
  not by themselves satisfy continuous visual feedback.
  **Alternatives:** Keep manual image opening or show only textual SMILES.

## Step 2: Extended C/O molecule builder

- **What:** Extend only Builder and its tests in this stage. Atom placement is
  restricted to C/O with the specified hydrogen explanation for any other input;
  retain Python 3.9.6-compatible syntax and the first-atom bond-order behavior.
  **Why:** Implement the requested construction API without advancing parser or
  live-preview work. **Alternatives:** Update command parsing and UI in this stage.
- **What:** Validate edits on molecule copies. Run chain, group, and ring actions
  on an isolated Builder using ordinary add_atom/connect operations; commit one
  parent snapshot only after all steps succeed. Failures preserve cursor and
  undo history as well as molecule state. Reset, even when empty, is undoable.
  **Why:** Compound actions must be atomic and take one undo to reverse.
  **Alternatives:** Expose intermediate mutations or require multiple undos.
- **What:** Store sanitized, kekulized molecules with explicit single/double
  bonds and cleared aromatic flags; RDKit canonical comparison recognizes the
  equivalent aromatic structures. Bond edits and readback use integer orders.
  **Why:** Avoid truncating aromatic bond order 1.5 to 1 and permit deletion or
  bond changes in aromatic rings without leftover aromatic flags.
  **Alternatives:** Store aromatic bonds and special-case each editing operation.
- **What:** Explicit add targets override the cursor; the new atom becomes
  current. Connect and bond changes retain the cursor. Deletion renumbers surviving
  atoms, preserves the cursor's identity when possible, and chooses the preceding
  surviving atom (or atom one) when deleting the cursor; empty means no cursor.
  **Why:** Keep numbering contiguous and cursor behavior predictable.
  **Alternatives:** Stable sparse atom IDs or always moving to the last atom.
- **What:** A ring template attaches its first carbon by one single bond to the
  current atom, if present, and leaves its final carbon current. Benzene has
  alternating double bonds. Fused rings use explicit connect operations. Group
  attachment uses the first atom of each group; group cursors finish on the final
  atom. Chain bond_order applies to the attachment and all new chain bonds;
  chain lengths are one through thirty.
  **Why:** Use one consistent atom-addition rule and avoid ambiguous template
  fusion or implicit cursor movements. **Alternatives:** Fuse templates onto an
  existing bond, select the attachment atom afterward, or vary chain bond orders.
- **What:** Add canonical structure comparisons for all sixteen requested
  molecules, template and shortcut recipes, element rejection, invalid edits,
  valence overflow, compound rollback, cursor renumbering, and undo of every new
  action type. Full suite: `.venv/bin/python -m pytest -q`, Python 3.9.6,
  **292 passed in 1.11s** (84 new cases).
  **Why:** Verify chemical connectivity and transaction behavior while retaining
  all existing integration coverage. **Alternatives:** Manual construction only
  or literal SMILES comparisons that depend on serialization order.

## Step 3: Extended command parser and text dispatch

- **What:** Keep full-command regex matching, case/punctuation normalization,
  the existing filler words and speech variants (adam/atoms, doubled/tripled,
  won/to/too/for/fore/ate). Extend numeric arguments to digits or number words
  one through thirty, including hyphenated twenty-one through twenty-nine.
  Explicit single bonds are now accepted alongside double and triple bonds.
  Signed, decimal, zero, and out-of-range arguments remain unrecognized.
  **Why:** Follow the expanded grammar without guessing unclear intent; this
  supersedes the old unrestricted digit range. **Alternatives:** Fuzzy matching,
  removing unknown words, or keeping the previous one-through-ten word limit.
- **What:** Return explicit action dictionaries for chains, groups, templates,
  connections, bond changes, deletion, reset, cursor queries, and available
  building blocks. Resolve close the ring in main.py as connect(current_atom, 1).
  Preserve all three readback aliases. Unsupported oxygen triple-bond syntax
  continues to return None, as before.
  **Why:** Keep parsing independent of molecule state and let Builder validate
  actual atom existence, bonds, and valence. **Alternatives:** Consult Builder
  during parsing or infer missing bond endpoints.
- **What:** Recognize known unsupported element names and symbols as a dedicated
  unsupported_element action. Main prints and speaks exactly: "Only carbon and
  oxygen can be added. Hydrogens are added automatically." Unknown nouns and
  incomplete, combined, or otherwise unclear commands still return None.
  **Why:** Give useful feedback for explicit element requests without guessing
  that every unknown addition is an element. **Alternatives:** Silently reject
  elements or classify all unknown nouns as element requests.
- **What:** Dispatch new edits to Builder, retaining shared speech/print feedback
  and image refresh after successful changes (including reset cleanup). Group
  help by purpose; what can I add lists supported elements, groups, and rings;
  where am I reports the cursor number and element or explains the empty state.
  Informational commands and failures do not add undo history or refresh images.
  **Why:** Keep command feedback consistent and preserve state on read-only paths.
  **Alternatives:** Duplicate editing logic in main or add history for queries.
- **What:** Add optional to_atom arguments to Builder.add_chain and add_ring,
  forwarding the target only to the first atom in their existing transaction.
  Parse and dispatch targeted chains and templates as well as atoms and groups.
  This extends the cursor-only chain/template signatures recorded in Step 2.
  **Why:** SPEC.md includes explicit targets for these build commands, and a
  separate go_to would break single-action undo and failure atomicity.
  **Alternatives:** Reject these targets or move the real cursor before building.
- **What:** Expand parser and main tests for requested phrases, all number values
  through thirty, speech variants, every template, supported additions, element
  feedback, more than ten unclear inputs, image refresh, read-only commands,
  empty-state failures, and undo/rollback of new command paths. Full suite:
  `.venv/bin/python -m pytest -q` on Python 3.9.6: **436 passed in 1.75s**
  (144 additional cases). Save remains the existing placeholder; this stage
  retains image export rather than implementing the separate live-preview UI.
  **Why:** Verify parser, dispatch, and existing behavior together while keeping
  this stage focused. **Alternatives:** Manual testing only or expanding UI work.

## Bond-edit no-op feedback (Option 1)

- **Decision:** Choose Option 1: report RDKit's truthful no-op rather than force
  cyclohexadiene. RDKit remains the chemistry authority. The guard applies only
  to the replace path and compares canonical SMILES before and after a successful
  commit. An unchanged result restores the molecule and cursor from the just-added
  history entry and reports rejection; the connect path retains its behavior.
- **Test:** Replace the old `C1CC=CC=C1` expectation with the requested no-op
  rejection and state/history checks, preserving the atom-deletion checks. The
  correction was requested because the old expected value was chemically wrong
  for the intended RDKit no-op behavior. Local validation does not establish that
  premise: this checkout clears aromatic flags during commit, and RDKit 2025.09.2
  changes benzene to `C1=CCCC=C1` for this edit, so the supplied guard does not fire.
- **Validation:** System `python3 -m pytest -q` cannot run because pytest is not
  installed in that interpreter. With the project's Python 3.9.6 virtual
  environment on PATH, the same command reports **435 passed, 1 failed**. The
  updated aromatic-edit test fails at `assert ok is False`; 436 passing tests
  cannot be confirmed with the exact requested implementation.

## Cross-platform speech and image opening

- **Decision:** Speech and image opening now select platform commands through a
  pinnable module-level `PLATFORM` value. macOS behavior and command arguments
  remain unchanged. Windows speech uses PowerShell System.Speech, with embedded
  single quotes doubled inside the spoken string; Windows image opening uses
  `os.startfile`. Linux uses `spd-say` for speech and `xdg-open` for images.
- **Behavior:** Commands receive data through argument lists or an escaped
  PowerShell string literal, without shell execution. Speech still starts with
  non-blocking `Popen`, supports interruption, and warns only once before falling
  back to text when an engine cannot be launched on any OS. Image-launch failures
  retain the saved image and return the existing graceful failure message.
- **Validation:** With the project's Python 3.9.6 virtual environment on PATH,
  `python3 -m pytest -q` reports **444 passed**. Tests pin platforms and mock all
  speech and viewer launches, including Windows quote escaping, Linux arguments,
  and missing-engine fallback on macOS, Windows, and Linux.

## HTTP API for the website

- Added `api.py` (Flask), exposing `POST /command`, `GET /state`, and `GET /image`.
  It reuses `parse()` and `Builder` with its own data-returning dispatch, leaving
  `main.py` and its tests unchanged. One shared molecule per server process keeps
  the hackathon session simple; CORS is enabled for local development. SVG is
  preferred for the web via RDKit `MolDraw2DSVG`, with PNG also available.
  Alternatives were extracting the terminal dispatch or duplicating chemistry;
  this keeps the requested independent HTTP layer while RDKit remains the
  chemistry authority. Added Flask to requirements. On Python 3.9.6,
  `python3 -m pytest -q` reports **456 passed**. The supplied PNG-signature test
  literal was written with escaped newlines to preserve valid Python syntax.

## Curated named-molecule library

- Added `library.py`, a static curated mapping of common names and synonyms to
  verified C/H/O SMILES. Lookup is punctuation/case-insensitive and never guesses
  unknown names; no AI or web lookup is involved. `Builder.load_molecule` loads
  SMILES as one undoable action through the existing sanitize/valence path and
  enforces C/O-only atoms with implicit hydrogens. Aromatic structures are
  kekulized before valence checks, including fused rings such as naphthalene.
- The parser recognizes `build/load/make <name>` before its signed-number guard
  so hyphenated names work. Both `main.py` and `api.py` resolve names through the
  library and call the Builder. Unknown names leave the molecule unchanged.
  Sugars and menthol are connectivity-only, with no stereochemistry, matching
  project scope. Alternatives were guessing names or generating structures;
  fixed lookup keeps behavior deterministic and RDKit the chemistry authority.
- Validation: `python3 -m pytest -q` with the Python 3.9.6 project environment
  reports **637 passed**, covering every entry, synonyms, invalid input,
  element restrictions, undo, parser commands, and terminal/API integration.

## Summary wording

- Removed the atom count from `summary()` because "N atoms in total" was
  ambiguous: it counted only user-placed carbon/oxygen, not implicit hydrogens.
  Summary now reports composition and hydrogen count only; `detail()` is
  unchanged. Updated only the six corresponding summary expectations.

## Skip spoken output

- Added `skip` (aliases `stop`, `shush`, `be quiet`, and `stop talking`) to
  silence a long readback using the existing `speech.stop_speaking()`. It prints
  "Stopped." without speaking, avoiding a new utterance after interruption.
  The API acknowledges the command because the browser owns playback there.
  Chemistry and molecule state are unchanged.

## How-to help text

- Rewrote help to a how-to-with-one-example style: each line shows how to do
  one kind of action. Full group/ring lists are deferred to "what can I add".
  Dropped the unimplemented "save" and redundant "help" entries from the help
  text. Command logic is unchanged; updated the two help-content tests.

## Skip feature consistency

- Confirmed the complete skip feature is present in the working tree: parser
  aliases (`skip`, `stop`, `shush`, `be quiet`, `stop talking`), the `api.py`
  acknowledgment, and parser/API skip tests are consistent with the existing
  terminal handler. These pieces were already present as uncommitted changes
  when the reported half-applied state was checked, so no duplicate code or
  tests were added. Left `main.py` and its skip tests untouched.
- Validation: `python3 -m pytest -q` on Python 3.9.6 reports **647 passed**.

## PubChem molecule names

- Added `name` and its aliases to look up the current molecule by URL-encoded
  SMILES through PubChem PUG-REST, reporting both the common Title and IUPAC name.
  This is the program's only network call; chemistry remains with RDKit. The
  request uses a 10-second timeout and returns plain messages for handled
  offline/timeout/not-found and malformed-response failures. Molecules without
  stereochemistry (such as glucose) may receive a generic name like "Hexose".
- Used the supplied implementation and tests. The socket timeout is not a strict
  total wall-clock deadline, and the supplied response checks do not cover every
  malformed field type, so an absolute never-crash/never-hang guarantee is not
  established. All network access in tests is mocked; the Python 3.9.6 suite
  reports **668 passed**.
