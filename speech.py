"""Interruptible platform speech, with a text-only fallback when unavailable."""

import re
import subprocess
import sys
from typing import Optional


RATE = 180
PLATFORM = sys.platform
QUIET = False
_process: Optional[subprocess.Popen] = None
_unavailable = False


def stop_speaking() -> None:
    """Stop and reap the current process, using only short bounded waits."""
    global _process
    process = _process
    _process = None
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=0.2)
    except (OSError, subprocess.TimeoutExpired):
        # A process may finish between poll and terminate. Keep the UI usable.
        pass


def set_quiet(quiet: bool) -> None:
    """Disable speech immediately, or enable it for subsequent calls."""
    global QUIET
    QUIET = bool(quiet)
    if QUIET:
        stop_speaking()


def set_rate(wpm: int) -> int:
    """Clamp the speech rate to 100–400 words per minute and return it."""
    global RATE
    RATE = max(100, min(400, int(wpm)))
    return RATE


def _command(text: str) -> list[str]:
    if PLATFORM == "darwin":
        return ["say", "-r", str(RATE), "--", text]
    if PLATFORM == "win32":
        rate = round((RATE - 100) * 20 / 300 - 10)
        escaped = text.replace("'", "''")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.Rate = {}; $s.Speak('{}')").format(rate, escaped)
        return ["powershell", "-NoProfile", "-Command", script]
    linux_rate = round((RATE - 100) * 200 / 300 - 100)
    return ["spd-say", "--wait", "-r", str(linux_rate), "--", text]


def speak(text: str) -> None:
    """Replace earlier speech without waiting for the new speech to finish."""
    global _process, _unavailable
    stop_speaking()
    if QUIET or _unavailable:
        return
    # Retain words and natural pauses; replace symbols with spaces, not joins.
    cleaned = re.sub(r"[^\w\s.,!?;'’\-]", " ", text)
    cleaned = " ".join(cleaned.replace("_", " ").split())
    if not any(character.isalnum() for character in cleaned):
        return
    try:
        # -- prevents leading dashes in text from being interpreted as options.
        _process = subprocess.Popen(
            _command(cleaned),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        _unavailable = True
        print("Warning: speech is unavailable. Continuing with text only.")
