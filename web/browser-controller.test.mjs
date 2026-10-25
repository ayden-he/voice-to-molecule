import { createBrowserController } from './browser-controller.mjs';

export async function runControllerTests(create = createBrowserController) {
  let checks = 0;
  const assert = (ok, message) => { if (!ok) throw new Error(message); checks++; };
  const requests = [], spoken = [], states = [], statuses = [], modes = [];
  let recognition;
  let cancelled = 0;
  let restarted = 0;
  let release;
  let gate = null;
  const listeners = new Map();
  const timers = new Map();
  let timerId = 0;
  class Recognition {
    constructor() { recognition = this; }
    start() { restarted++; }
    abort() { this.onend?.(); }
  }
  const env = {
    SpeechRecognition: Recognition,
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    speechSynthesis: {
      cancel() { cancelled++; },
      speak(speech) { spoken.push(speech.text); speech.onstart?.(); },
    },
    document: {
      addEventListener: (type, fn) => listeners.set(type, fn),
      removeEventListener: type => listeners.delete(type),
    },
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => {
      const text = JSON.parse(options.body).text;
      requests.push(text);
      assert(url === '/api/utterance', 'React uses the Vite API proxy');
      if (gate) await gate;
      // Include a final record without a trailing newline and a split UTF-8 char.
      const data = new TextEncoder().encode(JSON.stringify({ message: 'Added carbon.', version: 1 }) + '\n' +
        JSON.stringify({ message: 'Résumé ready.', version: 2 }));
      const split = data.indexOf(0xc3) + 1;
      const chunks = [data.slice(0, split), data.slice(split)];
      return { ok: true, body: { getReader: () => ({
        read: async () => chunks.length ? { done: false, value: chunks.shift() } : { done: true },
      }) } };
    },
  };
  const controller = create({ env,
    onState: value => states.push(value), onStatus: value => statuses.push(value),
    onMode: value => modes.push(value),
  });
  assert(spoken[0].includes('Enable microphone'), 'startup guide is spoken');
  controller.enable();
  assert(modes.at(-1) === 'paused', 'enable waits for Start');
  const result = (text, final = true) => recognition.onresult({ resultIndex: 0,
    results: [Object.assign([{ transcript: text }], { isFinal: final })] });
  result('add carbon');
  await controller.settled();
  assert(requests.length === 0, 'paused commands never call AI');
  result('Start');
  result('add carbon', false);
  assert(requests.length === 0, 'interim text never executes');
  result('add carbon');
  await controller.settled();
  assert(requests.join() === 'add carbon', 'Start enables commands');
  assert(states.length === 2 && states[1].version === 2, 'every NDJSON event updates the frontend');
  assert(spoken.at(-1) === 'Résumé ready.', 'UTF-8 feedback uses browser TTS on Windows');
  result('Pause'); result('undo');
  await controller.settled();
  assert(requests.length === 1, 'Undo is disabled while paused');
  result('Start');
  gate = new Promise(resolve => { release = resolve; });
  result('add oxygen');
  const beforeUndo = cancelled;
  result('undo');
  assert(cancelled > beforeUndo, 'Undo interrupts feedback immediately');
  await Promise.resolve();
  assert(requests.at(-1) === 'add oxygen', 'Undo waits behind earlier work');
  result('add carbon then stop', false);
  assert(modes.at(-1) === 'off', 'Stop aborts unfinished speech');
  release(); gate = null;
  await controller.settled();
  assert(requests.join() === 'add carbon,add oxygen,undo', 'Stop preserves accepted work without parsing unfinished speech');
  controller.enable(); result('Start');
  const beforeSkip = requests.length;
  result('skip');
  await controller.settled();
  assert(requests.length === beforeSkip && modes.at(-1) === 'active', 'Skip stops speech without stopping commands');
  const old = recognition;
  old.onend();
  assert(timers.size === 1, 'ordinary recognition end schedules restart');
  controller.stop();
  assert(timers.size === 0, 'Stop prevents automatic mic restart');
  controller.mute(true);
  const speechCount = spoken.length;
  controller.type('carbon');
  await controller.settled();
  assert(spoken.length === speechCount, 'muting preserves text results without TTS');
  controller.mute(false); controller.enable();
  controller.replay();
  assert(modes.at(-1) === 'off' && spoken.at(-1).includes('Enable microphone'), 'replaying startup disables microphone first');
  controller.enable();
  const stale = recognition;
  controller.dispose();
  stale.onend();
  assert(timers.size === 0 && listeners.size === 0, 'unmount releases microphone, speech, and startup listeners');
  assert(restarted >= 2 && statuses.length > 0, 'recognition and status callbacks exercised');
  return `${checks} React voice controller checks passed`;
}

console.log(await runControllerTests());
