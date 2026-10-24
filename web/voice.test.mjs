import { createVoice, postCommand } from './voice.mjs';

export async function runTests(create = createVoice, post = postCommand) {
  let checks = 0;
  function assert(value, message) {
    if (!value) throw new Error(message);
    checks++;
  }
  let instance;
  let stopped = false;
  const texts = [], statuses = [], busy = [];
  class Recognition {
    constructor() { instance = this; }
    start() { assert(stopped, 'TTS stops before microphone starts'); }
    abort() { this.onend(); }
  }
  const voice = create({
    env: { webkitSpeechRecognition: Recognition },
    stopSpeaking: () => { stopped = true; },
    onText: (text, options) => texts.push({ text, ...options }),
    onStatus: text => statuses.push(text), onBusy: value => busy.push(value),
  });
  const result = (text, final = true) => ({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal: final })] });
  assert(voice.start(), 'prefixed recognition works');
  assert(!voice.start(), 'overlapping capture rejected');
  instance.onresult(result('add carbon', false));
  instance.onresult(result('   '));
  assert(texts.length === 0, 'interim and empty results ignored');
  instance.onresult(result('add oxygen double bond to atom two'));
  instance.onresult(result('add carbon'));
  instance.onend();
  assert(texts.length === 1 && texts[0].text === 'add oxygen double bond to atom two', 'one unchanged final transcript');
  assert(busy.at(-1) === false, 'controls restored');
  voice.start({ test: true });
  instance.onresult(result('add carbon'));
  instance.onend();
  assert(texts[1].test, 'microphone test distinct from commands');
  voice.start();
  const stale = instance;
  voice.cancel();
  stale.onresult(result('undo'));
  assert(texts.length === 2, 'cancelled result cannot execute');
  voice.start();
  instance.onerror({ error: 'not-allowed' });
  instance.onresult(result('undo'));
  instance.onend();
  assert(texts.length === 2 && statuses.at(-1).includes('denied'), 'permission denial falls back without submitting');
  voice.start();
  instance.onend();
  assert(statuses.at(-1).includes('No speech'), 'silence feedback');
  const hintedInstances = [];
  class HintedRecognition extends Recognition {
    constructor() { super(); this.phrases = []; hintedInstances.push(this); }
  }
  const hinted = create({
    env: { SpeechRecognition: HintedRecognition, SpeechRecognitionPhrase: class {
      constructor(phrase, boost) { this.phrase = phrase; this.boost = boost; }
    } },
    onText() {}, onStatus: text => statuses.push(text),
  });
  hinted.start();
  assert(hintedInstances[0].phrases.length > 0, 'vocabulary hints configured');
  hintedInstances[0].onerror({ error: 'phrases-not-supported' });
  hintedInstances[0].onend();
  assert(statuses.at(-1).includes('phrases-not-supported'), 'exact browser error shown');
  hinted.start();
  assert(hintedInstances[1].phrases.length === 0, 'retry skips rejected hints');
  hintedInstances[1].onerror({ error: 'new-browser-error' });
  assert(statuses.at(-1).includes('new-browser-error'), 'unknown errors remain diagnosable');
  hintedInstances[1].onend();
  assert(!create({ env: {}, onText() {} }).start(), 'unsupported browser falls back');
  class Broken { start() { throw new Error('missing mic'); } }
  assert(!create({ env: { SpeechRecognition: Broken }, onText() {} }).start(), 'start failure falls back');
  const response = await post('add carbon', async (url, options) => {
    assert(url === '/command' && JSON.parse(options.body).text === 'add carbon', 'JSON command contract');
    return { ok: true, json: async () => ({ ok: false, message: 'Rejected by backend.' }) };
  });
  assert(response.ok === false, 'backend rejection preserved');
  let rejected = false;
  try { await post('undo', async () => ({ ok: false })); } catch { rejected = true; }
  assert(rejected, 'HTTP failure reported');
  return `${checks} voice checks passed`;
}

console.log(await runTests());
