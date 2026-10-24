"""Ordered execution and clarification barriers, independent of microphone/AI."""

from command_engine import CommandEngine
from interpreter import InterpretationError, validate_plan


class Conversation:
    def __init__(self, interpret, engine=None):
        self.engine = engine or CommandEngine()
        self.interpret = interpret
        self.pending = []
        self.message = "Enable your microphone, then say Start."
        self._speech_action = None

    @property
    def builder(self):
        return self.engine.builder

    @property
    def version(self):
        return self.engine.version

    def state(self):
        return dict(self.engine.snapshot(), message=self.message,
                    version=self.version, queued=[step["source"] for step in self.pending])

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

    def queued_message(self):
        if not self.pending:
            return ""
        later = [step["source"] for step in self.pending[1:]]
        return " Later instructions are queued and will run after clarification: {}.".format("; ".join(later)) if later else ""

    def accept(self, text, emit=lambda event: None):
        """Caller serializes requests. Every completed action emits its own state."""
        events = []
        def report(ok, message):
            self.message = message
            event = dict(self.state(), ok=ok)
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
            if not self.pending:
                self.pending = [{"source": text, "command": "", "question": "Please clarify or repeat this request."}]
            report(False, str(exc) + self.queued_message())
            return events
        if self.pending:
            # Interpret dependent instructions against the clarified, updated
            # molecule rather than trusting a plan made before the barrier.
            for step in self.pending[1:]:
                step["command"] = ""
                step["question"] = "__reinterpret__"
            self.pending[0:1] = steps
        else:
            self.pending = steps
        while self.pending:
            step = self.pending[0]
            if step["question"] == "__reinterpret__":
                try:
                    following = self.interpret(step["source"], self.state())
                    validate_plan({"steps": following})
                except (InterpretationError, ValueError):
                    step["question"] = "Please clarify: " + step["source"]
                    report(False, step["question"] + self.queued_message())
                    break
                self.pending[0:1] = following
                continue
            if not step["command"]:
                report(False, step["question"] + self.queued_message())
                break
            ok, message = self.execute(step["command"])
            if not ok:
                step["command"] = ""
                step["question"] = message + " How would you like to change this instruction?"
                report(False, step["question"] + self.queued_message())
                break
            self.pending.pop(0)
            report(True, message)
        return events
