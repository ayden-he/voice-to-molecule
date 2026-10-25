# API Contract — Voice-to-Molecule

Base URL: `http://localhost:5000` (default port; pass a different port as the
first argument to `server.py`).

All JSON responses share the same envelope shape (see §Response envelope).

---

## POST /command

Execute one text command against the shared molecule.

### Request

```
Content-Type: application/json

{ "text": "<command string>" }
```

`text` must be a non-empty string. It is normalized (lowercased, punctuation
stripped) before parsing, so "Add Carbon" and "add carbon" are equivalent.

### Response — 200 OK

```jsonc
{
  "ok": true,           // false when the command was rejected
  "message": "Added carbon as atom 1.",
  "smiles": "C",        // canonical SMILES; "" when the molecule is empty
  "current_atom": 1,    // 1-based; null when the molecule is empty
  "summary": "1 carbon, 1 atom in total, 4 hydrogens.",
  "atoms": [            // one entry per atom in added order
    {
      "number": 1,
      "symbol": "C",
      "implicit_hydrogens": 4,
      "bonds": []       // empty for an isolated atom
    }
  ]
}
```

When `ok` is `false` the molecule is **unchanged**. `message` is the
human-readable rejection reason (suitable for an aria-live region).

### Response — 400 Bad Request

Returned when the request body is missing, not JSON, or lacks a `"text"` field.

```json
{ "ok": false, "message": "Send JSON with a \"text\" field.", ... }
```

---

## GET /state

Return the current molecule state without changing it.

### Response — 200 OK

Same envelope as `POST /command` with `ok: true` and `message` set to the
one-sentence summary.

---

## GET /image

Return a molecule drawing.

### Query parameters

| Parameter | Values              | Default | Notes                                      |
|-----------|---------------------|---------|--------------------------------------------|
| `fmt`     | `png` \| `svg`      | `png`   | Image format                               |
| `t`       | any string          | —       | Ignored; pass `Date.now()` to bust caches  |

### Response — 200 OK

Binary image with `Content-Type: image/png` or `image/svg+xml`.

Atom numbers are drawn as notes on each atom. The current atom is highlighted
in amber.

### Response — 204 No Content

The molecule is empty; no image body is returned. The frontend should show
its empty-state placeholder instead.

### Response — 400 Bad Request

`fmt` was neither `png` nor `svg`.

### Response — 500 Internal Server Error

RDKit could not render the molecule (should not happen under normal use).

---

## Response envelope (all endpoints)

| Field          | Type            | Description                                       |
|----------------|-----------------|---------------------------------------------------|
| `ok`           | boolean         | `true` = command accepted; `false` = rejected     |
| `message`      | string          | Human-readable result, suitable for TTS / aria-live |
| `smiles`       | string          | Canonical SMILES; `""` when empty                 |
| `current_atom` | integer \| null | 1-based cursor position; `null` when empty        |
| `summary`      | string          | One-sentence composition summary                  |
| `atoms`        | array           | Per-atom detail (see below)                       |

### `atoms` entry

| Field                | Type    | Description                            |
|----------------------|---------|----------------------------------------|
| `number`             | integer | 1-based index in added order           |
| `symbol`             | string  | `"C"` or `"O"`                         |
| `implicit_hydrogens` | integer | RDKit-computed implicit hydrogen count |
| `bonds`              | array   | Each: `{ "atom": N, "order": 1|2|3 }` |

---

## CORS

All responses include `Access-Control-Allow-Origin: *` so the HTML page can be
opened directly from the filesystem without a proxy.

---

## Supported commands (quick reference)

| Category | Example commands |
|----------|-----------------|
| Add atom | `add carbon`, `add oxygen double bond` |
| Add chain | `add five carbons`, `add 3 carbons to atom 2` |
| Add group | `add methyl`, `add carboxylic acid to atom 1` |
| Add ring | `add benzene ring`, `add cyclohexane` |
| Connect | `bond atom 1 to atom 3`, `close the ring` |
| Edit bond | `change the bond between 2 and 3 to double` |
| Delete | `delete atom 4` |
| Navigate | `go to atom 2`, `where am I`, `what can I add` |
| Undo | `undo` |
| Reset | `start over` |
| Read | `read it back`, `summary` |

Commands that are not meaningful over HTTP (`quit`, `show`, `save`, `faster`,
`slower`) return `ok: false` with an explanatory message.

---

## JS mock (for frontend development without a running backend)

```js
const MOCK = {
  async postCommand(text) {
    if (text === "add carbon")
      return { ok: true, message: "Added carbon as atom 1.",
               smiles: "C", current_atom: 1,
               summary: "1 carbon, 1 atom in total, 4 hydrogens.",
               atoms: [{ number:1, symbol:"C", implicit_hydrogens:4, bonds:[] }] };
    if (text === "add nitrogen")
      return { ok: false, message: "Only carbon and oxygen can be added. Hydrogens are added automatically.",
               smiles: "", current_atom: null, summary: "The molecule is empty.", atoms: [] };
    return { ok: false, message: "I didn't understand that.", smiles: "", current_atom: null,
             summary: "The molecule is empty.", atoms: [] };
  },
  async getState() {
    return { ok: true, message: "The molecule is empty.", smiles: "",
             current_atom: null, summary: "The molecule is empty.", atoms: [] };
  },
};
```
