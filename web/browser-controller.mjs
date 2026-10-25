import { createSession } from './session.mjs';
import { startupInstructions } from './startup.mjs';

// Shared voice behavior for the React frontend; all chemistry stays in Python.
export function createBrowserController({
  env = globalThis, api = '/api',
  onState = () => {}, onHeard = () => {}, onMessage = () => {},
  onStatus = () => {}, onListening = () => {}, onMode = () => {},
}) {
  const Recognition = env.SpeechRecognition || env.webkitSpeechRecognition;
  let current = null;
  let capture = false;
  let disposed = false;
  let muted = false;
  let utterance = null;
  let spokenText = '';
  let restartTimer = null;
  const normalized = text => text.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
  function stopSpeech() {
    utterance = null;
    env.speechSynthesis?.cancel();
  }
  function speak(text, { onStart, onError } = {}) {
    if (disposed || muted || !env.speechSynthesis || !env.SpeechSynthesisUtterance) return false;
    stopSpeech();
    const speech = new env.SpeechSynthesisUtterance(text);
    utterance = speech;
    spokenText = normalized(text);
    speech.onstart = () => { if (utterance === speech) onStart?.(); };
    speech.onend = () => { if (utterance === speech) utterance = null; };
    speech.onerror = event => {
      if (utterance !== speech) return;
      utterance = null;
      onError?.(event);
    };
    env.speechSynthesis.speak(speech);
    return true;
  }
  function showEvent(event) {
    if (disposed) return;
    onState(event);
    if (event.message) onMessage(event.message);
    if (event.speech_action === 'stop') stopSpeech();
    else if (event.message) speak(event.message);
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
    onHeard(text);
    session.receive(text);
  }
  function listen() {
    if (disposed || !capture) return;
    try {
      const recognition = new Recognition();
      current = recognition;
      recognition.lang = 'en-US';
      recognition.continuous = true;
      recognition.interimResults = true;
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
      muted = value;
      if (muted) { welcome.dismiss(); stopSpeech(); }
    },
    dispose() { disposed = true; welcome.dismiss(); disableMic(); stopSpeech(); },
    settled: session.settled,
  };
}
