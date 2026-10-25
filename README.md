# Voice-to-Molecule Builder

See SPEC.md for the project scope and working rules.

## React frontend

With Node installed, run `npm ci` and `npm run build`. The Python voice server
then serves the built React frontend at its root URL, including `/api` routes
on the same port. The original voice page remains at `/voice-app.html`.
For frontend development, run `npm run dev` and open http://127.0.0.1:5173/;
Vite forwards `/api` to the voice server on port 8001.

The React page uses browser text-to-speech on Windows, macOS, and Linux for
startup instructions and backend feedback. Enable the mic, then say Start;
Pause, Stop, Undo, Skip, mute, replay, and typed fallback remain available.
Chrome may require an interaction before speaking. Python terminal speech
retains its Windows System.Speech implementation in `speech.py`.

## AI voice app

In PowerShell, set your own API key locally (do not commit it or paste it in chat):

```powershell
$geminiSecret = Read-Host "Enter Gemini API key" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $geminiSecret).Password
.venv\Scripts\python.exe voice_server.py
```

Open http://127.0.0.1:8001/ in Chrome. This is the real molecule app, separate
from the earlier fake-service demo on port 8000. The page attempts a spoken
welcome explaining how to begin. If Chrome blocks automatic speech, press a
key or activate **Hear startup instructions**. Replaying the guide turns off
the microphone. Written instructions remain available.

Use headphones, enable the
microphone, then say **Start** as a separate utterance. Say "add a carbon then
add oxygen". Each action updates the numbered drawing. Say **Undo** to reverse
the last action, **Pause** to suspend commands, **Start** to resume, and **Stop**
to turn the microphone off. Undo is ignored while paused. Stop does not cancel
work already submitted. Typed requests work without enabling the microphone.
Say **Skip** to interrupt feedback while staying in command mode.

The combined server supports both `/utterance` (AI interpretation) and
`/command` (canonical commands) with one molecule and undo history. Point the
frontend to this same server. The alternative `api.py` server on port 5000 uses
the same command engine code but, as a separate process, has its own session;
do not run both expecting a shared molecule. Main's named-molecule library,
name lookup, and halogen edits are supported through the shared engine.

Gemini translates finalized speech segments, which can contain several actions.
The app executes clear steps until the first ambiguity, discards everything
after it, and asks for clarification. Later instructions must be spoken again;
there is no backlog. It never commits changing interim transcripts, so
update timing depends on Chrome finalizing a speech segment and API latency.
The API key stays on the server. The default model is `gemini-3.5-flash-lite`;
optionally set `GEMINI_MODEL` to a compatible Gemini model you can access.
Create your key in https://aistudio.google.com/apikey. Your reported free quota
is 15 requests/minute, 250K tokens/minute, and 500 requests/day; limits are
project-specific and can change. A limit error discards the unexecuted request
without automatic retries or molecule changes. Repeat it after the limit clears.
Clarification may require extra calls.
Google's free-tier content may be used to improve its products.

Run backend checks with `python -m pytest tests/test_conversation.py` and
browser logic checks with `node web/session.test.mjs` (Node required).

## Browser voice demo

Run `python -m http.server 8000 --bind 127.0.0.1` from the repository (on
Windows use `.venv\Scripts\python.exe` if needed), then open
http://127.0.0.1:8000/web/voice-demo.html in Chrome. Choose **Test microphone
only** first, allow microphone permission, and say "add carbon". The test
shows the transcript without submitting it. **Speak one command** sends to an
explicit fake service; this demo does not build molecules. Typed input remains
available. Browser speech may require internet access and send audio to the
browser provider.

Frontend integration is documented in API.md. With Node installed, run the
microphone-free checks using `node web/voice.test.mjs`.

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
