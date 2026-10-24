# Role 3 — Frontend / Website

Paste this whole file into a new Kiro chat and say: "This is my role on the voice-to-molecule project. Read it and help me build it. Start by having me clone the repo and run the tests." Also read COLLABORATOR_HANDOFF.md and API.md in the repo.

## You own
The website the end user sees: the HTML/CSS/JS page, how it talks to the backend API, and deployment. You are the "face" of the product.

## The project in one line
A speech-to-structure tool for blind/low-vision organic chemistry students. The Python backend (Person 1) builds and validates molecules and exposes them over HTTP (see API.md). You render that in a browser. Chemistry stays in the backend; you never compute chemistry in JavaScript.

## Architecture (Option A)
Python backend + web UI wrapper. Your page calls the backend's HTTP endpoints (POST /command, GET /state, GET /image) and displays the results. You do NOT reimplement the builder or parser in JS.

## Accessibility is your headline feature (this is a blind-user tool)
Requirements, not nice-to-haves:
- Put the command result (message, summary) in an aria-live="polite" region so screen readers announce every update.
- Everything operable by keyboard alone; visible focus states; logical tab order. No mouse-only interactions.
- Large, high-contrast text (WCAG AA). Respect OS reduced-motion / high-contrast settings.
- Label the command input and all controls (label, aria-label).
- A visible command list, and a friendly empty state.
- The structure image (GET /image?fmt=svg) must have meaningful alt text (use the backend's summary), since the image is for sighted viewers.

## Your tasks (in order)
1. Clone, set up, run the Python tests once so you can run the backend locally (expect ~444 passed).
2. Agree the API contract with the team (API.md). Build against a MOCK first: a small JS object returning canned JSON shapes (empty, one carbon, acetone, a rejection). This unblocks you before the real backend exists.
3. Build the page: a command input that POSTs {text} to /command and shows message (aria-live), smiles, the structure image, and the atom list/summary; the structure view always visible and refreshed after every command (cache-busting query each time); on load call /state; a visible command help panel.
4. Coordinate with Person 2 (voice): their speech-to-text produces a text string that goes into the SAME /command call your typed input uses. If voice runs in the browser, plan a "push to talk" control on your page that fills the command field.
5. Deploy: for the demo, running locally (backend + page) is enough. A simple free host is a bonus. Keep it reproducible.

## Stack
Open to you. Plain HTML/CSS/JS is fine and fastest; React/Vite is OK if you are comfortable. Prioritize the accessibility requirements over visual polish.

## How to verify
With the backend running, build a molecule end to end from the page: "add carbon", "add oxygen double bond to atom one", "read it back" — message, SMILES, and image update, and a screen reader announces the message. Turn on VoiceOver (Mac) or NVDA (Windows) and confirm you can tell what happened without looking. Try "add nitrogen" and confirm the page shows the "only carbon and oxygen" message and the structure does not change.

## Workflow
Pull main first; branch (frontend/web-ui); keep the web UI in its own folder (e.g. web/) so you do not collide with Python modules; run the Python tests before pushing anything that touches the backend; PR; never commit to main.
