"""M12-UX: layout never contains project state, survives restart and corrupt files."""
import json

import pytest

from streamclipper.workspace_layout import (
    WorkspaceLayout, MAX_DOCUMENT_BYTES, load_workspace,
    save_workspace, delete_workspace, FILE_NAME)


def test_workspace_persists_dock_bytes_and_preset_only(tmp_path):
    payload = b"\\x00\\xffQDockWidget\\x00workspace"
    state = WorkspaceLayout("Schnitt", payload)
    path = save_workspace(state, root=tmp_path)
    assert path.name == FILE_NAME
    assert load_workspace(root=tmp_path) == state
    doc = json.loads(path.read_text("utf-8"))
    assert set(doc) == {"schema_version", "active", "state_base64"}
    assert "source" not in doc
    assert "token" not in doc
    delete_workspace(root=tmp_path)
    assert load_workspace(root=tmp_path) is None


def test_invalid_state_and_unknown_workspace_never_replace_saved_file(tmp_path):
    baseline = WorkspaceLayout("Highlights", b"safe")
    path = save_workspace(baseline, root=tmp_path)
    old = path.read_bytes()
    for bad in [
        WorkspaceLayout("Cloud", b"x"),
        WorkspaceLayout("Export", b""),
        WorkspaceLayout("Export", b"x" * (256 * 1024 + 1)),
    ]:
        with pytest.raises(ValueError):
            save_workspace(bad, root=tmp_path)
        assert path.read_bytes() == old


def test_layout_corruption_and_future_schema_are_discarded(tmp_path):
    path = tmp_path / FILE_NAME
    for blob in [
        b"not json",
        b"{" + b"x" * MAX_DOCUMENT_BYTES + b"}",
        b'{"schema_version":99,"active":"Schnitt","state_base64":"eA=="}',
        b'{"schema_version":1,"active":"Schnitt","state_base64":"not:base64"}',
        b'{"schema_version":1,"active":"Schnitt","state_base64":""}',
        b'{"schema_version":1,"active":"unknown","state_base64":"eA=="}',
    ]:
        path.write_bytes(blob)
        assert load_workspace(root=tmp_path) is None
    path.unlink()
    delete_workspace(root=tmp_path)
    assert load_workspace(root=tmp_path) is None
