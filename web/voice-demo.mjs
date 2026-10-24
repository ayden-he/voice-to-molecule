import { createVoice } from './voice.mjs';

const get = id => document.getElementById(id);
let pending = false;
let listening = false;
let queued = null;
function updateControls() {
  get('listen').disabled = get('test').disabled = pending || listening;
  get('send').disabled = pending || listening;
  get('cancel').disabled = !listening;
}
function feedback(message) {
  get('feedback').textContent = message;
  if (get('spoken').checked && window.speechSynthesis && !listening) {
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
  }
}
// Fake POST /command: deliberately no molecule state or chemistry decisions.
async function fakeCommand(text) {
  return { ok: true, message: `Demo received: ${text}. No molecule was changed.` };
}
async function submit(text) {
  if (pending || !text.trim()) return;
  pending = true;
  updateControls();
  try {
    // Frontend integration: replace fakeCommand with imported postCommand.
    const result = await fakeCommand(text);
    feedback(result.message);
  } catch {
    feedback('Could not send the command. It remains in the text box. Try again when connected.');
  } finally {
    pending = false;
    updateControls();
  }
}
const voice = createVoice({
  onStatus: message => { get('status').textContent = message; },
  onBusy: busy => {
    listening = busy;
    updateControls();
    if (!busy && queued !== null) {
      const text = queued;
      queued = null;
      void submit(text);
    }
  },
  onText: (text, { test }) => {
    get('command').value = text;
    if (test) get('feedback').textContent = `Microphone test heard: ${text}. Nothing was sent.`;
    else {
      // Wait for recognition to end before speaking the server's feedback.
      queued = text;
    }
  },
});
get('listen').onclick = () => voice.start();
get('test').onclick = () => voice.start({ test: true });
get('cancel').onclick = () => { queued = null; voice.cancel(); };
get('form').onsubmit = event => {
  event.preventDefault();
  if (!listening) void submit(get('command').value.trim());
};
get('spoken').onchange = () => { if (!get('spoken').checked) window.speechSynthesis?.cancel(); };
window.addEventListener('pagehide', () => { queued = null; voice.cancel(); window.speechSynthesis?.cancel(); });
