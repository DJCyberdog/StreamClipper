from pathlib import Path
import sys
from scripts.setup_gpu_runtime import setup,TORCH,VISION

def test_gpu_setup_downloads_model_before_tests(tmp_path):
    runtime=tmp_path/"runtime";runtime.mkdir();(runtime/"python.exe").touch()
    model=[False]; calls=[]
    def execute(args):
        args=list(map(str,args));calls.append(args)
        if any("setup_local_models.py" in a for a in args):model[0]=True
        return 0
    assert setup(tmp_path,consent=lambda:True,execute=execute,installed=lambda *a:model[0])==0
    assert "setup_local_models.py" in calls[0][1]
    assert TORCH in calls[2] and VISION in calls[2]
    assert calls[-2][-1]=="whisper-first" and calls[-1][-1]=="torch-first"
    assert all(Path(c[0])==runtime/"python.exe" for c in calls)

def test_gpu_setup_declined_model_is_pending(tmp_path):
    runtime=tmp_path/"runtime";runtime.mkdir();(runtime/"python.exe").touch()
    calls=[]
    def execute(args):
        args=list(map(str,args));calls.append(args)
        return 3 if any("check_gpu_runtime.py" in a for a in args) else 0
    assert setup(tmp_path,consent=lambda:False,execute=execute,installed=lambda *a:False)==3
    assert len(calls)==4
    assert not any("setup_local_models.py" in a for c in calls for a in c)

def test_gpu_setup_never_claims_combined_failure_pass(tmp_path):
    runtime=tmp_path/"runtime";runtime.mkdir();(runtime/"python.exe").touch()
    def execute(args):
        return 1 if "whisper-first" in args else 0
    assert setup(tmp_path,consent=lambda:False,execute=execute,installed=lambda *a:True)==1

def test_gpu_setup_download_failure_stops(tmp_path):
    runtime=tmp_path/"runtime";runtime.mkdir();(runtime/"python.exe").touch()
    calls=[]
    def execute(args):calls.append(args);return 1
    assert setup(tmp_path,consent=lambda:True,execute=execute,installed=lambda *a:False)==1
    assert len(calls)==1
