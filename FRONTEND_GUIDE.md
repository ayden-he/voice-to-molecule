# Frontend Build Guide (everything you need to build the website)

This is the detailed companion to roles/ROLE_3_FRONTEND.md. It gives you the
exact API behavior, example responses, an accessibility checklist, and a worked
starter page so you can build the whole site without guessing. Chemistry lives
in the Python backend; you only call it and display results.

## 1. How to run the backend locally

For the combined Gemini voice app, run `python voice_server.py` and use
`http://127.0.0.1:8001` for both canonical `/command` requests and streamed
AI `/utterance` requests. Open `/` on that server for the supplied voice page.
See README.md for the server-only API key setup. The alternative deterministic
Flask server runs with `python api.py` on port 5000. Choose one server/session;
the two processes do not share molecules. Both use `command_engine.py`.
The combined voice server expects same-origin requests; host its frontend on
that server. The cross-origin development support below applies to Flask.

Leave that running in one terminal. Your web page calls it. The server keeps ONE
molecule for its lifetime (single-user, fine for the demo). Restart the server
to start a fresh molecule, or send the command "start over".

CORS is enabled on the server, so your page can run from a different port during
development.

## 2. The three endpoints (full contract)

### POST /command   body: {"text": "<a command>"}
Runs one command and returns the full state. Always HTTP 200 for ordinary input
(including rejected commands). Example response for {"text":"add carbon"}:
```json
{
  "ok": true,
  "message": "Added carbon as atom 1.",
  "smiles": "C",
  "summary": "1 carbon, 1 atom in total, 4 hydrogens.",
  "detail": "Atom 1, carbon, with 4 hydrogens, not bonded to anything yet. The current atom is atom 1, carbon.",
  "current_atom": 1,
  "atoms": [ {"number": 1, "symbol": "C", "implicit_hydrogens": 4, "bonds": []} ],
  "image_url": "/image?v=1"
}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Voice to Molecule</title>
  <style>
    body { font: 20px/1.5 system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #111; background: #fff; }
    h1 { font-size: 1.6rem; }
    #struct { border: 2px solid #333; min-height: 200px; display: grid; place-items: center; }
    form { display: flex; gap: .5rem; margin: 1rem 0; }
    input[type=text] { flex: 1; font-size: 1.1rem; padding: .6rem; }
    button { font-size: 1.1rem; padding: .6rem 1rem; cursor: pointer; }
    #message { font-weight: 600; min-height: 1.5em; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    details { margin-top: 1rem; } code { background: #f0f0f0; padding: 0 .2em; }
    :focus { outline: 3px solid #0a58ca; outline-offset: 2px; }
  </style>
</head>
<body>
  <h1>Voice to Molecule</h1>
  <p id="message">Loading…</p>

  <div class="visually-hidden" aria-live="polite" id="live"></div>

  <div id="struct"><p id="empty">No atoms yet. Try: add carbon.</p></div>
  <p><strong>SMILES:</strong> <span id="smiles">—</span></p>

  <form id="cmdform">
    <label class="visually-hidden" for="cmd">Enter a command</label>
    <input type="text" id="cmd" autocomplete="off"
           placeholder="e.g. add carbon, add oxygen double bond, read it back">
    <button type="submit">Run</button>
  </form>

  <details>
    <summary>What can I say?</summary>
    <ul>
      <li><code>add carbon</code>, <code>add oxygen double bond</code>, <code>add five carbons</code></li>
      <li><code>add methyl</code>, <code>add hydroxyl</code>, <code>add benzene ring</code> … add <code>to atom N</code></li>
      <li><code>go to atom N</code>, <code>delete atom N</code>, <code>start over</code>, <code>undo</code></li>
      <li><code>read it back</code>, <code>summary</code>, <code>where am I</code>, <code>what can I add</code></li>
    </ul>
  </details>

  <script>
    const API_BASE = "http://127.0.0.1:5000";
    const $ = (id) => document.getElementById(id);

    function render(data) {
      $("message").textContent = data.message || "";
      $("live").textContent = data.message || "";
      $("smiles").textContent = data.smiles || "—";
      const struct = $("struct");
      if (!data.smiles) {
        struct.innerHTML = '<p>No atoms yet. Try: add carbon.</p>';
        return;
      }
      const img = new Image();
      img.alt = data.summary || "molecular structure";
      img.src = API_BASE + data.image_url;
      img.style.maxWidth = "100%";
      struct.innerHTML = "";
      struct.appendChild(img);
    }

    async function sendCommand(text) {
      const res = await fetch(API_BASE + "/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      render(await res.json());
    }

    fetch(API_BASE + "/state").then(r => r.json()).then(render)
      .catch(() => $("message").textContent = "Cannot reach the backend. Is api.py running?");

    $("cmdform").addEventListener("submit", (e) => {
      e.preventDefault();
      const text = $("cmd").value.trim();
      if (text) { sendCommand(text); $("cmd").value = ""; $("cmd").focus(); }
    });
  </script>
</body>
</html>
