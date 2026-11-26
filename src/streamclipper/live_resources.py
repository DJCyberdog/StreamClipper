"""Read-only system telemetry; no model imports or GPU context creation."""
import math
import os
import shutil
import subprocess
from pathlib import Path

def _number(value):
    try:v=float(value)
    except (TypeError,ValueError):return None
    return v if math.isfinite(v) and v>=0 else None

def parse_nvidia(raw):
    rows=[]
    for line in raw.splitlines():
        parts=[v.strip() for v in line.split(",")]
        if len(parts)!=6:continue
        name=parts[0];gpu,used,total,dec,enc=map(_number,parts[1:])
        if not name:continue
        rows.append({"name":name,"gpu":gpu,"vram_used_mib":used,"vram_total_mib":total,
                     "decode":dec,"encode":enc})
    return rows

def sample():
    result={"cpu":None,"ram_used":None,"ram_total":None,"process_ram":None,"gpus":[]}
    try:
        import psutil
        ram=psutil.virtual_memory()
        result.update(cpu=psutil.cpu_percent(interval=None),ram_used=ram.total-ram.available,
                      ram_total=ram.total,process_ram=psutil.Process().memory_info().rss)
    except (ImportError,OSError):pass
    tool=shutil.which("nvidia-smi")
    if not tool and os.name=="nt":
        candidate=Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32"/"nvidia-smi.exe"
        if candidate.is_file():tool=str(candidate)
    if tool:
        try:
            cmd=[tool,"--query-gpu=name,utilization.gpu,memory.used,memory.total,utilization.decoder,utilization.encoder",
                 "--format=csv,noheader,nounits"]
            output=subprocess.run(cmd,capture_output=True,text=True,timeout=2,check=True,
                     creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            result["gpus"]=parse_nvidia(output.stdout)
        except (OSError,subprocess.SubprocessError):pass
    return result

def format_sample(row):
    def percent(value):return "n/a" if value is None else f"{value:.0f}%"
    def memory(used,total,unit):
        if used is None or total is None:return "n/a"
        return f"{used/unit:.1f}/{total/unit:.1f} GiB"
    cpu=f"CPU {percent(row['cpu'])} | RAM {memory(row['ram_used'],row['ram_total'],1024**3)}"
    gpu=[]
    for g in row["gpus"]:
        gpu.append(f"{g['name']}: GPU {percent(g['gpu'])} | VRAM {memory(g['vram_used_mib'],g['vram_total_mib'],1024)}"
                   f" | Decode {percent(g['decode'])} | Encode {percent(g['encode'])}")
    return cpu, " · ".join(gpu) if gpu else "NVIDIA-GPU-Telemetrie: n/a"
