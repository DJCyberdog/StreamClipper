import json
from types import SimpleNamespace
import pytest

Image=pytest.importorskip("PIL.Image")
from streamclipper.vace_inpainting import restore_window, mask_composite, validate_window


def fixture():
    frames=[Image.new("RGB",(64,64),(10,20,30)) for _ in range(9)]
    masks=[Image.new("L",(64,64),0) for _ in frames]
    for m in masks:
        m.paste(255,(0,0,16,16))
    return frames,masks


def test_mask_preserves_context_and_temporal_count():
    frames,masks=fixture()
    generated=[Image.new("RGB",(64,64),(i,100,200)) for i in range(9)]
    out=mask_composite(frames,generated,masks)
    assert len(out)==9
    assert out[3].getpixel((0,0))==(3,100,200)
    assert out[3].getpixel((16,0))==(10,20,30)
    assert frames[3].getpixel((0,0))==(10,20,30)


def test_window_validates_binary_masks_and_output_size():
    frames,masks=fixture()
    with pytest.raises(ValueError):
        mask_composite(frames,frames[:-1],masks)
    masks[0].putpixel((1,1),128)
    with pytest.raises(ValueError,match="binär"):
        validate_window(frames,masks)


def test_explicit_local_pipeline_contract(tmp_path):
    frames,masks=fixture()
    (tmp_path/"model_index.json").write_text(json.dumps({"_class_name":"WanVACEPipeline"}))
    calls=[]
    def factory(folder,seed):
        assert folder==tmp_path.resolve() and seed==42
        def pipeline(**kw):
            calls.append(kw)
            assert kw["video"][0].getpixel((0,0))==(127,127,127)
            assert kw["video"][0].getpixel((20,20))==(10,20,30)
            assert kw["num_frames"]==9 and kw["mask"]==masks
            kw["callback_on_step_end"](None,0,None,{})
            return SimpleNamespace(frames=[[Image.new("RGB",(64,64),(200,0,0)) for _ in frames]])
        return pipeline,None
    out=restore_window(frames,masks,tmp_path,pipeline_factory=factory)
    assert len(calls)==1
    assert out[0].getpixel((0,0))==(200,0,0)
    assert out[0].getpixel((20,20))==(10,20,30)
