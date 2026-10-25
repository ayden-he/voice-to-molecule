import { createSession } from './session.mjs';
import { startupInstructions } from './startup.mjs';

// Browser TTS rate. 1.0 is the (slow-feeling) default; higher is faster.
const SPEECH_RATE = 2;

// Phrase hints bias Chrome's recognizer toward chemistry terms. Support varies
// by browser version, so hints must never be required for recognition to work.
export const VOCABULARY = [
  'add carbon', 'add oxygen', 'add fluorine', 'add chlorine', 'add bromine',
  'add iodine', 'atom', 'single bond', 'double bond', 'triple bond', 'to atom',
  'go to atom', 'methyl', 'ethyl', 'hydroxyl', 'methoxy', 'aldehyde',
  'carboxylic acid', 'acetoxy', 'cyclopropane', 'cyclobutane', 'cyclopentane',
  'cyclohexane', 'benzene', 'close the ring', 'undo', 'start over', 'read it back',
  'summary', 'help', 'start', 'pause', 'stop', 'skip',
];

// Deterministic fixes for frequent Chrome mishearings of chemistry words. Keys
// are lowercase whole words/phrases; applied before display and submission.
const CORRECTIONS = {
  'adam': 'atom', 'atoms': 'atom',
  'flooring': 'fluorine', 'flaurine': 'fluorine', 'florine': 'fluorine',
  'clarine': 'chlorine', 'claurine': 'chlorine',
  'benzine': 'benzene', 'benzyne': 'benzene',
  'hydroxl': 'hydroxyl', 'hydroxil': 'hydroxyl',
  'ethel': 'ethyl', 'methel': 'methyl',
  'bromide': 'bromine', 'iodide': 'iodine', 'ioreen': 'iodine',
  'cyclo hexane': 'cyclohexane', 'cyclo propane': 'cyclopropane',
  'acetoxie': 'acetoxy', 'acetoxi': 'acetoxy',
};

// Replace known-misheard words while preserving the rest of the utterance.
export function correctChemistry(text) {
  if (!text) return text;
  let result = text;
  // Multi-word phrases first.
  for (const [wrong, right] of Object.entries(CORRECTIONS)) {
    if (!wrong.includes(' ')) continue;
    result = result.replace(new RegExp(`\\b${wrong}\\b`, 'gi'), right);
  }
  // Then single words, preserving surrounding text.
  return result.replace(/[a-z]+/gi, word => {
    const fix = CORRECTIONS[word.toLowerCase()];
    return fix && !fix.includes(' ') ? fix : word;
  });
}

// Shared voice behavior for the React frontend; all chemistry stays in Python.
export function createBrowserController({
  env = globalThis, api = '/api',
  onState = () => {}, onHeard = () => {}, onMessage = () => {},
  onStatus = () => {}, onListening = () => {}, onMode = () => {}, onMute = () => {},
  onHighlight = () => {},
}) {
  const Recognition = env.SpeechRecognition || env.webkitSpeechRecognition;
  let current = null;
  let capture = false;
  let disposed = false;
  let muted = false;
  let utterance = null;
  let spokenText = '';
  let restartTimer = null;
  let usePhraseHints = true;
  let readbackToken = 0;
  let warmedUp = false;
  const normalized = text => text.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
  function stopSpeech() {
    utterance = null;
    readbackToken++;          // invalidate any in-progress segment sequence
    onHighlight(null);        // clear readback highlight
    env.speechSynthesis?.cancel();
  }
  // Single source of truth for mute: the Settings toggle, mute() API, and the
  // spoken "mute"/"unmute" commands all route through here and sync the UI.
  function setMuted(value) {
    muted = value;
    if (muted) { welcome.dismiss(); stopSpeech(); }
    onMute(muted);
  }
  // Prime Chrome's speech engine once so the first real utterance after it is
  // not clipped. A silent, near-instant utterance warms the pipeline.
  function warmUpSpeech() {
    if (warmedUp || !env.speechSynthesis || !env.SpeechSynthesisUtterance) return;
    warmedUp = true;
    const primer = new env.SpeechSynthesisUtterance(' ');
    primer.volume = 0;      // inaudible
    primer.rate = SPEECH_RATE;
    env.speechSynthesis.speak(primer);
  }
  function speak(text, { onStart, onError } = {}) {
    if (disposed || muted || !env.speechSynthesis || !env.SpeechSynthesisUtterance) return false;
    stopSpeech();
    // A short leading comma makes Chrome pause briefly before the first real
    // word, which stops it from clipping that word right after cancel().
    const speech = new env.SpeechSynthesisUtterance(', ' + text);
    speech.rate = SPEECH_RATE;   // faster than the slow default
    speech.pitch = 1;
    speech.volume = 1;
    utterance = speech;
    spokenText = normalized(text);   // echo suppression uses the real text
    speech.onstart = () => { if (utterance === speech) onStart?.(); };
    speech.onend = () => { if (utterance === speech) utterance = null; };
    speech.onerror = event => {
      if (utterance !== speech) return;
      utterance = null;
      onError?.(event);
    };
    env.speechSynthesis.speak(speech);
    env.speechSynthesis.resume?.();
    return true;
  }
  // Speak readback segments one at a time, highlighting each segment's atom/bond
  // as it begins. TTS-only: skipped when muted. Cancelled by stopSpeech (which
  // bumps readbackToken and clears the highlight).
  function speakReadback(segments) {
    if (disposed || muted || !env.speechSynthesis || !env.SpeechSynthesisUtterance) return;
    stopSpeech();                 // bumps token; start a fresh sequence below
    const token = readbackToken;
    let i = 0;
    const next = () => {
      if (disposed || muted || token !== readbackToken) return;  // cancelled
      if (i >= segments.length) { onHighlight(null); return; }
      const segment = segments[i++];
      const speech = new env.SpeechSynthesisUtterance(', ' + segment.text);
      speech.rate = SPEECH_RATE;
      speech.pitch = 1;
      speech.volume = 1;
      utterance = speech;
      spokenText = normalized(segment.text);
      speech.onstart = () => { if (token === readbackToken) onHighlight(segment.highlight || null); };
      speech.onend = () => { if (token === readbackToken) { utterance = null; next(); } };
      speech.onerror = () => { if (token === readbackToken) { utterance = null; next(); } };
      env.speechSynthesis.speak(speech);
      env.speechSynthesis.resume?.();
    };
    next();
  }
  function showEvent(event) {
    if (disposed) return;
    if (event.discard_following) session.discardFollowing();
    onState(event);
    if (event.message) onMessage(event.message);
    if (event.speech_action === 'stop') { stopSpeech(); return; }
    // A read-back response: its message is the full atom/bond description, which
    // equals the joined readback_segments. Speak it segment-by-segment with
    // synced highlighting instead of one flat utterance.
    const segments = event.readback_segments;
    const isReadback = Array.isArray(segments) && segments.length > 1 &&
      event.message === segments.map(s => s.text).join(' ');
    if (isReadback) { speakReadback(segments); return; }
    if (event.message) speak(event.message);
  }
  async function submit(text) {
    // Already accepted work finishes even when the mic is paused or stopped.
    const response = await env.fetch(`${api}/utterance`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error('Command service unavailable');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary;
      while ((boundary = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 1);
        if (line) showEvent(JSON.parse(line));
      }
      if (done) break;
    }
    if (buffer.trim()) showEvent(JSON.parse(buffer));
  }
  function disableMic() {
    capture = false;
    if (restartTimer !== null) env.clearTimeout(restartTimer);
    restartTimer = null;
    const previous = current;
    current = null;
    try { previous?.abort(); } catch { /* Recognition already ended. */ }
    onListening(false);
  }
  const session = createSession({
    submit, stopSpeech,
    status: onStatus,
    changed: mode => { onMode(mode); if (mode === 'off') disableMic(); },
  });
  function receive(text) {
    // Fix common chemistry mishearings before showing or submitting. Control
    // words (stop/start/pause/undo/skip) are not in the map, so they pass through.
    const corrected = correctChemistry(text);
    onHeard(corrected);
    // Spoken mute/unmute control the speech output without reaching the backend.
    const control = corrected.toLowerCase().trim().replace(/[.!?,]+$/g, '');
    if (control === 'mute') {
      setMuted(true);
      onStatus('Muted.');
      onMessage('Muted. Spoken feedback is off.');
      return;
    }
    if (control === 'unmute') {
      setMuted(false);
      onStatus('Unmuted.');
      onMessage('Unmuted. Spoken feedback is on.');
      speak('Spoken feedback is on.');
      return;
    }
    session.receive(corrected);
  }
  function listen() {
    if (disposed || !capture) return;
    try {
      const recognition = new Recognition();
      current = recognition;
      recognition.lang = 'en-US';
      recognition.continuous = true;
      recognition.interimResults = true;
      // Bias recognition toward chemistry terms where supported. Never let a
      // hint failure prevent recognition.
      try {
        if (usePhraseHints && 'phrases' in recognition && env.SpeechRecognitionPhrase) {
          recognition.phrases = VOCABULARY.map(
            phrase => new env.SpeechRecognitionPhrase(phrase, 3),
          );
        }
      } catch { /* Unsupported hints: use ordinary recognition. */ }
      recognition.onresult = event => {
        if (current !== recognition || !capture) return;
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const text = result[0].transcript.trim();
          // Discard unfinished speech when Stop is heard, without submitting it.
          if (/\bstop\s*[.!?,]*$/i.test(text)) { receive('stop'); return; }
          if (!result.isFinal || !text) continue;
          if (utterance && normalized(text) === spokenText) continue;
          stopSpeech();
          receive(text);
          if (!capture) return;
        }
      };
      recognition.onerror = event => {
        if (current !== recognition || event.error === 'no-speech') return;
        // The browser rejected vocabulary hints: disable them and restart
        // without killing the microphone.
        if (event.error === 'phrases-not-supported') {
          usePhraseHints = false;
          return;
        }
        session.stopped();
        onStatus(`Microphone stopped (${event.error}). Enable it again or use typed input.`);
      };
      recognition.onend = () => {
        if (current !== recognition || !capture) return;
        current = null;
        restartTimer = env.setTimeout(() => {
          restartTimer = null;
          if (capture && !current) listen();
        }, 150);
      };
      recognition.start();
    } catch {
      session.stopped();
      onStatus('Could not start the microphone. Use typed input.');
    }
  }
  const welcome = startupInstructions({
    speak,
    listen: (type, handler) => env.document.addEventListener(type, handler),
    unlisten: (type, handler) => env.document.removeEventListener(type, handler),
    hint: onStatus,
  });
  return {
    supported: Boolean(Recognition),
    enable() {
      if (disposed || capture) return;
      welcome.dismiss();
      if (!Recognition) { onStatus('Speech recognition unavailable. Use typed input.'); return; }
      stopSpeech();
      warmUpSpeech();
      capture = true;
      session.enabled();
      onListening(true);
      listen();
    },
    stop() { welcome.dismiss(); session.receive('stop'); },
    type(text) {
      if (disposed || !text.trim()) return;
      welcome.dismiss();
      stopSpeech();
      if (session.mode() === 'off' && !['stop', 'pause'].includes(text.toLowerCase().trim())) {
        session.enabled(); session.receive('start');
      }
      receive(text);
    },
    replay() {
      if (capture) session.receive('stop');
      welcome.replay();
    },
    mute(value) {
      setMuted(value);
    },
    dispose() { disposed = true; welcome.dismiss(); disableMic(); stopSpeech(); },
    settled: session.settled,
  };
}
