import json
from copy import deepcopy
import numpy as np
import soundfile as sf
import pytest
from streamclipper.m15_corpus import freeze_corpus,verify_corpus,compare_reports,digest
from streamclipper.speech_benchmark import evaluate_manifest


def save(path,data):
    path.write_text(json.dumps(data),encoding="utf-8")
    return path


@pytest.fixture
def corpus(tmp_path):
    cases=[]
    for i,(split,lang) in enumerate((("development","de"),("holdout","de"),("holdout","en"))):
        t=np.arange(48000)/48000
        for kind,signal in (("mix",.1*np.sin(2*np.pi*(220+i*100)*t)),("ref",.08*np.sin(2*np.pi*(220+i*100)*t))):
            sf.write(tmp_path/f"{kind}{i}.wav",signal,48000,subtype="FLOAT")
        sf.write(tmp_path/f"enroll{i}.wav",np.tile(signal,3),48000,subtype="FLOAT")
        cases.append({"id":str(i),"split":split,"language":lang,"speaker_group":f"s{i}","vod_group":f"v{i}",
            "conditions":["game_music","overlapping_speech","quiet_voice","target_absent","code_switching"],
            "mix":f"mix{i}.wav","reference_voice":f"ref{i}.wav","reference_wav":f"enroll{i}.wav",
            "reference_cues":[{"start":.1,"end":.9,"text":"hello"}]})
    return save(tmp_path/"cases.json",{"schema_version":1,"evidence_kind":"synthetic_test","cases":cases})


def test_freeze_binds_audio_annotations_and_split(corpus,tmp_path):
    lock=freeze_corpus(corpus);lp=save(tmp_path/"lock.json",lock)
    assert lock["coverage"]["holdout_speakers"]==2
    assert lock["missing_coverage"]==["real_authorized_gaming_holdout"]
    assert verify_corpus(corpus,lp)==lock
    doc=json.loads(corpus.read_text())
    doc["cases"][1]["reference_cues"][0]["text"]="changed"
    save(corpus,doc)
    with pytest.raises(ValueError,match="Frozen corpus changed"):verify_corpus(corpus,lp)
    doc["cases"][1]["vod_group"]=doc["cases"][0]["vod_group"]
    save(corpus,doc)
    with pytest.raises(ValueError,match="Group leakage"):freeze_corpus(corpus)


def test_audio_change_and_duplicate(corpus,tmp_path):
    lock=freeze_corpus(corpus);lp=save(tmp_path/"lock.json",lock)
    sf.write(tmp_path/"mix1.wav",np.zeros(48000),48000,subtype="FLOAT")
    with pytest.raises(ValueError,match="Frozen corpus changed"):verify_corpus(corpus,lp)
    doc=json.loads(corpus.read_text());doc["cases"][2]["mix"]="mix1.wav";save(corpus,doc)
    with pytest.raises(ValueError,match="Duplicate mix"):freeze_corpus(corpus)


def test_evaluated_report_pairing_and_weighted_wer(corpus,tmp_path):
    lock=freeze_corpus(corpus)
    doc=json.loads(corpus.read_text())
    frozen={c["id"]:c for c in lock["cases"]}
    doc.update({"corpus_sha256":lock["corpus_sha256"],"asr_model_sha256":"a"*64,"commit":"b"*40,"model":"test"})
    for c in doc["cases"]:
        c["estimate"]=c["reference_voice"]
        c["frozen_case_sha256"]=digest(frozen[c["id"]])
        c["variant_cues"]=c["id"]+".json"
        save(tmp_path/c["variant_cues"],[{"start":.1,"end":.8,"text":"hello" if c["id"]=="1" else "wrong"}])
    save(corpus,doc)
    a=evaluate_manifest(corpus);b=deepcopy(a);b["model"]="other"
    pa=save(tmp_path/"a.json",a);pb=save(tmp_path/"b.json",b)
    result=compare_reports(pa,pb)
    assert result["holdout"]["left"]["variant_cues"]["wer"]==.5
    assert result["by_language"]["de"]["left"]["variant_cues"]["wer"]==0
    assert result["quality_acceptance"]=="NOT_EVALUATED"
    b["cases"][1]["frozen_case_sha256"]="changed";save(pb,b)
    with pytest.raises(ValueError,match="case metadata"):compare_reports(pa,pb)
    b=deepcopy(a);b["asr_model_sha256"]="different";save(pb,b)
    with pytest.raises(ValueError,match="asr_model_sha256"):compare_reports(pa,pb)
