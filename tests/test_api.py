"""Tests for the HTTP API. They use Flask's test client; no real network."""

import pytest
from rdkit import Chem

import api

@pytest.fixture(autouse=True)
def fresh_state():
    # Each test starts with an empty molecule and version 0.
    api.reset_state()

@pytest.fixture
def client():
    return api.create_app().test_client()

def post(client, text):
    return client.post("/command", json={"text": text})

def test_add_carbon_returns_expected_shape(client):
    resp = post(client, "add carbon")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["smiles"] == "C"
    assert data["current_atom"] == 1
    assert data["atoms"][0]["symbol"] == "C"
    assert "summary" in data and "detail" in data
    assert data["image_url"].startswith("/image?v=")
    assert "Added carbon" in data["message"]

def test_build_acetone_over_several_commands(client):
    for text in ["add carbon", "add carbon", "add oxygen double bond",
                 "go to atom 2", "add carbon"]:
        assert post(client, text).get_json()["ok"] is True
    data = post(client, "summary").get_json()
    assert Chem.CanonSmiles(data["smiles"]) == Chem.CanonSmiles("CC(C)=O")

def test_rejection_leaves_molecule_unchanged(client):
    post(client, "add carbon")
    before = post(client, "summary").get_json()["smiles"]
    resp = post(client, "add nitrogen")
    data = resp.get_json()
    assert resp.status_code == 200          # never 500 on ordinary bad input
    assert data["ok"] is False
    assert data["message"] == api.ELEMENT_MESSAGE
    assert data["smiles"] == before          # unchanged

def test_unparseable_command_is_graceful(client):
    resp = post(client, "banana please")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["ok"] is False
    assert "didn't understand" in data["message"]
    assert data["smiles"] == ""

def test_empty_text_and_missing_body_do_not_crash(client):
    assert post(client, "").get_json()["ok"] is False
    assert client.post("/command", data="not json",
                       content_type="text/plain").status_code == 200

def test_read_only_commands_do_not_change_state(client):
    post(client, "add benzene ring")
    before = post(client, "summary").get_json()
    for text in ["summary", "read it back", "where am I", "what can I add", "help"]:
        data = post(client, text).get_json()
        assert data["ok"] is True
    after = post(client, "summary").get_json()
    assert after["smiles"] == before["smiles"]
    assert after["current_atom"] == before["current_atom"]

def test_undo_restores_previous_state(client):
    post(client, "add carbon")
    post(client, "add oxygen")
    assert post(client, "undo").get_json()["ok"] is True
    assert post(client, "summary").get_json()["smiles"] == "C"

def test_state_endpoint_reports_without_changing(client):
    post(client, "add carbon")
    data = client.get("/state").get_json()
    assert data["smiles"] == "C"
    assert data["current_atom"] == 1
    # Calling /state again must not alter anything.
    assert client.get("/state").get_json()["smiles"] == "C"

def test_image_url_version_changes_after_edits(client):
    v0 = client.get("/state").get_json()["image_url"]
    post(client, "add carbon")
    v1 = post(client, "add carbon").get_json()["image_url"]
    assert v0 != v1

def test_image_svg_has_content_when_built(client):
    assert client.get("/image").status_code == 204    # empty molecule
    post(client, "add benzene ring")
    resp = client.get("/image")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert b"svg" in resp.data

def test_image_png_available(client):
    post(client, "add carbon")
    resp = client.get("/image?fmt=png")
    assert resp.status_code == 200
    assert resp.data.startswith(b"\x89PNG\r\n\x1a\n")

def test_terminal_only_commands_are_polite(client):
    for text in ["quit", "faster", "slower", "save", "show"]:
        data = post(client, text).get_json()
        assert data["ok"] is True
        assert "website" in data["message"]

def test_build_named_molecule_over_api(client):
    data = post(client, "build aspirin").get_json()
    assert data["ok"] is True
    assert Chem.CanonSmiles(data["smiles"]) == Chem.CanonSmiles("CC(=O)Oc1ccccc1C(=O)O")

def test_unknown_named_molecule_over_api_is_graceful(client):
    post(client, "add carbon")
    data = post(client, "build unobtainium").get_json()
    assert data["ok"] is False
    assert "don't have that molecule" in data["message"]
    assert data["smiles"] == "C"            # unchanged

def test_named_molecule_rejects_hidden_non_co(client, monkeypatch):
    # Even if the library were tampered with, load_molecule enforces C/O only.
    import library
    monkeypatch.setitem(library._INDEX, "fake", "CCN")
    data = post(client, "build fake").get_json()
    assert data["ok"] is False
    assert "carbon and oxygen" in data["message"]
