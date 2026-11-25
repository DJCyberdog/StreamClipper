"""M10.5 wish: model byte progress, authentication and safety with no network."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
import pytest

from streamclipper.media import CancelledError
from streamclipper.model_download_progress import ModelDownloadProgress
import streamclipper.model_catalog as catalog


def test_progress_counts_bytes_only_and_keeps_100_for_validation():
    events = []
    progress = ModelDownloadProgress(lambda *event: events.append(event))
    progress.report("metadata")
    assert events[-1] == (None, 0, None, "metadata")
    progress.set_total(1000)
    progress.add(2, channel="file")  # legacy transfer, NOT a file counter
    assert events[-1][0] is None
    progress.add(498, channel="file")
    assert events[-1] == (50, 500, 1000, "download")
    progress.add(5000, channel="transfer")  # modern parent replaces per-file
    assert events[-1][0] == 99
    assert events[-1][1] == 5000
    progress.add(5000, channel="file")  # no double count once parent exists
    assert events[-1][1] == 5000
    progress.finish()
    assert events[-1][0] == 100


def test_tqdm_adapter_ignores_reconstruction_and_file_counts(monkeypatch):
    tqdm = ModuleType("tqdm")
    auto = ModuleType("tqdm.auto")
    class FakeTqdm:
        def __init__(self, *args, **kwargs):
            self.n = kwargs.get("initial", 0)
        def update(self, n=1):
            self.n += n
    auto.tqdm = FakeTqdm
    monkeypatch.setitem(sys.modules, "tqdm", tqdm)
    monkeypatch.setitem(sys.modules, "tqdm.auto", auto)
    result = []
    tracker = ModelDownloadProgress(lambda *value: result.append(value))
    tracker.set_total(1000)
    cls = tracker.tqdm_class()
    cls(name="huggingface_hub.snapshot_download", unit="B").update(800)
    cls(name="Fetching", unit="it").update(20)
    assert result[-1][1] == 0
    cls(name="huggingface_hub.snapshot_download.transfer", unit="B").update(345)
    assert result[-1][:3] == (34, 345, 1000)


def test_model_download_uses_token_for_both_snapshots_and_only_finishes_after_validation(
        monkeypatch, tmp_path):
    module = ModuleType("huggingface_hub")
    events, calls = [], []
    class API:
        def model_info(self, repo_id, *, files_metadata, token):
            assert token == "hf_test_secret"
            return SimpleNamespace(siblings=[
                SimpleNamespace(rfilename="config.json", size=100),
                SimpleNamespace(rfilename="pytorch_model.bin", size=500),
            ])
    def download(**kwargs):
        calls.append(kwargs)
        folder = Path(kwargs["local_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        if "pytorch_model.bin" in kwargs["allow_patterns"]:
            (folder / "pytorch_model.bin").write_bytes(b"x" * 3)
        else:
            (folder / "config.json").write_bytes(b"test")
        return str(folder)
    module.HfApi = API
    module.snapshot_download = download
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setattr(catalog, "validate_model_dir",
                        lambda kind, folder: Path(folder))
    # mock tqdm import without installing optional ML dependencies
    auto = ModuleType("tqdm.auto")
    auto.tqdm = type("MinimalTqdm", (), {"__init__": lambda self, *a, **k: None})
    monkeypatch.setitem(sys.modules, "tqdm", ModuleType("tqdm"))
    monkeypatch.setitem(sys.modules, "tqdm.auto", auto)
    folder = catalog.download_preset(
        "detr-resnet-50", root=tmp_path, token="hf_test_secret",
        progress=lambda *v: events.append(v))
    assert folder.is_dir()
    assert len(calls) == 2
    assert all(x["token"] == "hf_test_secret" and x.get("tqdm_class")
               for x in calls)
    assert any(x[3] == "validation" and x[0] is None for x in events)
    assert events[-1][0] == 100
    assert all(e[0] is None or e[0] <= 99 for e in events[:-1])


def test_token_never_surfaces_in_safe_errors():
    class Error(Exception):
        pass
    msg = catalog.safe_hf_error(Error("hf_secret_panic_exception"))
    assert "hf_secret" not in msg
    assert "Error" in msg
    class Unauthorized(Exception):
        response = SimpleNamespace(status_code=401)
    assert "401" in catalog.safe_hf_error(Unauthorized("hf_secret"))


def test_cancel_triggers_and_does_not_report_completion():
    flag = threading.Event()
    seen = []
    tracker = ModelDownloadProgress(lambda *v: seen.append(v), cancelled=flag.is_set)
    tracker.set_total(100)
    tracker.add(10, channel="transfer")
    flag.set()
    with pytest.raises(CancelledError):
        tracker.add(20, channel="transfer")
    with pytest.raises(CancelledError):
        tracker.finish()
    assert seen[-1][0] != 100


def test_preflight_missing_size_uses_indeterminate_progress():
    info = SimpleNamespace(siblings=[SimpleNamespace(rfilename="model.bin", size=None)])
    api = SimpleNamespace(model_info=lambda *a, **k: info)
    total = catalog._expected_model_bytes(
        api, catalog.preset("whisper-base"), ["model.bin"], token=None)
    assert total is None


def test_xet_transfer_bytes_do_not_double_count_reconstruction(monkeypatch):
    parent = ModuleType("tqdm")
    auto = ModuleType("tqdm.auto")
    class Tqdm:
        def __init__(self, *args, **kwargs):
            self.n = kwargs.get("initial", 0)
        def update(self, n=1):
            self.n += n
    auto.tqdm = Tqdm
    monkeypatch.setitem(sys.modules, "tqdm", parent)
    monkeypatch.setitem(sys.modules, "tqdm.auto", auto)
    results = []
    tracker = ModelDownloadProgress(lambda *item: results.append(item))
    tracker.set_total(1000)
    bar = tracker.tqdm_class()(name="Reconstructing", unit="B")
    bar.update(700)           # bytes written to disk: not network transfer
    assert results[-1][1] == 0
    bar.update_transfer(250)  # actual Xet network bytes
    assert results[-1][:3] == (25, 250, 1000)
    bar.update(200)
    assert results[-1][1] == 250
