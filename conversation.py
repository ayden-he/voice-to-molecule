"""Ordered execution and clarification barriers, independent of microphone/AI."""

from command_engine import CommandEngine
from interpreter import InterpretationError, validate_plan
from parser import parse


class Conversation:
    def __init__(self, interpret, engine=None):
        self.engine = engine or CommandEngine()
        self.interpret = interpret
        self.pending = []
        self.message = "Enable your microphone to begin."
        self._speech_action = None

    @property
    def builder(self):
        return self.engine.builder

    @property
    def version(self):
        return self.engine.version

    def state(self):
        return dict(self.engine.snapshot(), message=self.message,
                    version=self.version, queued=[],
                    clarification=self.pending[0]["question"] if self.pending else "")

    def image(self):
        return self.engine.svg() or ('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
                                    '<text x="30" y="60" font-size="28">Your molecule is empty.</text></svg>')

    def execute(self, text):
        result = self.engine.run_command(text)
        self._speech_action = result.get("speech_action")
        return result["ok"], result["message"]

    def direct_command(self, text):
        """Canonical /command requests share the voice engine and undo history."""
        version = self.version
        result = self.engine.run_command(text)
        self.message = result["message"]
        if self.version != version and self.pending:
            for step in self.pending:
                step["command"] = ""
                step["question"] = "The molecule changed. How should I continue this instruction?"
            self.message += " Pending voice instructions remain held for clarification."
        return dict(result, **{key: value for key, value in self.state().items()})

    def clarification_message(self, question):
        return question + " Later instructions were discarded. Please repeat any you still want after clarifying."

    def accept(self, text, emit=lambda event: None):
        """Caller serializes requests. Every completed action emits its own state."""
        events = []
        def report(ok, message, discard_following=False):
            self.message = message
            event = dict(self.state(), ok=ok, discard_following=discard_following)
            if self._speech_action:
                event["speech_action"] = self._speech_action
                self._speech_action = None
            events.append(event)
            emit(event)
        if text.strip().lower().rstrip('.!?') == "undo":
            ok, message = self.execute("undo")
            # Context has changed: re-interpret retained steps after clarification.
            if ok:
                for step in self.pending:
                    step["command"] = ""
                    step["question"] = "How should I continue after undo?"
            report(ok, message + (" Pending instructions remain held for clarification." if self.pending else ""))
            return events
        # A recognized standalone read-only name request needs no AI confirmation.
        # Keep an unrelated outstanding clarification intact rather than treating
        # the user's question as an answer to it.
        if parse(text) == {"action": "name"}:
            ok, message = self.execute("name")
            if self.pending:
                message += " " + self.pending[0]["question"]
            report(ok, message)
            return events
        if self.pending:
            first = self.pending[0]
            request = "Unresolved request: {}\nQuestion: {}\nUser clarification: {}".format(
                first["source"], first["question"], text)
        else:
            request = text
        try:
            steps = self.interpret(request, self.state())
            # Injected/mock interpreters must meet the same contract.
            validate_plan({"steps": steps})
        except (InterpretationError, ValueError) as exc:
            # No trustworthy boundary exists, so do not retain the whole request.
            self.pending = []
            report(False, str(exc) + " Please repeat the instruction you want to try.", True)
            return events
        # A clarification can replace only the confusing statement; its former
        # tail has already been forgotten and can never reappear here.
        self.pending = steps
        while self.pending:
            step = self.pending[0]
            if not step["command"]:
                self.pending = [step]
                report(False, self.clarification_message(step["question"]), True)
                break
            ok, message = self.execute(step["command"])
            if not ok:
                step["command"] = ""
                step["question"] = message + " How would you like to change this instruction?"
                self.pending = [step]
                report(False, self.clarification_message(step["question"]), True)
                break
            self.pending.pop(0)
            report(True, message)
        return events
