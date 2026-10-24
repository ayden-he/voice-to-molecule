# Role 2 — Voice (speech to text, and spoken output)

Paste this whole file into a new Kiro chat and say: "This is my role on the voice-to-molecule project. Read it and help me build it. Start by having me clone the repo and run the tests." Also read COLLABORATOR_HANDOFF.md and API.md in the repo.

## You own
Turning the user's speech into text (new: transcribe.py or browser-side voice) and the spoken output (speech.py, already cross-platform). You do NOT touch chemistry — your output is just a text string that goes to the backend's POST /command.

## The project in one line
A speech-to-structure tool for blind/low-vision organic chemistry students. You are the "ears and mouth." The clean boundary: speech in -> text -> /command, and backend message -> speech out. Chemistry stays in the backend.

## YOUR BIG DECISION (you get to choose)
Where does speech recognition run? Pick one, write it in API.md and DECISIONS.md, and tell the team:
- (A) In the browser — Web Speech API (JavaScript). No install, works in Chrome, lowest friction, great for a web demo. You work closely with the frontend person. Output text is POSTed to /command. Recommended if the demo is in Chrome.
- (B) Server-side — Whisper (Python). faster-whisper (base.en, CPU, int8) + sounddevice, push-to-talk, 16 kHz mono. Record audio, send to POST /transcribe returning {"text": ...} (empty string for silence — never invent words), then send that text to /command. More control, heavier, keeps you independent. Needs mic permission.
Either way the rest of the system is identical, because the boundary is "text."

## Hard rules
- Never invent words: silence or too-short audio returns empty text.
- Recognition can mishear; the backend parser already tolerates common mishears (adam for atom, to/too for two). If you find frequent chemistry-word errors, note them so Person 1 can widen the parser — do not correct chemistry yourself.
- Python 3.9.6-compatible if you write Python. Log decisions in DECISIONS.md.

## Status when you start
Spoken OUTPUT already works (speech.py): interruptible, rate control, --quiet, graceful text-only fallback, cross-platform. Speech INPUT is not built yet; that is your main task.

## Your tasks (in order)
1. Clone, set up, run tests (expect ~444 passed).
2. Decide A or B. Write it in API.md + DECISIONS.md.
3. Build it in isolation first against a FAKE /command (you just need to produce the right text strings like "add carbon", "add oxygen double bond to atom two"). You do not need the real backend to start.
4. Add the command vocabulary as a Whisper initial_prompt (B) or grammar hints (A) so recognition favors the real commands.
5. Build a tiny mic_test.py (or in-page mic test) so a user can confirm their microphone before building a molecule.
6. Graceful fallbacks: missing mic / denied permission / model download failure fall back to typed input with a clear message. Stop spoken output before recording so the app does not hear itself.
7. Tests: mock the recognizer/mic so tests need no real microphone or model download.

## How to verify (the important one)
Eyes-closed test: screen off or eyes shut, speak a target molecule into existence (propanoic acid or ethyl acetate) using only what you hear. Note every confusing or misheard moment and fix wording / vocabulary. This is strong evidence for the award's human-judgment criterion.

## Workflow
Pull main first; branch (voice/transcribe); Kiro writes COMPLETE files and runs tests in its sandbox before you apply; run tests locally; PR; no direct commits to main.
