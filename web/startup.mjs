export const STARTUP_MESSAGE = 'Welcome to Voice to Molecule. To begin, activate the Enable microphone button and allow microphone access if asked. Then say Start. Say a command such as add carbon. Say Pause to pause commands, Start to resume, Undo to reverse your last command, or Stop to turn the microphone off. You can also type requests in the text box.';

// Browsers may reject page-load speech; retry only after a real interaction.
export function startupInstructions({ speak, listen, unlisten, hint }) {
  let pending = true;
  let attached = false;
  function attach() {
    if (attached) return;
    listen('pointerdown', interact);
    listen('keydown', interact);
    attached = true;
  }
  function detach() {
    if (!attached) return;
    unlisten('pointerdown', interact);
    unlisten('keydown', interact);
    attached = false;
  }
  function dismiss() { pending = false; detach(); }
  function play() {
    pending = false;
    const available = speak(STARTUP_MESSAGE, {
      onStart: dismiss,
      onError: error => {
        if (error.error !== 'not-allowed') return;
        pending = true;
        attach();
        hint('To hear startup instructions, press a key or activate Hear startup instructions.');
      },
    });
    if (available === false) {
      dismiss();
      hint('Spoken instructions are unavailable. Startup instructions are displayed above.');
    }
  }
  function interact(event) {
    if (!pending || event.repeat) return;
    // These controls cancel speech or start recording, so do not replay here.
    if (['enable', 'stop', 'spoken', 'text', 'welcome'].includes(event.target?.id)) return;
    play();
  }
  attach();
  play();
  return { replay: play, dismiss };
}
