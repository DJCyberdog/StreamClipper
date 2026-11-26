"""Thread-local notification of the actual vision inference device."""
from contextvars import ContextVar
from typing import Callable
import logging

device_notice: ContextVar[Callable[[str],None] | None] = ContextVar("vision_device_notice",default=None)

def report_vision_device(label, device):
    message=f"{label}: {'GPU / CUDA' if str(device).startswith('cuda') else 'CPU (keine CUDA-Inferenz)'}"
    logging.getLogger(__name__).info(message)
    print(message,flush=True)
    callback=device_notice.get()
    if callback is not None:callback(message)
