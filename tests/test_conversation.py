import json
import threading
from urllib.request import Request, urlopen

import pytest

from conversation import Conversation
from interpreter import InterpretationError, GeminiInterpreter, validate_plan, http_diagnostic
from urllib.error import HTTPError
from voice_server import make_server


def step(source, command="", question=""):
    return dict(source=source, command=command, question=question)


def test_clarification_holds_tail_and_announces_it():
    responses = iter([
        [step("carbon", "add carbon"), step("that group", question="Which group?"),
         step("add oxygen", "add oxygen")],
        [step("methyl", "add methyl")],
        [step("add oxygen", "add oxygen")],
    ])
    session = Conversation(lambda *_: next(responses))
    events = session.accept("carbon, that group, oxygen")
    assert len(session.builder.describe_atoms()) == 1
    assert "add oxygen" in events[-1]["message"]
    assert "queued" in events[-1]["message"]
    events = session.accept("methyl")
    assert len(events) == 2
    assert session.builder.smiles() == "CCO"
    session.accept("undo")
    assert session.builder.smiles() == "CC"


def test_rejected_edit_blocks_following_actions():
    session = Conversation(lambda *_: [step("oxygen", "add oxygen"),
        step("another oxygen", "add oxygen double bond"), step("carbon", "add carbon")])
    events = session.accept("build")
    assert len(events) == 3
    assert not events[-1]["ok"]
    assert session.builder.smiles() == "O=O"
    assert len(session.pending) == 1


def test_model_failure_preserves_request_and_state():
    def fail(*_):
        raise InterpretationError("service failed")
    session = Conversation(fail)
    session.accept("add a carbon")
    assert session.builder.smiles() == ""
    assert session.pending[0]["source"] == "add a carbon"


def test_queued_reference_reinterpreted_after_clarification():
    calls = []
    def interpret(text, state):
        calls.append((text, len(state["atoms"])))
        if len(calls) == 1:
            return [step("that group", question="Which group?"),
                    step("oxygen on the new atom", "add oxygen to atom 1")]
        if len(calls) == 2:
            return [step("ethyl", "add ethyl")]
        assert len(state["atoms"]) == 2
        return [step("oxygen on the new atom", "add oxygen to atom 2")]
    session = Conversation(interpret)
    session.accept("that group then oxygen on the new atom")
    session.accept("ethyl")
    assert session.builder.smiles() == "CCO"
    assert calls[-1] == ("oxygen on the new atom", 2)


@pytest.mark.parametrize("bad", [
    [step("carbon", "add carbon"), step("bad", "execute code")],
    [step("quit", "quit")], [step("ambiguous")],
])
def test_invalid_plan_never_partially_executes(bad):
    session = Conversation(lambda *_: bad)
    session.accept("anything")
    assert session.builder.smiles() == ""


def test_gemini_transport_contract(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self):
            return json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [
                {"thought": True, "text": "private reasoning"},
                {"text": json.dumps({"steps": [step("a carbon", "add carbon")]})}
            ]}}]}).encode()
    def transport(request, timeout):
        payload = json.loads(request.data)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["generationConfig"]["responseJsonSchema"]["required"] == ["steps"]
        assert request.full_url.endswith('/models/gemini-3.5-flash-lite:generateContent')
        assert request.get_header('X-goog-api-key') == 'test-key'
        assert 'test-key' not in request.full_url
        assert json.loads(payload['contents'][0]['parts'][0]['text'])['speech'] == 'a carbon'
        assert timeout == 30
        return Response()
    assert GeminiInterpreter(transport)("a carbon", {})[0]["command"] == "add carbon"


def test_no_api_key_fails_without_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(InterpretationError, match="GEMINI_API_KEY"):
        GeminiInterpreter()("carbon", {})


def test_gemini_rate_limit_holds_request_without_retry(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    calls = []
    def transport(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, 429, 'limited', {}, None)
    session = Conversation(GeminiInterpreter(transport))
    events = session.accept('add a carbon')
    assert len(calls) == 1
    assert session.builder.smiles() == ''
    assert session.pending[0]['source'] == 'add a carbon'
    assert 'usage limit' in events[-1]['message']


def test_gemini_error_shows_diagnostic_but_redacts_key(monkeypatch):
    import io
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-key')
    def transport(request, timeout):
        body = {'error': {'message': 'API key test-secret-key is invalid. Also AIzaAnotherSecret123'}}
        raise HTTPError(request.full_url, 400, 'bad request', {}, io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(InterpretationError) as captured:
        GeminiInterpreter(transport)('carbon', {})
    message = str(captured.value)
    assert 'HTTP 400' in message
    assert 'is invalid' in message
    assert 'test-secret-key' not in message
    assert 'AIzaAnotherSecret123' not in message


def test_gemini_non_json_error_still_shows_http_code(monkeypatch):
    import io
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    def transport(request, timeout):
        raise HTTPError(request.full_url, 503, 'unavailable', {}, io.BytesIO(b'<html>unavailable</html>'))
    with pytest.raises(InterpretationError, match='HTTP 503'):
        GeminiInterpreter(transport)('carbon', {})


@pytest.mark.parametrize('raw,expected', [
    (b'', '0 response bytes'),
    (b'<html>proxy rejected secret-key</html>', 'proxy rejected [redacted]'),
    (b'[{"error":{"message":"Invalid schema"}}]', 'Invalid schema'),
])
def test_error_response_formats(raw, expected):
    import io
    error = HTTPError('https://example.com', 400, 'bad request', {}, io.BytesIO(raw))
    message = http_diagnostic(error, 'secret-key')
    assert expected in message
    assert 'secret-key' not in message


@pytest.mark.parametrize('candidate', [
    {}, {'candidates': []},
    {'candidates': [{'finishReason': 'MAX_TOKENS'}]},
    {'candidates': [{'finishReason': 'SAFETY'}]},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'not json'}]}}]},
])
def test_incomplete_or_invalid_gemini_response_cannot_execute(monkeypatch, candidate):
    import io
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    session = Conversation(GeminiInterpreter(lambda *args, **kwargs: io.BytesIO(json.dumps(candidate).encode())))
    events = session.accept('add carbon')
    assert session.builder.smiles() == ''
    assert not events[-1]['ok']


def test_http_stream_has_separate_states_and_images():
    server = make_server(0, lambda *_: [step("carbon", "add carbon"), step("oxygen", "add oxygen")])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:{}".format(server.server_port)
    try:
        with urlopen(base + "/health") as response:
            health = json.load(response)
            assert health['provider'] == 'gemini'
            assert isinstance(health['api_key_configured'], bool)
            assert 'api_key' not in health
        request = Request(base + "/utterance", data=json.dumps({"text": "carbon then oxygen"}).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request) as response:
            events = [json.loads(line) for line in response]
        assert [event["smiles"] for event in events] == ["C", "CO"]
        with urlopen(base + "/image") as response:
            assert b"svg" in response.read()
        with urlopen(base + "/state") as response:
            assert json.load(response)["smiles"] == "CO"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
