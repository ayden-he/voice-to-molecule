import { createSession } from './session.mjs';

export async function runSessionTests(create = createSession) {
  const submitted = [];
  let interrupted = 0;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const assert = (ok, text) => { if (!ok) throw new Error(text); };
  const session = create({
    submit: async text => { submitted.push(text); if (text === 'carbon') await gate; },
    stopSpeech: () => { interrupted++; }, status() {},
  });
  session.enabled();
  assert(session.mode() === 'active', 'enabling the mic activates commands without Start');
  session.receive('carbon');
  session.receive('undo');
  await Promise.resolve();
  assert(submitted.join() === 'carbon', 'undo waits behind earlier interpretation');
  assert(interrupted === 1, 'undo interrupts speech immediately');
  session.receive('Pause');
  session.receive('oxygen');
  session.receive('undo');
  session.receive('Stop');
  assert(session.mode() === 'off', 'stop disables microphone state');
  session.receive('start');
  assert(session.mode() === 'off', 'voice cannot restart disabled microphone');
  release();
  await session.settled();
  assert(submitted.join() === 'carbon,undo', 'stop preserves accepted work; pause rejects new work');
  session.enabled(); session.receive('start');
  const beforeSkip = interrupted;
  session.receive('skip');
  await session.settled();
  assert(interrupted === beforeSkip + 1 && session.mode() === 'active', 'skip stops feedback without disabling commands');
  assert(submitted.join() === 'carbon,undo', 'skip uses no AI quota');
  const afterAmbiguity = [];
  const second = create({
    submit: async text => {
      afterAmbiguity.push(text);
      if (text === 'unclear') second.discardFollowing();
    }, stopSpeech() {}, status() {},
  });
  second.enabled(); second.receive('start');
  second.receive('unclear'); second.receive('add oxygen'); second.receive('add carbon');
  await second.settled();
  assert(afterAmbiguity.join() === 'unclear', 'ambiguity discards waiting speech instead of treating it as clarification');
  second.receive('methyl');
  await second.settled();
  assert(afterAmbiguity.join() === 'unclear,methyl', 'fresh clarification still works after discard');
  return '11 session checks passed';
}

console.log(await runSessionTests());
