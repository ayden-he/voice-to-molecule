# Kiro Development Handoff: Voice-to-Molecule Notebook

Updated: 2026-10-24
Workspace: `C:\Users\Siddh\voice-to-molecule`

## Read this first

This handoff describes the current notebook-only frontend and how it connects to the existing GitHub backend. The backend of record is checked-in `voice_server.py` (Gemini interpretation plus molecule API), backed by `conversation.py`, `command_engine.py`, and `builder.py`. Do not recreate chemistry, Gemini interpretation, or molecule drawing in the frontend. `builder.py` and the checked-in engine are authoritative.

The user explicitly said: **"Don't use your own backend code, all the functionalities should be straight from the GitHub."** The temporary, untracked custom `server.py` was removed. Do not restore it. The app has one user-facing React frontend, the Notebook. The studio UI was removed from `web/src/main.jsx`; `/` and `/notebook` both render the notebook.

## Current experience

- Full viewport, split 25% left / 75% right.
- Left column: cyan microphone ring in the upper half; heard transcript and interpreted result in the lower half. A vertical divider separates this from the drawing, and a horizontal rule divides the two left sections.
- Right column: molecule SVG from the backend, shown only when the backend state has a nonempty SMILES string.
- Microphone is started/stopped by clicking the ring. The ring has a soft, nonuniform cyan pulse while browser speech recognition is active.
- The notebook shows the recognized phrase under HEARD, then backend event message under ACTION.
- There is no sample molecule on startup.

## Architecture and data flow

### Frontend

- `web/index.html`: Vite entry document; title is "Sentence Structure Notebook".
- `web/src/main.jsx`: React notebook. It is now the only React view. It fetches initial state, uses `createVoice` for one utterance at a time, posts finalized transcripts to `/api/utterance`, parses newline-delimited JSON events, and updates the visible molecule using the backend-provided `image_url`.
- `web/src/styles.css`: contains notebook CSS near the end, plus older unused studio CSS retained from the former React UI. Current `main.jsx` no longer renders studio components.
- `web/voice.mjs`: existing project mic helper (`createVoice`). A local change makes it retry once without phrase hints if Chrome emits `phrases-not-supported`.
- `web/vite.config.js`: Vite dev server on `127.0.0.1:5173`; `/api/*` proxies to `http://127.0.0.1:8001/*`, strips `/api`, and rewrites `Origin` to satisfy `voice_server.py`'s same-origin mutation guard.
- `package.json` at repository root has `npm run dev` and `npm run build`; Vite's root is `web/`.

`NOTEBOOK_API_BASE` defaults to `/api`. Backend image paths like `/image?v=2` are prefixed to `/api/image?v=2`. The voice server always returns its own numbered SVG. Do not redraw or restyle the backend SVG with a second chemistry renderer.

### Backend (checked-in GitHub implementation)

- `voice_server.py`: local HTTP server on port 8001. It owns one conversation/molecule state and provides `/health`, `/state`, `/image`, `/command`, and `/utterance`.
- `conversation.py`: ordered Gemini interpretation, validation, clarification barriers, pending instructions, undo handling, and event generation.
- `interpreter.py`: server-side Gemini call and structured plan validation. The API key is read from `GEMINI_API_KEY` in the server process and sent to Google in a header; it is not part of browser requests.
- `command_engine.py`: shared deterministic command dispatcher and SVG drawing, used by both `voice_server.py` and `api.py`.
- `builder.py`: chemistry operations and molecule state. RDKit is the chemistry authority.
- `api.py`: separate deterministic Flask API on port 5000. It shares engine code but runs a separate molecule session. Do not run it expecting shared state with `voice_server.py`.

`POST /utterance` is **NDJSON**, not a single JSON object: it streams one JSON state event per executed action or clarification barrier. Each event has state, `ok`, `message`, `queued`, and `version`. `/image` returns backend SVG. The notebook consumes this stream and updates its image from each event.

## Running locally

The Vite site is `http://127.0.0.1:5173/` (and `/notebook`). The voice service is `http://127.0.0.1:8001/`. From the repository root:

```powershell
npm install
npm run dev
```

In another PowerShell window, start the GitHub voice backend with the key in that process environment. To enter the key without echoing it, use:

```powershell
$secureKey = Read-Host 'Gemini API key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
.venv\Scripts\python.exe voice_server.py
```

Alternatively, `start_notebook.ps1` prompts securely when no process-level key is already set and launches `voice_server.py`. Keep that PowerShell window open while using the site. Closing the server process stops the API; the environment variable is not persisted to disk by the script.

Check configuration without printing the secret:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health |
  Select-Object provider, model, api_key_configured
```

At handoff time, port 8001 answered `/health` with provider `gemini`, model `gemini-3.5-flash-lite`, and `api_key_configured: true`. The actual Gemini utterance flow and physical microphone have not been manually tested in this handoff turn. Vite was already running on port 5173.

## Current limitations and follow-up work

1. **One utterance per ring click.** `createVoice` uses `continuous = false` and `interimResults = false`. It forwards one finalized phrase, then stops. The UI does not currently implement the official continuous microphone session controls from `web/voice-app.mjs` / `web/session.mjs` (Enable, Start, Pause, Stop, Skip, TTS, queue indicator). If adding these, reuse the checked-in session logic rather than inventing new backend semantics.
2. **No typed input in the notebook UI.** The official backend supports `/command`, but the notebook currently exposes only microphone capture. Add a text form if full non-mic command access is desired; send it through the same proxied voice server so it shares state and undo history.
3. **The frontend currently posts transcripts only to `/utterance`.** Undo is specially handled by `Conversation.accept`; other control words such as Start/Pause/Stop are client-session controls in the original `web/voice-app.mjs`. The notebook does not currently implement those controls. Avoid sending those words to Gemini unless deliberately choosing to change that interaction model.
4. **Direct backend root still serves the upstream voice app.** `voice_server.py` serves checked-in `web/voice-app.html` at its own `/`. The notebook-only product frontend is the Vite app on port 5173. Avoid navigating to port 8001 as the user-facing notebook. Do not alter `voice_server.py` merely to hide its upstream page unless the user explicitly wants to change the canonical backend interface; keep the notebook as the public frontend and the voice server as its API.
5. **Build distribution.** `npm run build` creates `web/dist`, but `voice_server.py` does not serve that React build. Local setup uses Vite dev server. If production hosting is needed, select a static frontend host or add a documented hosting layer without replacing the project backend.
6. **Legacy files/docs.** `README.md` still has a stale Web UI paragraph that says `python server.py`; that file was removed. `API.kiro.md` is an older, incompatible contract describing `server.py` on port 5000 and omits the current Gemini NDJSON flow. Prefer actual source and current `API.md`; update or retire these stale docs before relying on their instructions.
7. **Styling cleanup.** `web/src/styles.css` retains unused studio CSS and an old Reenie Beanie font import. Notebook-specific CSS is present, and notebook text currently uses Arial. Cleaning unused CSS is safe only after confirming no notebook selector depends on it.
8. **Phrase-hint fallback.** The shared `web/voice.mjs` has a local modification: if a browser rejects optional contextual phrase hints with `phrases-not-supported`, it disables hints and retries once. Preserve this behavior unless fixing it another way; it addressed a reported Chrome recognition error.
9. **Gemini configuration is process-local.** The key was confirmed configured in the currently running voice server by `/health`; never print it, put it in frontend code, commit it, or include it in this handoff. If the server is restarted in another process, set the key in that process environment again.

## Verification recorded

- `npm run build` succeeded after the notebook became the sole React view.
- HTTP smoke checks returned 200 for Vite `/` and `/notebook`.
- `/health` returned `api_key_configured: true` for the running port 8001 voice server.
- No pytest suite or real Chrome microphone/Gemini mutation was run during the handoff turn. Do not infer end-to-end correctness from build/health alone.

## Git/worktree context

- Branch: `main`, at `1e2d214` (`origin/main` points to the same commit when inspected).
- A local `frontend/web-ui` branch also points at `1e2d214`.
- The worktree contains user/local changes. At inspection, `.gitignore`, `API.md`, `README.md`, and `requirements.txt` had staged changes; `web/voice.mjs` had an unstaged change; and frontend files plus `start_notebook.ps1`, `API.ayden.md`, and `API.kiro.md` were untracked. Do not reset or overwrite these blindly.
- `web/src/main.jsx`, `web/src/styles.css`, `web/vite.config.js`, `web/index.html`, `package.json`, and the launcher are currently local/untracked frontend work; inspect Git status before making changes or committing.
- The temporary assistant-created `server.py` and `tests/test_server.py` were removed because they were custom backend code, not part of GitHub `main`.

## Suggested first steps for Kiro

1. Read this handoff, then inspect `git status`, `voice_server.py`, `conversation.py`, `command_engine.py`, and `web/src/main.jsx` before editing.
2. Keep `/` and `/notebook` notebook-only. Avoid restoring the studio React UI.
3. Keep all chemistry and molecule rendering in the checked-in backend.
4. Consider completing the frontend's feature coverage: add typed command input and decide whether to adapt `web/session.mjs` for continuous mic controls, while retaining the calm notebook layout.
5. Update stale `README.md` and `API.kiro.md` instructions so there is one clear startup workflow and no reference to deleted `server.py`.
6. Manually validate with Chrome: mic permission, short spoken command, multi-action phrase, ambiguity/clarification, undo, backend image updates, and browser refresh/state restoration. Check the backend `/health` without exposing the key.
