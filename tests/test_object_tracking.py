"""Model-free contract tests: real model inference is an explicit acceptance gate."""
import math
import sys
from types import ModuleType
from pathlib import Path

import pytest

from streamclipper import analyze as analyzer
from streamclipper.model_catalog import (DEFAULTS, PRESETS, download_preset,
                                          is_installed, preset, preset_path,
                                          validate_model_dir)
from streamclipper.models import VideoInfo
from streamclipper.object_tracking import (Detection, detect_and_track,
    group_tracklets, intersection_over_union, object_track_evidence)
from streamclipper.semantic import EventEvidence, fuse_events


def obj(t, x=.1, y=.1, label='car'):
    return Detection(t, label, .95, (x, y, x+.3, y+.2))


def test_model_catalog_has_distinct_supported_model_types_and_existing_defaults():
    assert len(PRESETS) == len({m.id for m in PRESETS})
    assert DEFAULTS['speech'] == 'whisper-small'
    assert DEFAULTS['vision'] == 'clip-vit-base-patch32'
    assert len([m for m in PRESETS if m.kind == 'speech']) >= 5
    assert len([m for m in PRESETS if m.kind == 'vision']) == 2
    assert len([m for m in PRESETS if m.kind == 'detector']) == 2
    assert preset('detr-resnet-50').repository == 'facebook/detr-resnet-50'
    with pytest.raises(ValueError): preset('remote/arbitrary')


def test_models_are_checked_locally_and_missing_weights_never_succeed(tmp_path):
    det = preset_path('detr-resnet-50', tmp_path)
    det.mkdir()
    (det / 'config.json').write_text('{}')
    (det / 'preprocessor_config.json').write_text('{}')
    assert not is_installed('detr-resnet-50', tmp_path)
    with pytest.raises(FileNotFoundError, match='model.safetensors'):
        validate_model_dir('detector', det)
    (det / 'model.safetensors').write_bytes(b'fake')
    assert is_installed('detr-resnet-50', tmp_path)
    assert validate_model_dir('detector', det) == det
    speech = preset_path('whisper-base',tmp_path)
    speech.mkdir()
    (speech / 'model.bin').write_bytes(b'mock')
    (speech / 'config.json').write_text('{}')
    assert is_installed('whisper-base', tmp_path)


def test_models_download_only_requested_preset_and_fallback(tmp_path, monkeypatch):
    calls=[]
    hub = ModuleType('huggingface_hub')
    def snapshot_download(*, repo_id, local_dir, allow_patterns):
        calls.append((repo_id,allow_patterns))
        path=Path(local_dir)
        path.mkdir(parents=True,exist_ok=True)
        (path/'config.json').write_text('{}')
        (path/'preprocessor_config.json').write_text('{}')
        if 'pytorch_model.bin' in allow_patterns:
            (path/'pytorch_model.bin').write_bytes(b'fake')
    hub.snapshot_download=snapshot_download
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    path=download_preset('detr-resnet-50', tmp_path)
    assert path == tmp_path / 'detr-resnet-50'
    assert [x[0] for x in calls] == ['facebook/detr-resnet-50']*2
    assert calls[-1][1] == ['pytorch_model.bin']


def test_models_never_download_during_preflight(tmp_path, monkeypatch):
    incomplete=tmp_path/'detector'
    incomplete.mkdir()
    called=[]
    monkeypatch.setattr(analyzer,'probe_video',lambda *_: called.append('probe'))
    monkeypatch.setattr(analyzer,'audio_levels',lambda *_,**kwargs: called.append('audio'))
    with pytest.raises(FileNotFoundError, match='Modell unvollständig'):
        analyzer.analyze('6-hours.mp4', detector_model=str(incomplete))
    assert called==[]


def test_temporal_association_requires_nearby_frames_and_matching_class():
    frames = [obj(100,.1), obj(100.7,.11), obj(100.7,.2,label='truck'),
              obj(300,.1), obj(300.6,.11,label='truck')]
    tracks=group_tracklets(frames)
    assert sorted(map(len,tracks))==[1,1,1,2]
    assert tracks[0][0].at==100
    assert group_tracklets([obj(1),obj(8)])[0] == [obj(1)]
    assert intersection_over_union(obj(0,.1).box,obj(1,.1).box)==1
    assert intersection_over_union(obj(0,.1).box,obj(1,.6).box)==0


def test_track_evidence_requires_motion_and_temporal_confirmation():
    hits=[obj(10,.1),obj(11,.15),obj(30,.2),obj(31,.22)]
    motion=[EventEvidence(10.5,'motion',.55,'Scene spike')]
    ev=object_track_evidence(hits,motion)
    assert len(ev)==1
    assert ev[0].kind=='object'
    assert 'Auto' in ev[0].description
    assert 'kein bestätigtes Ereignis' in ev[0].description
    assert object_track_evidence(hits,[])==[]
    assert object_track_evidence([hits[0]],motion)==[]
    combined=fuse_events(ev+[EventEvidence(10.5,'motion',.55,'Image spike')],60)
    assert 'Objektspur' in combined[0].reason


def test_six_hour_object_only_integration_preserves_offline_and_budget(monkeypatch):
    video=VideoInfo('long.mp4',6*3600,1920,1080,60,True)
    called=[]
    monkeypatch.setattr(analyzer,'validate_model_dir',lambda *args: called.append('preflight'))
    monkeypatch.setattr(analyzer,'probe_video',lambda _: video)
    monkeypatch.setattr(analyzer,'audio_levels',lambda *args,**kw: [-30]*21600)
    def scan(*args,**kw):
        called.append('scan')
        return [EventEvidence(20000,'motion',.59,'Bildveränderung')]
    def detect(*args,**kw):
        called.append('detect')
        assert kw['max_frames']==24
        assert any(e.kind=='motion' for e in kw['anchors'])
        return [EventEvidence(20000.5,'object',.46,'Objektspur: LKW')]
    monkeypatch.setattr(analyzer,'scan_temporal_activity',scan)
    monkeypatch.setattr(analyzer,'detect_and_track',detect)
    progress=[]
    out=analyzer.analyze('long.mp4',detector_model='detector',max_object_frames=24,
                         progress=progress.append)
    assert called==['preflight','scan','detect']
    assert out.method=='multimodal-object-tracklets-v3'
    assert 'Objektspur' in out.candidates[0].reason
    assert out.transcript==[]
    assert progress[-1]==100
    assert all(b>=a for a,b in zip(progress,progress[1:]))


def test_object_detector_cancelled_before_import_or_fetch(tmp_path):
    path=tmp_path/'detector';path.mkdir()
    for name in ('config.json','preprocessor_config.json','model.safetensors'):
        (path/name).write_bytes(b'fake')
    with pytest.raises(Exception,match='abgebrochen'):
        detect_and_track(VideoInfo('not-real.mp4',20,800,600,30,False),path,
                         anchors=[], cancelled=lambda: True)


def test_detection_adapter_uses_local_transformers_and_three_neighbor_frames(tmp_path, monkeypatch):
    """Exercise the complete detector adapter without Torch, Pillow or network."""
    from contextlib import nullcontext
    from types import SimpleNamespace
    import streamclipper.object_tracking as tracking

    folder = tmp_path / 'detector'
    folder.mkdir()
    for name in ('config.json', 'preprocessor_config.json', 'model.safetensors'):
        (folder/name).write_bytes(b'fake')

    def frames(*args, **kwargs):
        assert kwargs['max_frames'] == 6
        for at in (9, 10, 11):
            yield float(at), b'synthetic-jpeg'
    monkeypatch.setattr(tracking, 'sampled_jpeg_frames', frames)

    class FakeImage:
        size = (80, 60)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def convert(self, mode):
            assert mode == 'RGB'
            return self
    pil = ModuleType('PIL')
    image_module = ModuleType('PIL.Image')
    image_module.open = lambda _: FakeImage()
    pil.Image = image_module
    monkeypatch.setitem(sys.modules, 'PIL', pil)
    monkeypatch.setitem(sys.modules, 'PIL.Image', image_module)

    class Tensor:
        def to(self, device):
            assert device == 'cpu'
            return self
        def float(self): return self
        def all(self): return True
    torch = ModuleType('torch')
    torch.cuda = SimpleNamespace(is_available=lambda: False)
    torch.no_grad = nullcontext
    torch.isfinite = lambda tensor: tensor
    monkeypatch.setitem(sys.modules, 'torch', torch)

    class Box(list):
        def tolist(self): return list(self)
    class Processor:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert path == str(folder) and kwargs == {'local_files_only': True}
            return cls()
        def __call__(self, **kwargs):
            return {'pixel_values': Tensor()}
        def post_process_object_detection(self, output, **kwargs):
            assert kwargs['threshold'] == 0.55
            assert kwargs['target_sizes'] == [(60, 80)]
            return [{'scores': [.95], 'labels': [1],
                     'boxes': [Box([10., 10., 35., 30.])]}]
    class Detector:
        config = SimpleNamespace(id2label={1: 'car'})
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert path == str(folder) and kwargs == {'local_files_only': True}
            return cls()
        def to(self, device): return self
        def eval(self): return self
        def __call__(self, **kwargs): return SimpleNamespace(logits=Tensor(),pred_boxes=Tensor())
    fake = ModuleType('transformers')
    fake.AutoImageProcessor = Processor
    fake.AutoModelForObjectDetection = Detector
    monkeypatch.setitem(sys.modules, 'transformers', fake)

    updates = []
    events = tracking.detect_and_track(
        VideoInfo('fake.mp4', 30, 1920, 1080, 60, False), folder,
        anchors=[EventEvidence(10, 'motion', .7, 'Ungewöhnliche Szene')],
        max_frames=6, progress=updates.append)
    assert len(events) == 1
    assert 'Objektspur: Auto' in events[0].description
    assert updates[-1] == 100
