"""All speech processes are mocked: this suite never produces sound."""

import subprocess
from unittest.mock import Mock

import pytest

import speech


@pytest.fixture(autouse=True)
def reset_speech(monkeypatch):
    monkeypatch.setattr(speech, "PLATFORM", "darwin")
    monkeypatch.setattr(speech, "RATE", 180)
    monkeypatch.setattr(speech, "QUIET", False)
    monkeypatch.setattr(speech, "_process", None)
    monkeypatch.setattr(speech, "_unavailable", False)
    popen = Mock()
    popen.return_value.poll.return_value = None
    monkeypatch.setattr(speech.subprocess, "Popen", popen)
    return popen


def test_arguments_and_nonblocking_start(reset_speech):
    speech.speak("Hello there.")
    reset_speech.assert_called_once_with(
        ["say", "-r", "180", "--", "Hello there."],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    reset_speech.return_value.wait.assert_not_called()
    assert speech._process is reset_speech.return_value


def test_windows_command(monkeypatch, reset_speech):
    monkeypatch.setattr(speech, "PLATFORM", "win32")
    speech.speak("Hello there.")
    command = reset_speech.call_args.args[0]
    assert command[:3] == ["powershell", "-NoProfile", "-Command"]
    assert "System.Speech" in command[3]
    assert "$s.Speak('Hello there.')" in command[3]
    assert "$s.Rate = -5;" in command[3]
    reset_speech.return_value.wait.assert_not_called()


def test_windows_quotes_are_data(monkeypatch, reset_speech):
    monkeypatch.setattr(speech, "PLATFORM", "win32")
    speech.speak("It's carbon'; oxygen")
    assert "$s.Speak('It''s carbon''; oxygen')" in reset_speech.call_args.args[0][3]
    assert "shell" not in reset_speech.call_args.kwargs


def test_linux_command(monkeypatch, reset_speech):
    monkeypatch.setattr(speech, "PLATFORM", "linux")
    speech.speak("Hello there.")
    assert reset_speech.call_args.args[0] == [
        "spd-say", "--wait", "-r", "-47", "--", "Hello there.",
    ]
    reset_speech.return_value.wait.assert_not_called()


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_missing_engine_on_each_platform(platform, monkeypatch, reset_speech, capsys):
    monkeypatch.setattr(speech, "PLATFORM", platform)
    reset_speech.side_effect = FileNotFoundError()
    speech.speak("One")
    speech.speak("Two")
    reset_speech.assert_called_once()
    assert speech._unavailable is True
    assert capsys.readouterr().out.count("Warning:") == 1


def test_quiet_stops_active_speech_and_prevents_calls(reset_speech):
    speech.speak("First")
    process = reset_speech.return_value
    speech.set_quiet(True)
    process.terminate.assert_called_once()
    reset_speech.reset_mock()
    speech.speak("Silent")
    reset_speech.assert_not_called()
    speech.set_quiet(False)
    speech.speak("Enabled")
    reset_speech.assert_called_once()


def test_second_speech_stops_first_before_starting(reset_speech):
    first, second = Mock(), Mock()
    first.poll.return_value = None
    reset_speech.side_effect = [first, second]
    speech.speak("First")

    def start_second(*args, **kwargs):
        first.terminate.assert_called_once()
        first.wait.assert_called_once_with(timeout=0.2)
        return second

    reset_speech.side_effect = start_second
    speech.speak("Second")
    assert speech._process is second


@pytest.mark.parametrize("requested, expected", [(0, 100), (100, 100), (220, 220), (400, 400), (900, 400)])
def test_rate_is_clamped(requested, expected, reset_speech):
    assert speech.set_rate(requested) == expected
    speech.speak("Rate")
    assert reset_speech.call_args.args[0][2] == str(expected)


def test_cleaning_and_argument_safety(reset_speech):
    speech.speak("--hello [carbon]=#(oxygen) {test} $HOME `echo` ;")
    assert reset_speech.call_args.args[0] == [
        "say", "-r", "180", "--", "--hello carbon oxygen test HOME echo ;",
    ]
    assert "shell" not in reset_speech.call_args.kwargs


def test_empty_cleaned_text_does_not_start_process(reset_speech):
    speech.speak("[=#]")
    reset_speech.assert_not_called()


@pytest.mark.parametrize("error", [FileNotFoundError(), PermissionError()])
def test_unavailable_warns_once_and_keeps_running(error, reset_speech, capsys):
    reset_speech.side_effect = error
    speech.speak("One")
    speech.speak("Two")
    reset_speech.assert_called_once()
    assert capsys.readouterr().out.count("Warning:") == 1


def test_stop_finished_process(reset_speech):
    speech.speak("Done")
    process = reset_speech.return_value
    process.poll.return_value = 0
    speech.stop_speaking()
    process.terminate.assert_not_called()
    process.wait.assert_called_once()
    assert speech._process is None
    speech.stop_speaking()


def test_stop_kills_process_if_termination_times_out(reset_speech):
    speech.speak("Long")
    process = reset_speech.return_value
    process.wait.side_effect = [subprocess.TimeoutExpired("say", 0.2), 0]
    speech.stop_speaking()
    process.kill.assert_called_once()
    assert speech._process is None


def test_stop_tolerates_process_exit_race(reset_speech):
    speech.speak("Finishing")
    reset_speech.return_value.terminate.side_effect = ProcessLookupError()
    speech.stop_speaking()
    assert speech._process is None
