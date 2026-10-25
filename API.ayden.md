# API Contract (the shared seam between all three roles)

This is the agreement that lets the backend, voice, and frontend people work in
parallel without blocking each other. Agree on this first. Change it only by
team agreement, and update this file when you do.

The backend (Person 1) implements these endpoints. The frontend (Person 3) and
voice (Person 2) code against them ΓÇö and can build against a mock that returns
canned versions of these shapes until the real backend is ready.

## Principle (do not break)
The AI never does chemistry. Voice/browser turns speech into text; that text is
sent to /command; the Python backend runs the deterministic parser + RDKit and
returns the result. Chemistry lives only in the backend.

## Base
- Local dev server, e.g. http://127.0.0.1:5000
- All request and response bodies are JSON.
- One molecule-building session per server process is fine for the hackathon
  (a single shared Builder). Multi-user sessions are out of scope.

## POST /command
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

## (Optional) POST /transcribe ΓÇö only if Person 2 chooses server-side voice
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
