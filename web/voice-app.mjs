import { createSession } from './session.mjs';
import { startupInstructions } from './startup.mjs';

const get = id => document.getElementById(id);
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let capture = false;
let speaking = false;
let lastVersion = -1;
let spokenText = '';
function stopSpeech() { window.speechSynthesis?.cancel(); speaking = false; }
function say(text, { onStart, onError } = {}) {
  get('feedback').textContent = text;
  if (!get('spoken').checked || !window.speechSynthesis) return false;
  stopSpeech();
  const speech = new SpeechSynthesisUtterance(text);
  spokenText = text.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
  speaking = true;
  speech.onstart = () => { onStart?.(); };
  speech.onend = () => { speaking = false; };
  speech.onerror = event => { speaking = false; onError?.(event); };
  window.speechSynthesis.speak(speech);
  return true;
}
function render(state) {
  get('queued').textContent = state.queued.length ? `Queued: ${state.queued.join('; ')}` : '';
  if (state.version !== lastVersion) {
    lastVersion = state.version;
    get('image').src = state.image_url;
    get('image').alt = state.detail;
  }
}
async function submit(text) {
  const response = await fetch('/utterance', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error('Request failed');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary;
    while ((boundary = buffer.indexOf('\n')) !== -1) {
      const event = JSON.parse(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 1);
      render(event);
      if (event.speech_action === 'stop') stopSpeech();
      else say(event.message);
    }
    if (done) break;
  }
}
function disableMic() {
  capture = false;
  const previous = recognition;
  recognition = null;
  previous?.abort();
  get('enable').disabled = false;
  get('stop').disabled = true;
}
const session = createSession({
  submit, stopSpeech,
  status: message => { get('status').textContent = message; },
  changed: mode => { if (mode === 'off') disableMic(); },
});
function hear(text) {
  get('heard').textContent = `Heard: ${text}`;
  session.receive(text);
}
function listen() {
  const current = new Recognition();
  recognition = current;
  current.lang = 'en-US';
  current.continuous = true;
  current.interimResults = true;
  current.onresult = event => {
    if (recognition !== current || !capture) return;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const text = result[0].transcript.trim();
      const control = text.toLowerCase().replace(/[.!?,]+$/g, '');
      // Stop aborts even an unfinished utterance; no partial text is submitted.
      if (/\bstop\s*[.!?,]*$/i.test(text)) { session.receive('stop'); return; }
      if (!result.isFinal) { get('heard').textContent = `Hearing: ${text}`; continue; }
      // Do not discard a user's next command just because feedback is speaking.
      // Headphones prevent acoustic feedback; exact echoes are also ignored.
      if (speaking && text.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim() === spokenText) continue;
      stopSpeech();
      hear(text);
      if (!capture) return;
    }
  };
  current.onerror = event => {
    if (recognition !== current) return;
    if (event.error === 'no-speech') return;
    session.stopped();
    get('status').textContent = `Microphone stopped (${event.error}). Use typed input or enable it again.`;
  };
  current.onend = () => {
    if (recognition === current && capture) {
      recognition = null;
      setTimeout(() => { if (capture && !recognition) listen(); }, 150);
    }
  };
  try { current.start(); }
  catch { session.stopped(); get('status').textContent = 'Could not start speech recognition. Use typed input.'; }
}
get('enable').onclick = () => {
  welcome.dismiss();
  if (!Recognition) { get('status').textContent = 'Speech recognition unavailable. Use typed input.'; return; }
  stopSpeech();
  capture = true;
  get('enable').disabled = true;
  get('stop').disabled = false;
  session.enabled();
  listen();
};
get('stop').onclick = () => session.receive('stop');
get('form').onsubmit = event => {
  event.preventDefault();
  welcome.dismiss();
  stopSpeech();
  const text = get('text').value.trim();
  // Typed requests work without microphone activation, with identical ordering.
  if (session.mode() === 'off' && !['stop', 'pause'].includes(text.toLowerCase())) {
    session.enabled(); session.receive('start');
  }
  hear(text);
  get('text').value = '';
};
get('spoken').onchange = () => { if (!get('spoken').checked) { welcome.dismiss(); stopSpeech(); } };
window.addEventListener('pagehide', () => { welcome.dismiss(); disableMic(); stopSpeech(); });
fetch('/state').then(response => response.json()).then(render).catch(() => {
  get('status').textContent = 'Could not connect to the local server.';
});
const welcome = startupInstructions({
  speak: say,
  listen: (type, handler) => document.addEventListener(type, handler),
  unlisten: (type, handler) => document.removeEventListener(type, handler),
  hint: message => { get('startup-hint').textContent = message; },
});
get('welcome').onclick = () => {
  // Replaying the instructions turns the mic off to avoid hearing the guide.
  if (capture) session.receive('stop');
  welcome.replay();
};
