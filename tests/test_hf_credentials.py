"""Windows Credential Manager integration using only a generated dummy token."""
from __future__ import annotations

import os
import uuid

import pytest
import streamclipper.hf_credentials as credentials


@pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager only")
def test_windows_credential_manager_dummy_token_roundtrip(monkeypatch):
    target = "StreamClipper/CI-Test-" + uuid.uuid4().hex
    monkeypatch.setattr(credentials, "TARGET", target)
    sample = "hf_fake_ci_credential_" + uuid.uuid4().hex
    try:
        assert credentials.read_token() is None
        credentials.save_token(sample)
        assert credentials.read_token() == sample
    finally:
        credentials.remove_token()
    assert credentials.read_token() is None


@pytest.mark.skipif(os.name == "nt", reason="Check safe non-Windows path")
def test_non_windows_never_persists_credential():
    assert not credentials.supported()
    with pytest.raises(RuntimeError):
        credentials.save_token("hf_fake_session")
