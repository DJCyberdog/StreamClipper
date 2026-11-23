"""Progress tracking for explicit Hugging Face model provisioning.

Only network byte counters can produce determinate percentages. Tqdm's
"Fetching files" and reconstruction counters are NOT download progress.
"""
from __future__ import annotations

import math
import threading
from typing import Callable

from .media import CancelledError

# percent=None signals indeterminate activity (not a fictitious 0%).
ProgressEvent = Callable[[int | None, int, int | None, str], None]


class ModelDownloadProgress:
    def __init__(self, notify: ProgressEvent,
                 cancelled: Callable[[], bool] | None = None) -> None:
        self.notify = notify
        self.cancelled = cancelled
        self._lock = threading.Lock()
        self.total: int | None = None
        self.transferred = 0
        self._aggregated = False
        self._seen_transfer = False

    def _guard(self) -> None:
        if self.cancelled and self.cancelled():
            raise CancelledError("Modelldownload abgebrochen")

    def report(self, stage: str) -> None:
        self._guard()
        with self._lock:
            total = self.total
            done = self.transferred
        percent = min(99, done * 100 // total) if total and done else None
        if percent == 0:
            percent = None  # under 1 %: show activity, not a stalled 0 %
        self.notify(percent, done, total, stage)

    def set_total(self, total: int | None) -> None:
        """Only use total from complete per-file *byte* sizes, never file count."""
        self._guard()
        if total is not None and (not isinstance(total, int) or total <= 0):
            total = None
        with self._lock:
            self.total = total
        self.report("download")

    def add(self, delta: int, *, channel: str) -> None:
        """Aggregate modern snapshot transfer bytes, or legacy file bytes."""
        self._guard()
        if channel not in {"transfer", "file"} or delta <= 0:
            return
        with self._lock:
            if channel == "transfer":
                if not self._seen_transfer:
                    self._seen_transfer = True
                    self.transferred = 0  # no double count with older per-file bars
                self._aggregated = True
            elif self._aggregated:
                return
            self.transferred += delta
        self.report("download")

    def finish(self) -> None:
        self._guard()
        with self._lock:
            done, total = self.transferred, self.total
        # 100% only after validate_model_dir passed.
        self.notify(100, done, total, "complete")

    def tqdm_class(self):
        """A per-job subclass, never global monkeypatching tqdm or HF logging."""
        try:
            from tqdm.auto import tqdm
        except ImportError as exc:
            raise RuntimeError('Modell-Setup fehlt: pip install -e ".[models]"') from exc

        tracker = self

        class TrackedTqdm(tqdm):
            def __init__(self, *args, **kwargs):
                name = str(kwargs.get("name") or "")
                unit = kwargs.get("unit")
                self._channel = (
                    "transfer" if unit == "B" and name.endswith(".transfer")
                    else "ignore" if (name.endswith(".snapshot_download")
                                       or "reconstruct" in name.lower()
                                       or unit != "B")
                    else "file"
                )
                super().__init__(*args, **kwargs)

            def update(self, n=1):
                tracker._guard()
                before = self.n
                result = super().update(n)
                if self._channel != "ignore":
                    delta = max(0, int(self.n - before))
                    tracker.add(delta, channel=self._channel)
                return result

        return TrackedTqdm


def format_bytes(amount: int) -> str:
    if amount < 1024:
        return f"{amount} B"
    if amount < 1024 ** 2:
        return f"{amount / 1024:.1f} KiB"
    if amount < 1024 ** 3:
        return f"{amount / 1024 ** 2:.1f} MiB"
    return f"{amount / 1024 ** 3:.2f} GiB"
