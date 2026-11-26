"""Execute real PyTorch and TorchVision CUDA kernels, optionally with Whisper."""
from __future__ import annotations
import argparse
from streamclipper.portable import configure_portable_environment

def torch_test():
    import torch
    import torchvision
    print("PyTorch:", torch.__version__, "| TorchVision:", torchvision.__version__)
    print("CUDA-Build:", torch.version.cuda)
    if not torch.version.cuda or not torch.cuda.is_available():
        raise RuntimeError("PyTorch-CUDA nicht verfügbar (CPU-Build oder Treiberproblem).")
    print("GPU:", torch.cuda.get_device_name(0), "| Compute:", torch.cuda.get_device_capability(0))
    # Matrix multiply, convolution and torchvision CUDA operator.
    with torch.inference_mode():
        x=torch.ones((32,32),device="cuda")
        y=x@x
        assert y.is_cuda and float(y[0,0])==32
        z=torch.nn.Conv2d(3,4,3).cuda()(torch.ones((1,3,32,32),device="cuda"))
        assert z.is_cuda and bool(torch.isfinite(z).all())
        boxes=torch.tensor([[0.,0.,10.,10.],[1.,1.,9.,9.]],device="cuda")
        keep=torchvision.ops.nms(boxes,torch.tensor([.9,.8],device="cuda"),.5)
        assert keep.is_cuda and keep.numel()==1
        torch.cuda.synchronize()
    print("PASS: PyTorch- und TorchVision-CUDA-Kernel ausgeführt.")

def main():
    configure_portable_environment()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined",choices=("whisper-first","torch-first"))
    args=parser.parse_args()
    try:
        if args.combined=="whisper-first":
            from check_gpu_runtime import main as whisper_test
            if whisper_test()!=0:return 1
        torch_test()
        if args.combined=="torch-first":
            from check_gpu_runtime import main as whisper_test
            if whisper_test()!=0:return 1
            # Verify torch still works after loading the CTranslate2 stack.
            torch_test()
        return 0
    except Exception as exc:
        print(f"PyTorch-CUDA-Test fehlgeschlagen: {type(exc).__name__}: {exc}")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
