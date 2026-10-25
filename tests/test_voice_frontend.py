"""Production React assets and /api aliases use the voice server's session."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import voice_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    dist = tmp_path / 'dist'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text('<html>React frontend</html>')
    (dist / 'assets' / 'app.js').write_text('console.log("frontend")')
    (tmp_path / 'outside.txt').write_text('must stay private')
    monkeypatch.setattr(voice_server, 'DIST', dist)
    server = voice_server.make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:{}'.format(server.server_port)
    server.shutdown()
    server.server_close()
    thread.join()


def test_built_frontend_and_api_aliases_share_state_and_undo(server):
    with urlopen(server + '/') as response:
        assert b'React frontend' in response.read()
    with urlopen(server + '/assets/app.js') as response:
        assert 'javascript' in response.headers['Content-Type']
    request = Request(server + '/api/command', data=b'{"text":"add carbon"}',
                      headers={'Content-Type': 'application/json'})
    with urlopen(request) as response:
        assert json.load(response)['smiles'] == 'C'
    with urlopen(server + '/state') as response:
        assert json.load(response)['smiles'] == 'C'
    request = Request(server + '/command', data=b'{"text":"undo"}',
                      headers={'Content-Type': 'application/json'})
    with urlopen(request) as response:
        assert json.load(response)['smiles'] == ''
    with urlopen(server + '/api/state') as response:
        assert json.load(response)['smiles'] == ''


def test_frontend_assets_cannot_escape_build_directory(server):
    with pytest.raises(HTTPError) as captured:
        urlopen(server + '/assets/../../outside.txt')
    assert captured.value.code == 404
