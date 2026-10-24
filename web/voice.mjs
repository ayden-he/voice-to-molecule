// Speech supplies text only. Parsing and chemistry belong to POST /command.
export const VOCABULARY = [
  'add carbon', 'add oxygen', 'single bond', 'double bond', 'triple bond',
  'to atom', 'go to atom', 'methyl', 'ethyl', 'hydroxyl', 'methoxy',
  'aldehyde', 'carboxylic acid', 'cyclopropane', 'cyclobutane',
  'cyclopentane', 'cyclohexane', 'benzene', 'close the ring', 'undo',
  'start over', 'read it back', 'summary', 'where am I', 'help',
];

export function createVoice({
  env = globalThis, onText, onStatus = () => {}, onBusy = () => {},
  stopSpeaking = () => env.speechSynthesis?.cancel(),
}) {
  const Recognition = env.SpeechRecognition || env.webkitSpeechRecognition;
  let active = null;
  let usePhraseHints = true;
  function start({ test = false } = {}) {
    if (active) return false;
    if (!Recognition) {
      onStatus('Speech recognition is unavailable. Type your command instead.');
      return false;
    }
    let recognition;
    let delivered = false;
    let failed = false;
    try {
      stopSpeaking();
      recognition = new Recognition();
      recognition.lang = 'en-US';
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      // Contextual biasing is optional and must never prevent recognition.
      try {
        if (usePhraseHints && 'phrases' in recognition && env.SpeechRecognitionPhrase) {
          recognition.phrases = VOCABULARY.map(
            text => new env.SpeechRecognitionPhrase(text, 3),
          );
        }
      } catch { /* Unsupported hints: use ordinary recognition. */ }
      active = recognition;
      recognition.onresult = event => {
        if (active !== recognition || delivered || failed) return;
        for (let i = event.resultIndex || 0; i < event.results.length; i++) {
          const result = event.results[i];
          if (!result.isFinal) continue;
          const text = (result[0]?.transcript || '').trim();
          if (!text) continue;
          delivered = true;
          onStatus(`Heard: ${text}`);
          onText(text, { test });
          break;
        }
      };
      recognition.onerror = event => {
        if (active !== recognition) return;
        failed = true;
        if (event.error === 'phrases-not-supported') usePhraseHints = false;
        const messages = {
          'not-allowed': 'Microphone permission was denied.',
          'service-not-allowed': 'Speech recognition permission was denied.',
          'audio-capture': 'No microphone is available.',
          'network': 'The speech service could not be reached.',
          'no-speech': 'No speech was recognized.',
          'aborted': 'Listening cancelled.',
          'phrases-not-supported': 'The speech service rejected vocabulary hints. Hints are now disabled; click the microphone button again.',
          'language-not-supported': 'The speech service does not support US English. Check your browser speech language settings.',
          'bad-grammar': 'The speech service rejected its recognition configuration.',
        };
        const code = event.error || 'unknown';
        onStatus(`${messages[code] || 'Speech recognition failed.'} (Error: ${code}) Type your command or try again.`);
      };
      recognition.onend = () => {
        if (active !== recognition) return;
        active = null;
        onBusy(false);
        if (!delivered && !failed) onStatus('No speech was recognized. Type your command or try again.');
      };
      onBusy(true);
      onStatus(test ? 'Microphone test: say a short command.' : 'Listening. Say one command.');
      recognition.start();
      return true;
    } catch (error) {
      active = null;
      onBusy(false);
      onStatus(`Could not start the microphone (${error?.name || 'unknown error'}). Type your command instead.`);
      return false;
    }
  }
  function cancel() {
    if (!active) return;
    const recognition = active;
    active = null;
    try { recognition.abort(); } catch { /* Already stopped. */ }
    onBusy(false);
    onStatus('Listening cancelled.');
  }
  return { supported: Boolean(Recognition), start, cancel };
}

export async function postCommand(text, fetcher = globalThis.fetch) {
  const response = await fetcher('/command', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error('Command service unavailable');
  const result = await response.json();
  if (typeof result.message !== 'string') throw new Error('Invalid command response');
  return result;
}
