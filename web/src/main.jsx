import React, { useEffect, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import "./styles.css";
import { createBrowserController } from "../browser-controller.mjs";
import { STARTUP_MESSAGE } from "../startup.mjs";

const API = "/api"; // Vite proxies /api → http://127.0.0.1:8001

// Display-only tidy-up for transcript "heard" lines: Chrome speech output often
// lacks a leading capital and end punctuation. This affects the shown text only;
// the raw transcript is still what gets submitted to the backend.
function formatHeard(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return trimmed;
  const capitalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capitalized) ? capitalized : capitalized + ".";
}

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
const HIGHLIGHT_COLOR = "#f2b134"; // amber-yellow, matches the Send button (--card-info)

function Viewer3D({ version, currentAtom, highlight }) {
  const containerRef = useRef(null);
  const viewerRef    = useRef(null);
  const [empty, setEmpty] = useState(true);

  // Initialise 3Dmol once on mount
  useEffect(() => {
    if (!window.$3Dmol || !containerRef.current) return;
    viewerRef.current = window.$3Dmol.createViewer(containerRef.current, {
      backgroundColor: "#12241b", // solid dark green on-palette; never white
    });
    viewerRef.current.setBackgroundColor(0x12241b, 1);
  }, []);

  // Reload the MOL block whenever version changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    fetch(`${API}/structure3d`)
      .then(r => r.status === 204 ? null : r.text())
      .then(block => {
        viewer.clear();
        // Keep the solid dark-green background on every reload so the panel
        // never repaints white when a molecule renders.
        viewer.setBackgroundColor(0x12241b, 1);
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

        // Highlight: during readback, the segment's atom or bond takes
        // precedence; otherwise the builder's current atom. The MOL block has
        // explicit H atoms, so index into heavy atoms by the 1-based number.
        const heavyAtoms = viewer.getModel()
          .selectedAtoms({ elem: HEAVY_ELEMENTS })
          .sort((a, b) => a.serial - b.serial);
        const highlightNumbers = highlight && highlight.atom != null
          ? [highlight.atom]
          : highlight && highlight.bond
            ? highlight.bond
            : (currentAtom != null ? [currentAtom] : []);
        for (const number of highlightNumbers) {
          const target = heavyAtoms[number - 1];
          if (target != null) {
            viewer.setStyle({ serial: target.serial }, {
              stick:  { radius: 0.18, color: HIGHLIGHT_COLOR },
              sphere: { scale: 0.38, color: HIGHLIGHT_COLOR },
            });
          }
        }

        viewer.zoomTo();
        viewer.spin("y", 0.5);
        // Final re-assert: addModel/setStyle can restore a default clear colour,
        // so set the solid dark green just before render to avoid a white flash.
        viewer.setBackgroundColor(0x12241b, 1);
        viewer.render();
      })
      .catch(() => {});
  }, [version, currentAtom, highlight]);

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
  const BASE_D = "M 60 10 A 50 50 0 1 1 59.99 10 Z";

  useEffect(() => {
    if (!listening) return;           // idle renders a static circle declaratively
    let cancelled = false;
    const draw = () => {
      if (cancelled || !pathRef.current) return;
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
      pathRef.current.setAttribute("d", `M ${pts.join(" L ")} Z`);
      frameRef.current = requestAnimationFrame(draw);
    };
    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelled = true;
      if (frameRef.current) { cancelAnimationFrame(frameRef.current); frameRef.current = null; }
    };
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
      {/* Keyed on `listening` so the ring subtree remounts fresh on every
          toggle. A stopped mic always mounts clean static SVG — no animated
          leftover geometry (wobble path or ripple radius) can be left frozen. */}
      <svg key={listening ? "on" : "off"} viewBox="0 0 120 120" aria-hidden="true">
        {listening ? (
          <>
            {/* Live wobble path (RAF-driven) + animated ripples */}
            <path ref={pathRef} className="ring-wave" d={BASE_D} />
            <circle className="ripple r1" cx="60" cy="60" r="52" />
            <circle className="ripple r2" cx="60" cy="60" r="52" />
            <circle className="ripple r3" cx="60" cy="60" r="52" />
          </>
        ) : (
          /* Idle: a single clean static ring, no animation state at all. */
          <path className="ring-wave" d={BASE_D} />
        )}
        {/* Inner filled circle */}
        <circle cx="60" cy="60" r="38" className="ring-fill" />
        {/* Mic icon */}
        <g className="mic-glyph" transform="translate(60,60)" fill="white">
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
    commonName ? { cls: "mol-name",    text: commonName } : null,
    formula    ? { cls: "mol-formula", text: formula }    : null,
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
// ---------------------------------------------------------------------------
// Settings popout panel
// ---------------------------------------------------------------------------
function SettingsPanel({ open, muted, onMute, onClose }) {
  if (!open) return null;
  return (
    <div className="settings-overlay" role="dialog" aria-modal="true" aria-label="Settings">
      <div className="settings-panel">
        <div className="settings-head">
          <h2 className="settings-title">Settings</h2>
          <button className="settings-close" aria-label="Close settings" onClick={onClose}>×</button>
        </div>
        <div className="settings-row">
          <span className="toggle-label">Mute</span>
          <label className="toggle">
            <input id="spoken" type="checkbox" checked={muted} onChange={event => onMute(event.target.checked)} />
            <span className="toggle-track" aria-hidden="true"><span className="toggle-knob" /></span>
          </label>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Logo — an audio waveform in the shape of a hexagon.
// A hexagon outline with vertical sound bars inside whose heights rise toward
// the center like a waveform.
// ---------------------------------------------------------------------------
function Logo() {
  // Bars across the hexagon width; heights peak in the middle (waveform).
  const bars = [
    { x: 14, h: 10 },
    { x: 20, h: 20 },
    { x: 26, h: 30 },
    { x: 32, h: 38 },
    { x: 38, h: 30 },
    { x: 44, h: 20 },
    { x: 50, h: 10 },
  ];
  return (
    <svg className="logo-mark" viewBox="0 0 64 56" width="40" height="36" role="img" aria-label="ChemSpeak logo: audio waveform in a hexagon">
      {/* hexagon outline */}
      <polygon
        points="32,4 56,18 56,38 32,52 8,38 8,18"
        fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"
      />
      {/* waveform bars, centered vertically at y=28 */}
      <g stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
        {bars.map(({ x, h }) => (
          <line key={x} x1={x} y1={28 - h / 2} x2={x} y2={28 + h / 2} />
        ))}
      </g>
    </svg>
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
  const [status, setStatus] = useState("Enable your microphone to begin.");
  const [mode, setMode] = useState("off");
  const [typed, setTyped] = useState("");
  const [muted, setMuted] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Readback highlight: {atom:n} | {bond:[a,b]} | null. Drives 2D + 3D sync.
  const [highlight, setHighlight] = useState(null);

  // Settings announcement uses the browser speech channel directly so it does
  // not depend on the controller's internal speak(). X/close cancels any speech.
  const openSettings = useCallback(() => {
    setSettingsOpen(true);
    if (!muted && window.speechSynthesis && window.SpeechSynthesisUtterance) {
      const text = "Settings. Mute toggle, currently off.";
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(", " + text);
      u.rate = 1.5;
      window.speechSynthesis.speak(u);
      window.speechSynthesis.resume?.();
    }
  }, [muted]);

  const closeSettings = useCallback(() => {
    window.speechSynthesis?.cancel();
    setSettingsOpen(false);
  }, []);

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
      onHeard: text => addEntry("heard", formatHeard(text)),
      onMessage: text => addEntry("action", text),
      onStatus: setStatus, onListening: setListening, onMode: setMode,
      onMute: setMuted,
      onHighlight: setHighlight,
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

  // During a readback highlight, show the live highlighted SVG for that
  // atom/bond; otherwise show the normal current-molecule image.
  let displayUrl = moleculeUrl;
  if (highlight && moleculeUrl) {
    const sep = moleculeUrl.includes("?") ? "&" : "?";
    if (highlight.atom != null) displayUrl = `${moleculeUrl}${sep}atom=${highlight.atom}`;
    else if (highlight.bond) displayUrl = `${moleculeUrl}${sep}bond=${highlight.bond.join(",")}`;
  }

  return (
    <div className="app-shell">
      {/* TOP BAR */}
      <header className="topbar">
        <div className="brand">
          <span className="brand-logos" aria-hidden="false">
            <Logo />
          </span>
          <span className="brand-name">ChemSpeak</span>
        </div>
        <button className="settings-btn" aria-haspopup="dialog" aria-expanded={settingsOpen} onClick={openSettings}>
          Settings
        </button>
      </header>

      <SettingsPanel
        open={settingsOpen}
        muted={muted}
        onMute={value => { controllerRef.current?.mute(value); }}
        onClose={closeSettings}
      />

      <div className="app">
        {/* LEFT COLUMN — single tab: mic + status, scrolling transcript, typed input pinned bottom */}
        <div className="col-left">
          <div className="rail-top">
            <MicRing listening={listening && mode !== "off"} onClick={toggleMic} disabled={!hasSR} />
            <span className="rail-mode">{listening ? `Microphone on: ${mode}` : "Enable microphone"}</span>
            <p id="voice-status" className="rail-status" role="status">{status}</p>
            <p className="sr-only" id="startup-instructions">{STARTUP_MESSAGE}</p>
            <p className="rail-hint">Lost? Try saying 'Help'!</p>
          </div>

          <div className="rail-transcript">
            <TranscriptLog entries={entries} />
          </div>

          <form
            className="rail-typed"
            onSubmit={event => { event.preventDefault(); controllerRef.current?.type(typed); setTyped(""); }}
          >
            <label htmlFor="text">Type a request or control word</label>
            <div className="rail-typed-row">
              <input id="text" value={typed} onChange={event => setTyped(event.target.value)} />
              <button type="submit">Send</button>
            </div>
          </form>
        </div>

      {/* CENTER COLUMN */}
      <div className="col-center">
        <div className="molecule-card">
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
                <img className="molecule-img" src={displayUrl} alt="Current molecule structure" />
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
                Enable your microphone by clicking<br/>the icon or hitting space!
              </motion.span>
            )
          }
        </AnimatePresence>
        </div>
      </div>

      {/* RIGHT COLUMN */}
      <div className="col-right">
        <div className="panel top">
          <Viewer3D version={version} currentAtom={currentAtom} highlight={highlight} />
        </div>
        <div className="panel bottom">
          <MoleculeInfo atoms={atoms} smiles={smiles} />
        </div>
      </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
