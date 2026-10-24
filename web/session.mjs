// Local controls never wait for an AI call. Only finalized speech enters the queue.
export function createSession({ submit, stopSpeech, status, changed = () => {} }) {
  let mode = 'off';
  let tail = Promise.resolve();
  function setMode(value) { mode = value; changed(mode); }
  function enabled() { setMode('paused'); status('Microphone enabled. Say Start to begin.'); }
  function stopped() { setMode('off'); status('Microphone off. Use Enable microphone to restart.'); }
  function receive(text) {
    const control = text.toLowerCase().trim().replace(/[.!?,]+$/g, '');
    if (control === 'stop') { stopSpeech(); stopped(); return 'stop'; }
    if (mode === 'off') return;
    if (control === 'start') { setMode('active'); status('Accepting commands.'); return; }
    if (control === 'pause') { stopSpeech(); setMode('paused'); status('Paused. Say Start to resume.'); return; }
    if (mode !== 'active' || !text.trim()) return;
    if (control === 'undo') stopSpeech();
    // Preserve spoken order, including undo, while earlier AI requests finish.
    tail = tail.then(() => submit(text)).catch(() => {
      setMode('paused');
      status('Connection lost. Paused; check the molecule before retrying.');
    });
  }
  return { enabled, stopped, receive, mode: () => mode, settled: () => tail };
}
