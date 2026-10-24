"""Tests for the PubChem name lookup. The network is always mocked."""

from unittest.mock import Mock

import pytest

import naming

def fake_response(payload, monkeypatch):
    """Make naming._request_json return a fixed parsed payload (no network)."""
    monkeypatch.setattr(naming, "_request_json", Mock(return_value=payload))

def test_both_names_returned(monkeypatch):
    fake_response({"PropertyTable": {"Properties": [
        {"CID": 2244, "Title": "Aspirin", "IUPACName": "2-acetyloxybenzoic acid"}
    ]}}, monkeypatch)
    common, iupac, message = naming.lookup_name("CC(=O)Oc1ccccc1C(=O)O")
    assert common == "Aspirin"
    assert iupac == "2-acetyloxybenzoic acid"
    assert "Aspirin" in message and "2-acetyloxybenzoic acid" in message

def test_matching_names_are_not_repeated(monkeypatch):
    fake_response({"PropertyTable": {"Properties": [
        {"CID": 702, "Title": "Ethanol", "IUPACName": "ethanol"}
    ]}}, monkeypatch)
    common, iupac, message = naming.lookup_name("CCO")
    assert message.lower().count("ethanol") == 1

def test_only_iupac_available(monkeypatch):
    fake_response({"PropertyTable": {"Properties": [
        {"CID": 123, "IUPACName": "some-systematic-name"}
    ]}}, monkeypatch)
    common, iupac, message = naming.lookup_name("CCC")
    assert common is None
    assert iupac == "some-systematic-name"
    assert "systematic name is some-systematic-name" in message

def test_structure_not_found_cid_zero(monkeypatch):
    fake_response({"PropertyTable": {"Properties": [{"CID": 0}]}}, monkeypatch)
    common, iupac, message = naming.lookup_name("C1CC1C1CC1OC(O)(O)O")
    assert common is None and iupac is None
    assert "couldn't find a name" in message

def test_network_failure_returns_message(monkeypatch):
    monkeypatch.setattr(naming, "_request_json", Mock(return_value=None))
    common, iupac, message = naming.lookup_name("CCO")
    assert common is None and iupac is None
    assert "couldn't reach the naming service" in message

def test_malformed_response_is_handled(monkeypatch):
    fake_response({"unexpected": "shape"}, monkeypatch)
    common, iupac, message = naming.lookup_name("CCO")
    assert common is None and iupac is None
    assert "couldn't find a name" in message

@pytest.mark.parametrize("bad", ["", None])
def test_empty_smiles_does_not_call_network(bad, monkeypatch):
    called = Mock()
    monkeypatch.setattr(naming, "_request_json", called)
    common, iupac, message = naming.lookup_name(bad)
    assert common is None and iupac is None
    called.assert_not_called()

def test_smiles_is_url_encoded(monkeypatch):
    seen = {}

    def capture(url):
        seen["url"] = url
        return {"PropertyTable": {"Properties": [{"CID": 1, "Title": "X"}]}}

    monkeypatch.setattr(naming, "_request_json", capture)
    naming.lookup_name("C#CC(=O)O")
    assert "C%23CC%28%3DO%29O" in seen["url"]
    assert "C#CC(=O)O" not in seen["url"]
