import { createBrowserController } from './browser-controller.mjs';

export async function runControllerTests(create = createBrowserController) {
  let checks = 0;
  const assert = (ok, message) => { if (!ok) throw new Error(message); checks++; };
  const requests = [], spoken = [], states = [], statuses = [], modes = [], mutes = [];
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
    onMode: value => modes.push(value), onMute: value => mutes.push(value),
  });
  assert(spoken[0].includes('Press space'), 'startup guide is spoken');
  controller.enable();
  assert(modes.at(-1) === 'active', 'enable activates commands without Start');
  const result = (text, final = true) => recognition.onresult({ resultIndex: 0,
    results: [Object.assign([{ transcript: text }], { isFinal: final })] });
  result('add carbon', false);
  assert(requests.length === 0, 'interim text never executes');
  result('add carbon');
  await controller.settled();
  assert(requests.join() === 'add carbon', 'enable accepts commands immediately');
  assert(states.length === 2 && states[1].version === 2, 'every NDJSON event updates the frontend');
  assert(spoken.at(-1).includes('Résumé ready.'), 'UTF-8 feedback uses browser TTS on Windows');
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
  // Spoken "mute"/"unmute" control speech output and sync the UI via onMute.
  result('mute');
  assert(mutes.at(-1) === true, 'spoken mute mutes feedback and syncs the toggle');
  const mutedCount = spoken.length;
  result('add carbon');
  await controller.settled();
  assert(spoken.length === mutedCount, 'spoken mute suppresses TTS for later feedback');
  result('unmute');
  assert(mutes.at(-1) === false, 'spoken unmute restores feedback and syncs the toggle');
  controller.replay();
  assert(modes.at(-1) === 'off' && spoken.at(-1).includes('Press space'), 'replaying startup disables microphone first');
  controller.enable();
  const stale = recognition;
  controller.dispose();
  stale.onend();
  assert(timers.size === 0 && listeners.size === 0, 'unmount releases microphone, speech, and startup listeners');
  assert(restarted >= 2 && statuses.length > 0, 'recognition and status callbacks exercised');
  const posted = [];
  const second = create({ env: { ...env, fetch: async (_url, options) => {
    posted.push(JSON.parse(options.body).text);
    let done = false;
    return { ok: true, body: { getReader: () => ({ read: async () => {
      if (done) return { done: true };
      done = true;
      return { done: false, value: new TextEncoder().encode(
        JSON.stringify({ message: 'Which group? Later instructions were discarded.', discard_following: true }) + '\n') };
    } }) } };
  } } });
  second.type('unclear'); second.type('oxygen');
  await second.settled();
  assert(posted.join() === 'unclear', 'backend discard signal clears waiting React requests');
  second.dispose();

  // Readback: a message equal to the joined segments speaks segment-by-segment
  // and highlights each segment's atom/bond, clearing the highlight at the end.
  const segs = [
    { text: 'The current atom is atom 2, oxygen.', highlight: { atom: 2 } },
    { text: 'Atom 1, carbon, with 3 hydrogens, bonded', highlight: { atom: 1 } },
    { text: 'to atom 2 by a single bond.', highlight: { bond: [1, 2] } },
    { text: 'Atom 2, oxygen, with 1 hydrogen.', highlight: { atom: 2 } },
  ];
  const readbackEnv = { ...env, speechSynthesis: {
    cancel() {}, resume() {},
    // Fire start then end synchronously so the segment chain advances in the test.
    speak(speech) { speech.onstart?.(); speech.onend?.(); },
  } };
  const fourthHighlights = [];
  const fourth = create({ env: { ...readbackEnv, fetch: async () => {
    let done = false;
    return { ok: true, body: { getReader: () => ({ read: async () => {
      if (done) return { done: true };
      done = true;
      return { done: false, value: new TextEncoder().encode(
        JSON.stringify({ message: segs.map(s => s.text).join(' '), readback_segments: segs }) + '\n') };
    } }) } };
  } }, onHighlight: value => fourthHighlights.push(value) });
  fourth.enable();
  recognition.onresult({ resultIndex: 0,
    results: [Object.assign([{ transcript: 'read it back' }], { isFinal: true })] });
  await fourth.settled();
  const nonNull = fourthHighlights.filter(h => h !== null);
  assert(nonNull.map(h => JSON.stringify(h)).join('|') ===
    segs.map(s => JSON.stringify(s.highlight)).join('|'),
    'readback highlights each segment atom/bond in order');
  assert(fourthHighlights.at(-1) === null, 'readback clears the highlight when finished');
  fourth.dispose();
  return `${checks} React voice controller checks passed`;
}

console.log(await runControllerTests());
