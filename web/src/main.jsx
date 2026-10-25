import React, { useEffect, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import "./styles.css";
import { createBrowserController } from "../browser-controller.mjs";
import { STARTUP_MESSAGE } from "../startup.mjs";

const API = "/api"; // Vite proxies /api → http://127.0.0.1:8001

// ---------------------------------------------------------------------------
// 3Dmol viewer component
// ---------------------------------------------------------------------------

// CPK colors for all elements this app supports
const CPK = {
  C:  "#909090",  // grey
  O:  "#FF0D0D",  // red
  H:  "#FFFFFF",  // white
  F:  "#90E050",  // green
  Cl: "#1FF01F",  // bright green
  Br: "#A62929",  // dark red
  I:  "#940094",  // purple
};
const HEAVY_ELEMENTS = ["C", "O", "F", "Cl", "Br", "I"];
const HIGHLIGHT_COLOR = "#00FFFF"; // cyan — not used by any CPK element above

function Viewer3D({ version, currentAtom }) {
  const containerRef = useRef(null);
  const viewerRef    = useRef(null);
  const [empty, setEmpty] = useState(true);

  // Initialise 3Dmol once on mount
  useEffect(() => {
    if (!window.$3Dmol || !containerRef.current) return;
    viewerRef.current = window.$3Dmol.createViewer(containerRef.current, {
      backgroundColor: "white",
    });
  }, []);

  // Reload the MOL block whenever version changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    fetch(`${API}/structure3d`)
      .then(r => r.status === 204 ? null : r.text())
      .then(block => {
        viewer.clear();
        if (!block) { setEmpty(true); return; }
        setEmpty(false);
        viewer.addModel(block, "mol");

        // Base style — grey for everything, then override per element
        viewer.setStyle({}, {
          stick:  { radius: 0.15, color: CPK.C },
          sphere: { scale: 0.3,  color: CPK.C },
        });

        // Explicit CPK colors per element
        Object.entries(CPK).forEach(([elem, color]) => {
          viewer.setStyle({ elem }, {
            stick:  { radius: 0.15, color },
            sphere: { scale: 0.3,  color },
          });
        });

        // Highlight the current atom in cyan.
        // The MOL block includes explicit H atoms for 3D embedding — filter
        // to only C and O (the only elements this app builds) so the index
        // matches the builder's 1-based heavy-atom cursor exactly.
        if (currentAtom != null) {
          const heavyAtoms = viewer.getModel()
            .selectedAtoms({ elem: HEAVY_ELEMENTS })
            .sort((a, b) => a.serial - b.serial);
          const target = heavyAtoms[currentAtom - 1];
          if (target != null) {
            viewer.setStyle({ serial: target.serial }, {
              stick:  { radius: 0.18, color: HIGHLIGHT_COLOR },
              sphere: { scale: 0.38, color: HIGHLIGHT_COLOR },
            });
          }
        }

        viewer.zoomTo();
        viewer.spin("y", 0.5);
        viewer.render();
      })
      .catch(() => {});
  }, [version, currentAtom]);

  return (
    <div className="viewer-3d-wrap">
      {empty && <span className="panel-empty">No molecule yet</span>}
      <div ref={containerRef} className="viewer-3d" style={{ opacity: empty ? 0 : 1 }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mic ring component
// ---------------------------------------------------------------------------
function MicRing({ listening, onClick, disabled }) {
  const pathRef = useRef(null);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!listening) {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      if (pathRef.current)
        pathRef.current.setAttribute("d", "M 60 10 A 50 50 0 1 1 59.99 10 Z");
      return;
    }
    const draw = () => {
      const t = performance.now() / 1000;
      const N = 80;
      const pts = [];
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2 - Math.PI / 2;
        const pulse  = Math.sin(t * 1.4 + Math.sin(a * 3) * 0.7);
        const ripple = Math.sin(a * 5 + t * 0.8) * 1.3
                     + Math.sin(a * 9 - t * 0.5) * 0.6;
        const r = 50 + pulse * 2 + ripple;
        pts.push(`${60 + Math.cos(a) * r},${60 + Math.sin(a) * r}`);
      }
      pathRef.current?.setAttribute("d", `M ${pts.join(" L ")} Z`);
      frameRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [listening]);

  return (
    <button
      className={`mic-ring${listening ? " active" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={listening}
      id="enable"
      aria-label={listening ? "Stop microphone" : "Enable microphone"}
    >
      <svg viewBox="0 0 120 120" aria-hidden="true">
        {/* Pulsing outline path */}
        <path ref={pathRef} className="ring-wave" d="M 60 10 A 50 50 0 1 1 59.99 10 Z" />
        {/* Static ripple rings shown only when active */}
        {listening && <>
          <circle className="ripple r1" cx="60" cy="60" r="52" />
          <circle className="ripple r2" cx="60" cy="60" r="52" />
          <circle className="ripple r3" cx="60" cy="60" r="52" />
        </>}
        {/* Inner filled circle */}
        <circle cx="60" cy="60" r="38" className="ring-fill" />
        {/* Mic icon */}
        <g transform="translate(60,60)" fill="white">
          <rect x="-7" y="-17" width="14" height="20" rx="7" />
          <path d="M-12 2 a12 12 0 0 0 24 0" strokeWidth="2.5" stroke="white" fill="none" strokeLinecap="round"/>
          <line x1="0" y1="14" x2="0" y2="20" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
          <line x1="-5" y1="20" x2="5" y2="20" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
        </g>
      </svg>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Transcript log component
// ---------------------------------------------------------------------------
function TranscriptLog({ entries }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="transcript-log" aria-live="polite" aria-label="Transcript">
      <div className={`transcript-inner${entries.length === 0 ? " is-empty" : ""}`}>
        {entries.length === 0 && (
          <p className="t-empty">No molecule yet</p>
        )}
        {entries.map((entry, i) =>
          entry.type === "heard"
            ? <p key={i} className="t-heard">{entry.text}</p>
            : <p key={i} className="t-action">{entry.text}</p>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Molecular formula from atoms array
// e.g. [{symbol:"C",...},{symbol:"O",...}] → "C₂H₆O"
// ---------------------------------------------------------------------------
const SUBSCRIPTS = "₀₁₂₃₄₅₆₇₈₉";
function sub(n) {
  return n <= 1 ? "" : String(n).split("").map(d => SUBSCRIPTS[+d]).join("");
}
function molecularFormula(atoms) {
  if (!atoms || atoms.length === 0) return "";
  const counts = {};
  let hTotal = 0;
  for (const a of atoms) {
    counts[a.symbol] = (counts[a.symbol] || 0) + 1;
    hTotal += a.implicit_hydrogens || 0;
  }
  // Hill order: C first, H second, then others alphabetically
  const symbols = Object.keys(counts).sort((a, b) => {
    if (a === "C") return -1; if (b === "C") return 1;
    return a.localeCompare(b);
  });
  let formula = "";
  for (const s of symbols) formula += s + sub(counts[s]);
  if (hTotal > 0) {
    // Insert H after C
    const cIdx = formula.indexOf("C");
    const afterC = formula.slice(formula.indexOf("C")).search(/[A-Z](?!.*[a-z])/);
    formula = formula.replace(/^(C[₀-₉]*)/, `$1H${sub(hTotal)}`);
  }
  return formula;
}

// ---------------------------------------------------------------------------
// Bottom-right: formula + common name + IUPAC with staggered fade-in
// ---------------------------------------------------------------------------
const INFO_VARIANTS = {
  hidden: { opacity: 0, y: 10 },
  show:   (i) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.1, duration: 0.35, ease: "easeOut" },
  }),
  exit:   { opacity: 0, y: -6, transition: { duration: 0.2 } },
};

function MoleculeInfo({ atoms, smiles }) {
  const [commonName, setCommonName] = useState(null);
  const [iupacName, setIupacName]   = useState(null);
  const prevSmiles = useRef(null);

  useEffect(() => {
    if (!smiles || smiles === prevSmiles.current) return;
    prevSmiles.current = smiles;
    setCommonName(null);
    setIupacName(null);
    fetch(`${API}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "name" }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.common_name) setCommonName(data.common_name);
        if (data.iupac_name)  setIupacName(data.iupac_name);
      })
      .catch(() => {});
  }, [smiles]);

  const formula = molecularFormula(atoms);

  const items = [
    formula    ? { cls: "mol-formula", text: formula }    : null,
    commonName ? { cls: "mol-name",    text: commonName } : null,
    iupacName  ? { cls: "mol-iupac",   text: iupacName }  : null,
  ].filter(Boolean);

  return (
    <div className="mol-info">
      <AnimatePresence mode="wait">
        {items.length === 0
          ? (
            <motion.span
              key="empty"
              className="mol-info-empty"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              No molecule yet
            </motion.span>
          )
          : (
            <motion.div
              key={smiles}
              className="mol-info-inner"
              initial="hidden"
              animate="show"
              exit="exit"
            >
              {items.map((item, i) => (
                <motion.span
                  key={item.cls}
                  className={item.cls}
                  custom={i}
                  variants={INFO_VARIANTS}
                >
                  {item.text}
                </motion.span>
              ))}
            </motion.div>
          )
        }
      </AnimatePresence>
    </div>
  );
}
export default function App() {
  const [listening, setListening]     = useState(false);
  const [entries, setEntries]         = useState([]);
  const [moleculeUrl, setMoleculeUrl] = useState("");
  const [version, setVersion]         = useState(0);
  const [atoms, setAtoms]             = useState([]);
  const [smiles, setSmiles]           = useState("");
  const [currentAtom, setCurrentAtom] = useState(null);
  const controllerRef = useRef(null);
  const [status, setStatus] = useState("Enable your microphone, then say Start.");
  const [mode, setMode] = useState("off");
  const [typed, setTyped] = useState("");
  const [muted, setMuted] = useState(false);

  const addEntry = useCallback((type, text) => {
    setEntries(prev => [...prev, { type, text }]);
  }, []);

  const applyState = useCallback(state => {
    if (state.image_url) setMoleculeUrl(`${API}${state.image_url}&fmt=svg`);
    if (state.atoms) setAtoms(state.atoms);
    if (state.smiles !== undefined) setSmiles(state.smiles);
    if (state.current_atom !== undefined) setCurrentAtom(state.current_atom);
    if (state.version !== undefined) setVersion(state.version);
  }, []);

  useEffect(() => {
    const controller = createBrowserController({
      env: window, api: API,
      onState: applyState,
      onHeard: text => addEntry("heard", text),
      onMessage: text => addEntry("action", text),
      onStatus: setStatus, onListening: setListening, onMode: setMode,
    });
    controllerRef.current = controller;
    let mounted = true;
    fetch(`${API}/state`).then(response => {
      if (!response.ok) throw new Error("Backend unavailable");
      return response.json();
    }).then(state => { if (mounted) applyState(state); }).catch(() => {
      if (mounted) setStatus("Could not reach the backend. Start voice_server.py on port 8001.");
    });
    return () => { mounted = false; controller.dispose(); controllerRef.current = null; };
  }, [applyState, addEntry]);

  const toggleMic = useCallback(() => {
    if (listening) controllerRef.current?.stop();
    else controllerRef.current?.enable();
  }, [listening]);

  useEffect(() => {
    const onKey = event => {
      if (event.code === "Space" && event.target === document.body && !event.repeat) {
        event.preventDefault(); toggleMic();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleMic]);

  const hasSR = !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  return (
    <div className="app">
      {/* LEFT COLUMN */}
      <div className="col-left">
        <div className="panel top">
          <div className="voice-controls">
            <MicRing listening={listening} onClick={toggleMic} disabled={!hasSR} />
            <span>{listening ? `Microphone on: ${mode}` : "Enable microphone"}</span>
            <p id="voice-status" role="status">{status}</p>
            <p className="sr-only" id="startup-instructions">{STARTUP_MESSAGE}</p>
            <button id="welcome" aria-describedby="startup-instructions" onClick={() => controllerRef.current?.replay()}>
              Hear startup instructions
            </button>
            <label>
              <input id="spoken" type="checkbox" checked={!muted} onChange={event => {
                const value = !event.target.checked;
                setMuted(value); controllerRef.current?.mute(value);
              }} /> Speak feedback
            </label>
            <form onSubmit={event => {
              event.preventDefault(); controllerRef.current?.type(typed); setTyped("");
            }}>
              <label htmlFor="text">Type a request or control word</label>
              <input id="text" value={typed} onChange={event => setTyped(event.target.value)} />
              <button type="submit">Send</button>
            </form>
          </div>
        </div>
        <div className="panel bottom">
          <TranscriptLog entries={entries} />
        </div>
      </div>

      {/* CENTER COLUMN */}
      <div className="col-center">
        <AnimatePresence mode="wait">
          {(moleculeUrl && atoms.length > 0)
            ? (
              <motion.div
                key={smiles}
                className="molecule-frame"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: "easeInOut" }}
              >
                <img className="molecule-img" src={moleculeUrl} alt="Current molecule structure" />
              </motion.div>
            )
            : (
              <motion.span
                key="empty"
                className="center-empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                Enable microphone or press space,<br/>then say Start and add carbon
              </motion.span>
            )
          }
        </AnimatePresence>
      </div>

      {/* RIGHT COLUMN */}
      <div className="col-right">
        <div className="panel top">
          <Viewer3D version={version} currentAtom={currentAtom} />
        </div>
        <div className="panel bottom">
          <MoleculeInfo atoms={atoms} smiles={smiles} />
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
