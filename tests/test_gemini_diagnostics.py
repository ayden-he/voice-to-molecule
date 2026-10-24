import json
from types import SimpleNamespace
from urllib.request import Request

from gemini_test import curl_probe


def test_curl_keeps_key_out_of_command_arguments(monkeypatch, capsys):
    import gemini_test
    monkeypatch.setattr(gemini_test.shutil, 'which', lambda _: 'curl.exe')
    def run(args, **kwargs):
        assert 'secret-key' not in ' '.join(args)
        assert 'secret-key' in kwargs['input']
        assert '--config' in args
        return SimpleNamespace(returncode=0, stdout='{}\nHTTP_STATUS:200')
    monkeypatch.setattr(gemini_test.subprocess, 'run', run)
    curl_probe(Request('https://example.com', data=b'{}'), 'secret-key')
    assert 'PASSED' in capsys.readouterr().out


def test_curl_redacts_google_error(monkeypatch, capsys):
    import gemini_test
    monkeypatch.setattr(gemini_test.shutil, 'which', lambda _: 'curl.exe')
    body = json.dumps({'error': {'message': 'Invalid secret-key'}})
    monkeypatch.setattr(gemini_test.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=body + '\nHTTP_STATUS:400'))
    curl_probe(Request('https://example.com', data=b'{}'), 'secret-key')
    output = capsys.readouterr().out
    assert 'secret-key' not in output
    assert 'HTTP 400' in output
