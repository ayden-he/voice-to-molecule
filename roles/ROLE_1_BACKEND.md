# Role 1 — Backend / Features

Paste this whole file into a new Kiro chat and say: "This is my role on the voice-to-molecule project. Read it and help me build it. Start by having me clone the repo and run the tests." Also read COLLABORATOR_HANDOFF.md and API.md in the repo.

## You own
builder.py, parser.py, readback.py, export.py, the test suite, and a NEW api.py that exposes the molecule engine over HTTP for the website.

## The project in one line
A speech-to-structure tool for blind/low-vision organic chemistry students. Voice/browser turns speech into text; your code (plain regex + RDKit) builds and validates the molecule and returns the result. You are the "brain." The AI never decides chemistry — RDKit is the authority.

## Hard rules (do not break)
- Elements: carbon and oxygen only; hydrogens implicit (RDKit fills them). No nitrogen/sulfur/halogens, no amine/amide/nitrile. Max valence C 4, O 2.
- Python 3.9.6-compatible syntax (no X | Y unions, no match).
- Every state-changing action is undoable; failures leave the molecule unchanged; compound actions commit all-or-nothing.
- Log non-trivial decisions in DECISIONS.md (what / why / alternatives).

## Status when you start
The chemistry engine and parser are DONE and tested (444 tests passing with RDKit). All 16 complex target molecules build correctly (aspirin, glucose, menthol, etc.). Your main new work is the API layer, plus any remaining SPEC features.

## IMPORTANT: you do NOT build on main.py
main.py is the terminal interface — one frontend onto the engine. The website needs a NEW api.py (an HTTP server) that wraps the SAME engine (builder/parser/readback/export). The command-dispatch logic currently lives inside main.py's handle_line(). Extract that shared dispatch so both main.py and api.py call one code path and cannot drift apart. Keep main.py working as a local test tool and fallback demo.

## Your tasks (in order)
1. Clone, set up, verify: git clone the repo, make a venv, pip install -r requirements.txt, then python3 -m pytest -v (expect 444 passed).
2. Agree the API contract with the team (see API.md). Do not skip this.
3. Build api.py — a small Flask (or FastAPI) app implementing API.md: hold ONE shared Builder; POST /command runs parse(text) then dispatches to the Builder (reuse the shared dispatch) and returns the JSON shape in API.md; GET /state returns current molecule with no change; GET /image?fmt=svg (and png) draws via export.py (add an SVG drawer with RDKit MolDraw2DSVG, keeping numbered atoms + current-atom highlight). Never 500 on ordinary bad input; return ok:false with a message.
4. Add Flask (or FastAPI) to requirements.txt and tests for the API (test client; assert JSON shapes and that rejections leave state unchanged).
5. Keep main.py working.

## How you unblock the others
Frontend (Person 3) and voice (Person 2) build against your API's JSON shapes. Give them a runnable server early. Keep the shapes in API.md accurate.

## How to verify
python3 -m pytest -v green. Start the server, then curl -X POST /command with {"text":"add carbon"} returns expected JSON; then "add oxygen double bond to atom one", "read it back", and "add nitrogen" (confirm graceful rejection).

## Workflow
Pull main first; branch (backend/api); have Kiro write COMPLETE files and run tests in its sandbox before you apply; run tests locally; push; open a PR; do not commit to main.
