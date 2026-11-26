"""Isolated Python worker: deny direct sockets and non-media child processes.

Audit hooks add defense in depth for trusted Python downloader code. Native
extensions and FFmpeg are not an OS sandbox; never load plugins or JS here.
"""
import os,sys,socket,shutil
from pathlib import Path
from urllib.parse import urlsplit

def guard(proxy,ffmpeg,ffprobe):
    p=urlsplit(proxy)
    if p.scheme!="http" or p.hostname!="127.0.0.1" or not p.port:raise ValueError("Invalid proxy")
    allowed={os.path.normcase(str(Path(x).resolve())) for x in (ffmpeg,ffprobe)}
    def audit(event,args):
        if event in ("socket.connect","socket.sendto"):
            address=args[1]
            if not isinstance(address,tuple) or address[:2]!=("127.0.0.1",p.port):
                raise PermissionError("Direct network access denied")
        elif event=="socket.getaddrinfo":
            if args[0] not in ("127.0.0.1",b"127.0.0.1",None):
                raise PermissionError("Direct DNS denied")
        elif event in ("socket.gethostbyname","socket.gethostbyaddr"):
            if args[0] not in ("127.0.0.1",b"127.0.0.1"):
                raise PermissionError("Direct DNS denied")
        elif event=="subprocess.Popen":
            executable,argv,_,_=args
            path=shutil.which(os.fsdecode(executable)) or os.fsdecode(executable)
            if os.path.normcase(str(Path(path).resolve())) not in allowed:
                raise PermissionError("External downloader denied")
            if not isinstance(argv,(tuple,list)):raise PermissionError("Shell denied")
            for i,arg in enumerate(argv):
                if not isinstance(arg,str):raise PermissionError("Invalid media command")
                if i and ("://" in arg or arg.startswith(("concat:","subfile:","crypto:","data:","tcp:","udp:"))):
                    raise PermissionError("Remote media child input denied")
        elif event in ("os.system","os.exec","os.posix_spawn"):
            raise PermissionError("External execution denied")
    return audit

def main():
    if len(sys.argv)<5:raise SystemExit(2)
    proxy,ffmpeg,ffprobe=sys.argv[1:4];args=sys.argv[4:]
    import yt_dlp
    sys.addaudithook(guard(proxy,ffmpeg,ffprobe))
    yt_dlp.main(args)
if __name__=="__main__":main()
