"""Optional local process-tree RSS and NVIDIA process VRAM telemetry.

RSS is sampled and can double-count shared mappings. nvidia-smi WDDM may not
provide process VRAM. Missing measurements are None, never zero by default.
"""
from threading import Event,Thread
import os
import shutil
import subprocess

class ResourceSampler:
    def __init__(self):
        self.peak_ram_bytes=None;self.peak_vram_bytes=None;self.samples=0
        self.stop=Event();self.worker=None
    def sample(self):
        pids={os.getpid()}
        try:
            import psutil
            process=psutil.Process()
            processes=[process,*process.children(recursive=True)]
            rss=0
            for p in processes:
                pids.add(p.pid)
                try:rss+=p.memory_info().rss
                except (psutil.NoSuchProcess,psutil.AccessDenied):continue
            self.peak_ram_bytes=max(self.peak_ram_bytes or 0,rss)
        except (ImportError,OSError):pass
        tool=shutil.which("nvidia-smi")
        if tool:
            try:
                output=subprocess.run([tool,"--query-compute-apps=pid,used_memory","--format=csv,noheader,nounits"],
                    capture_output=True,text=True,check=True,timeout=3).stdout
                rows=[]
                for line in output.splitlines():
                    pair=line.split(",")
                    if len(pair)!=2:continue
                    pid,mem=(part.strip() for part in pair)
                    if pid.isdigit() and int(pid) in pids and mem.isdigit():rows.append(int(mem)*1024**2)
                if rows:self.peak_vram_bytes=max(self.peak_vram_bytes or 0,sum(rows))
            except (OSError,subprocess.SubprocessError):pass
        self.samples+=1
    def _run(self):
        while not self.stop.is_set():
            self.sample()
            self.stop.wait(1.)
    def __enter__(self):
        self.sample()
        self.worker=Thread(target=self._run,daemon=True)
        self.worker.start();return self
    def __exit__(self,*exc):
        self.stop.set()
        if self.worker:self.worker.join(timeout=5)
        if self.worker and self.worker.is_alive():raise RuntimeError("Ressourcenmessung nicht beendet")
        self.sample()
    def report(self):
        return {"peak_ram_bytes":self.peak_ram_bytes,"peak_vram_bytes":self.peak_vram_bytes,
                "resource_samples":self.samples,"resource_measurement":"sampled process tree RSS and NVIDIA compute process memory"}
