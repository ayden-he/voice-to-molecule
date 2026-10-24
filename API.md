# API Contract (the shared seam between all three roles)

This is the agreement that lets the backend, voice, and frontend people work in
parallel without blocking each other. Agree on this first. Change it only by
team agreement, and update this file when you do.

The backend (Person 1) implements these endpoints. The frontend (Person 3) and
voice (Person 2) code against them — and can build against a mock that returns
canned versions of these shapes until the real backend is ready.

## Principle (do not break)
RDKit remains the chemistry authority. Chrome transcribes speech; Gemini maps
natural language to the existing command vocabulary. The deterministic parser
checks that vocabulary and Builder validates each edit. This AI interpretation
route replaces the original regex-only language interpretation by user request.

## Base
- Local dev server, e.g. http://127.0.0.1:5000
- Requests are JSON. Responses are JSON except `/utterance` (NDJSON) and images.
- One molecule-building session per server process is fine for the hackathon
  (a single shared Builder). Multi-user sessions are out of scope.

## Voice decision: browser Web Speech API

### Continuous AI app (current implementation)

Run `voice_server.py` on localhost port 8001 and open `/`. The API key exists
only in the server environment (`GEMINI_API_KEY`). `GEMINI_MODEL` optionally
overrides the default `gemini-3.5-flash-lite`. No Python SDK dependency is required.
The interpreter uses Gemini generateContent with JSON Schema output and sends
the key in the `x-goog-api-key` header, never the browser or URL. Non-STOP,
blocked, malformed, and invalid-command responses execute no steps. Quota
errors retain the request for clarification/retry without automatic API retries.

`POST /utterance` accepts `{ "text": "add a carbon then an oxygen" }`.
It returns `application/x-ndjson`: one complete state event per executed action
or clarification barrier, each with `ok`, `message`, `queued`, `version`, and
the ordinary molecule state fields. GET `/state` returns the latest snapshot;
GET `/image` returns numbered SVG. Requests are serialized client-side and
server-side. Each successful mutation has one Builder undo step. A browser
disconnect does not cancel an already accepted request.
The combined voice server also provides `/command`, sharing this exact engine
and undo stack. Direct edits hold pending voice plans for clarification because
their context changed. `command_engine.py` supplies the dispatcher to both this
server and Flask `api.py`. Separate server processes have separate sessions;
configure the frontend to use one selected server for all molecule requests.
The voice server serves SVG; Flask also supports PNG as described below.

Enable microphone starts paused. Start enables commands; Pause disables
commands including Undo while retaining recognition; Stop aborts recognition
and discards unfinished speech. A button is required to enable the mic again.
Control words are separate utterances and handled locally. Undo interrupts TTS
immediately and executes after earlier submitted requests finish. Already
submitted work runs even after Pause/Stop. Recognition uses finalized segments,
not revisable interim transcripts. Updates occur per action after a segment
is finalized and interpreted; this is not word-by-word speculative execution.
Skip (also "stop talking", "be quiet", "shush") stops feedback while command
mode remains active, without an AI request. Stop still turns off the microphone.
Skip is ignored while paused, consistently with other non-control commands.

Clear steps before the first ambiguity execute; the ambiguous step and all
following instructions are held. The question explicitly announces queued
instructions. A clarification resolves the first blocked request, then retained
instructions are reinterpreted against the updated state and run in order.
RDKit rejections also block dependent steps. Interpretation failures preserve
the original request without mutating the molecule. Network failures are not
automatically retried, to avoid duplicating an edit after a lost response.

Use headphones during continuous listening to avoid TTS entering the mic.
Microphone permissions, browser recognition restarts, acoustic feedback, and
real Gemini interpretation still require manual end-to-end validation.

### Isolated microphone demo (earlier implementation)

Role 2 uses browser `SpeechRecognition` / `webkitSpeechRecognition`, one
user-triggered utterance at a time. No Whisper dependencies or `/transcribe`
endpoint are needed. `web/voice.mjs` exposes `createVoice` and `postCommand`.
Only one nonempty final transcript is forwarded, unchanged; interim results,
silence, errors, and cancelled captures never submit commands. The microphone
test returns text with `{test: true}` and must never call `/command`.

Frontend integration: pass `onText(text, {test})`, `onStatus(message)`, and
`onBusy(boolean)` callbacks. Queue command transcripts until `onBusy(false)`
before sending and speaking feedback. Stop browser speech before capture;
if another speech engine is used, supply a `stopSpeaking` callback that also
stops it. Keep typed input available and serialize command requests.
`postCommand(text)` sends the existing JSON contract to the same origin.
The demo uses an explicit fake service; it does not implement chemistry.

Serve on localhost or HTTPS. Chrome is the initial demo target; detect support
at runtime. Browser speech may use a remote provider and need internet access.
Optional `SpeechRecognitionPhrase` hints are used where supported; deprecated
grammars have no recognition effect. No local-only processing is promised.

## POST /command

Implemented by both Flask `api.py` and the combined `voice_server.py`. The
continuous app uses `/utterance` for language interpretation and this same
dispatcher for its resulting canonical commands.
Run one command (the same strings the terminal app accepts, e.g. "add carbon",
"add oxygen double bond to atom two", "read it back").

Request: { "text": "add carbon" }

Response (always 200 unless the server itself errored):
{
  "ok": true,
  "message": "Added carbon as atom 1.",
  "smiles": "C",
  "summary": "1 carbon, 1 atom in total, 4 hydrogens.",
  "detail": "Atom 1, carbon, ... The current atom is atom 1, carbon.",
  "current_atom": 1,
  "atoms": [ { "number": 1, "symbol": "C", "implicit_hydrogens": 4, "bonds": [] } ],
  "image_url": "/image?v=1"
}

Fields:
- ok (bool): did the command succeed? A rejected command returns ok:false with a
  plain-language message and the molecule UNCHANGED.
- message (string): spoken/printed feedback. Frontend shows it and puts it in an
  aria-live region.
- smiles (string): canonical SMILES, or "" when empty.
- summary / detail (string): from readback.py.
- current_atom (int or null): 1-based cursor, null when empty.
- atoms (list): from Builder.describe_atoms().
- image_url (string): URL to fetch the current picture; include a changing v= so
  the browser does not cache a stale image.

## GET /state
Return the current molecule WITHOUT changing anything (initial load / re-sync).
Same shape as /command minus ok/message (or ok:true, message:""). Use for the
always-visible live view.

## GET /image
Return the current structure as an image. Query ?fmt=svg (recommended for web)
or ?fmt=png. The backend draws numbered atoms with the current atom highlighted
(see export.py). Empty molecule: return a friendly placeholder or 204.

## (Optional) POST /transcribe — only if Person 2 chooses server-side voice
If voice runs in the browser (Web Speech API), this is NOT needed. If voice runs
server-side (Whisper): request is audio bytes (multipart/form-data, 16 kHz mono
WAV); response is { "text": "add carbon" } or { "text": "" } for silence (never
invent words). Person 2 decides and updates this file if they add it.

## Error behavior
- Unparseable command: ok:false, message "I didn't understand that. Try: add
  carbon; add oxygen double bond; go to atom 3.", molecule unchanged.
- Never 500 on ordinary bad input. Reserve non-200 for real server faults.

## Mocking (so nobody is blocked)
Until POST /command is live, frontend and voice hit a fake returning the shapes
above. Agree on 3-4 canned examples (empty, one carbon, acetone, a rejection).
