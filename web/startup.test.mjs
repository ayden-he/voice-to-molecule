import { startupInstructions, STARTUP_MESSAGE } from './startup.mjs';

export function runStartupTests(install = startupInstructions, message = STARTUP_MESSAGE) {
  let checks = 0;
  const assert = (ok, description) => { if (!ok) throw new Error(description); checks++; };
  const listeners = new Map();
  const spoken = [];
  let callbacks;
  let hint = '';
  const options = {
    speak: (text, events) => { spoken.push(text); callbacks = events; return true; },
    listen: (type, handler) => listeners.set(type, handler),
    unlisten: type => listeners.delete(type),
    hint: text => { hint = text; },
  };
  const startup = install(options);
  assert(spoken[0] === message && spoken.length === 1, 'welcome attempted on page open');
  assert(message.includes('Enable microphone') && message.includes('say Start'), 'guide explains startup');
  callbacks.onError({ error: 'not-allowed' });
  assert(hint.includes('press a key'), 'autoplay failure offers an accessible fallback');
  listeners.get('keydown')({ target: { id: 'enable' } });
  assert(spoken.length === 1, 'mic activation does not trigger another welcome');
  listeners.get('keydown')({ target: {}, repeat: true });
  assert(spoken.length === 1, 'held keys do not replay');
  listeners.get('keydown')({ target: {}, key: 'Tab' });
  assert(spoken.length === 2, 'blocked speech retries on keyboard interaction');
  callbacks.onStart();
  assert(listeners.size === 0, 'successful speech removes retry listeners');
  startup.replay();
  assert(spoken.length === 3, 'explicit replay remains available');
  callbacks.onError({ error: 'not-allowed' });
  startup.dismiss();
  assert(listeners.size === 0, 'mic start or mute removes retries');
  install({ ...options, speak: () => false });
  assert(hint.includes('unavailable') && listeners.size === 0, 'missing TTS retains written instructions');
  return `${checks} startup checks passed`;
}

console.log(runStartupTests());
