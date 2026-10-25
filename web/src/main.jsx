import React, { useEffect, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = "/api"; // Vite proxies /api → http://127.0.0.1:8001

// ---------------------------------------------------------------------------
// 3Dmol viewer component
// ---------------------------------------------------------------------------
function Viewer3D({ version }) {
  const containerRef = useRef(null);
  const viewerRef    = useRef(null);

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
        if (!block) return;
        viewer.addModel(block, "mol");
        viewer.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.3 } });
        viewer.zoomTo();
        viewer.spin("y", 0.5);
        viewer.render();
      })
      .catch(() => {});
  }, [version]);

  return (
    <div className="viewer-3d-wrap">
      <div ref={containerRef} className="viewer-3d" />
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
      aria-label={listening ? "Stop listening" : "Start listening"}
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
      <div className="transcript-inner">
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
// Bottom-right: formula + common name
// ---------------------------------------------------------------------------
function MoleculeInfo({ atoms, smiles }) {
  const [commonName, setCommonName] = useState(null);
  const prevSmiles = useRef(null);

  useEffect(() => {
    if (!smiles || smiles === prevSmiles.current) return;
    prevSmiles.current = smiles;
    setCommonName(null);
    // Ask the backend for the common name via the "name" command
    fetch(`${API}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "name" }),
    })
      .then(r => r.json())
      .then(data => { if (data.common_name) setCommonName(data.common_name); })
      .catch(() => {});
  }, [smiles]);

  const formula = molecularFormula(atoms);

  if (!formula) return (
    <div className="mol-info empty">No molecule yet</div>
  );

  return (
    <div className="mol-info">
      <span className="mol-formula">{formula}</span>
      {commonName && (
        <span className="mol-name"> (<em>{commonName}</em>)</span>
      )}
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
  const recogRef                      = useRef(null);

  const addEntry = useCallback((type, text) => {
    setEntries(prev => [...prev, { type, text }]);
  }, []);

  // Load initial molecule state on mount
  useEffect(() => {
    fetch(`${API}/state`)
      .then(r => r.json())
      .then(state => {
        if (state.image_url) setMoleculeUrl(`${API}${state.image_url}&fmt=svg`);
        if (state.atoms)  setAtoms(state.atoms);
        if (state.smiles !== undefined) setSmiles(state.smiles);
      })
      .catch(() => {});
  }, []);

  // Stream /utterance NDJSON and add each event's message as an action line
  const postUtterance = useCallback(async (text) => {
    try {
      const res = await fetch(`${API}/utterance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.message) addEntry("action", event.message);
          if (event.image_url) setMoleculeUrl(`${API}${event.image_url}&fmt=svg`);
          if (event.atoms !== undefined) setAtoms(event.atoms);
          if (event.smiles !== undefined) setSmiles(event.smiles);
          setVersion(v => v + 1);
        }
      }
      if (buffer.trim()) {
        const event = JSON.parse(buffer);
        if (event.message) addEntry("action", event.message);
        if (event.image_url) setMoleculeUrl(`${API}${event.image_url}&fmt=svg`);
      }
    } catch (err) {
      addEntry("action", "Could not reach the backend.");
    }
  }, [addEntry]);

  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const r = new SR();
    r.lang = "en-US";
    r.continuous = false;
    r.interimResults = false;
    r.onstart  = () => setListening(true);
    r.onend    = () => setListening(false);
    r.onerror  = () => setListening(false);
    r.onresult = (e) => {
      const transcript = e.results[0][0].transcript.trim();
      if (transcript) {
        addEntry("heard", transcript);
        postUtterance(transcript);
      }
    };
    r.start();
    recogRef.current = r;
  }, [addEntry, postUtterance]);

  const stopListening = useCallback(() => {
    recogRef.current?.stop();
    recogRef.current = null;
    setListening(false);
  }, []);

  const toggleMic = useCallback(() => {
    listening ? stopListening() : startListening();
  }, [listening, startListening, stopListening]);

  const hasSR = !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  return (
    <div className="app">
      {/* LEFT COLUMN */}
      <div className="col-left">
        <div className="panel top">
          <MicRing listening={listening} onClick={toggleMic} disabled={!hasSR} />
        </div>
        <div className="panel bottom">
          <TranscriptLog entries={entries} />
        </div>
      </div>

      {/* CENTER COLUMN */}
      <div className="col-center">
        {moleculeUrl
          ? <img className="molecule-img" src={moleculeUrl} alt="Current molecule structure" />
          : <span className="molecule-empty">No molecule yet</span>
        }
      </div>

      {/* RIGHT COLUMN */}
      <div className="col-right">
        <div className="panel top">
          <Viewer3D version={version} />
        </div>
        <div className="panel bottom">
          <MoleculeInfo atoms={atoms} smiles={smiles} />
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
