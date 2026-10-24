"""Ordered execution and clarification barriers, independent of microphone/AI."""

from builder import Builder
from main import HELP_TEXT, OPTIONS_TEXT, ELEMENT_MESSAGE
from parser import parse
from readback import detail, summary
from rdkit.Chem.Draw import rdMolDraw2D
from interpreter import InterpretationError, validate_plan


class Conversation:
    def __init__(self, interpret):
        self.builder = Builder()
        self.interpret = interpret
        self.pending = []
        self.message = "Enable your microphone, then say Start."
        self.version = 0

    def state(self):
        return {"smiles": self.builder.smiles(), "summary": summary(self.builder),
                "detail": detail(self.builder), "atoms": self.builder.describe_atoms(),
                "current_atom": self.builder.current_atom, "message": self.message,
                "version": self.version, "queued": [s["source"] for s in self.pending],
                "image_url": "/image?v={}".format(self.version)}

    def image(self):
        molecule = self.builder.molecule_copy()
        if not molecule.GetNumAtoms():
            return '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><text x="30" y="60" font-size="28">Your molecule is empty.</text></svg>'
        for atom in molecule.GetAtoms():
            atom.SetProp("atomNote", str(atom.GetIdx() + 1))
        drawer = rdMolDraw2D.MolDraw2DSVG(800, 600)
        highlight = [] if self.builder.current_atom is None else [self.builder.current_atom - 1]
        rdMolDraw2D.PrepareAndDrawMolecule(drawer, molecule, highlightAtoms=highlight)
        drawer.FinishDrawing()
        return drawer.GetDrawingText()

    def execute(self, text):
        command = parse(text)
        if command is None:
            return False, "That command was not understood."
        action = command["action"]
        b = self.builder
        calls = {
            "add_atom": lambda: b.add_atom(command["symbol"], command["bond_order"], command.get("to_atom")),
            "add_chain": lambda: b.add_chain(command["count"], to_atom=command.get("to_atom")),
            "add_group": lambda: b.add_group(command["name"], command.get("to_atom")),
            "add_ring": lambda: b.add_ring(command["kind"], to_atom=command.get("to_atom")),
            "connect": lambda: b.connect(command["a"], command["b"], command["bond_order"]),
            "close_ring": lambda: b.connect(b.current_atom, 1),
            "set_bond_order": lambda: b.set_bond_order(command["a"], command["b"], command["order"]),
            "delete_atom": lambda: b.delete_atom(command["atom_number"]),
            "reset": b.reset, "undo": b.undo,
        }
        if action in calls:
            ok, message = calls[action]()
            if ok:
                self.version += 1
            return ok, message
        if action == "read_back":
            return True, detail(b)
        if action == "summary":
            return True, summary(b)
        if action == "help":
            return True, HELP_TEXT
        if action == "what_can_i_add":
            return True, OPTIONS_TEXT
        if action == "where_am_i":
            return True, "Current atom: {}.".format(b.current_atom or "none")
        if action == "unsupported_element":
            return False, ELEMENT_MESSAGE
        return False, "That command is unavailable in the browser."

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
