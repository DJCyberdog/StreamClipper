"""Explicit opt-in download of the VoxLock model files from the pinned revision."""
import argparse
import hashlib
from pathlib import Path
from huggingface_hub import hf_hub_download

REVISION="2413b292bc2c337bfc19a9802aaf3e011e68e9c4"
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--directory",default="data/models/voxlock")
    args=parser.parse_args()
    root=Path(args.directory).resolve()
    for name in ("enroll.onnx","chunk_int8.onnx"):
        path=Path(hf_hub_download("arbazsiddiqui/voxlock","onnx/v2/"+name,
            revision=REVISION,local_dir=str(root)))
        with path.open("rb") as f: digest=hashlib.file_digest(f,"sha256").hexdigest()
        print(name,digest)
    print("Modellordner:",root/"onnx"/"v2")
if __name__=="__main__":main()
