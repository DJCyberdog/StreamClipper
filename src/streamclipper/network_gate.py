"""HTTPS CONNECT gate for trusted yt-dlp workers. Public DNS only, pinned sockets.
Not an OS sandbox. Native downloader only; no browser cookies or remote scripts.
"""
import ipaddress,socket,socketserver,select,threading
from contextlib import contextmanager

def public_addresses(host,port=443,resolver=socket.getaddrinfo):
    if port!=443 or not host or "%" in host:raise ValueError("HTTPS port 443 required")
    rows=resolver(host,port,type=socket.SOCK_STREAM)
    if not rows:raise ValueError("DNS empty")
    for family,kind,proto,_,address in rows:
        ip=ipaddress.ip_address(address[0])
        mapped=getattr(ip,"ipv4_mapped",None)
        if not ip.is_global or ip.is_multicast or (mapped and not mapped.is_global):
            raise ValueError("Private or non-public network address")
    return rows

class Gate(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,budget):
        super().__init__(("127.0.0.1",0),Tunnel)
        self.budget=budget;self.used=0;self.lock=threading.Lock();self.stop=threading.Event()
    def consume(self,n):
        with self.lock:
            self.used+=n
            if self.used>self.budget:self.stop.set();raise ValueError("Transfer limit")

class Tunnel(socketserver.StreamRequestHandler):
    def handle(self):
        remote=None
        try:
            self.request.settimeout(15)
            line=self.rfile.readline(8192).decode("ascii").strip().split()
            if len(line)!=3 or line[0]!="CONNECT":raise ValueError("HTTPS CONNECT only")
            host,sep,port=line[1].rpartition(":")
            if not sep or port!="443":raise ValueError("Port")
            for i in range(64):
                header=self.rfile.readline(8192)
                if header in (b"\r\n",b"\n"):break
                if not header or len(header)>=8192:raise ValueError("Headers")
            else:raise ValueError("Headers")
            for family,kind,proto,_,addr in public_addresses(host.strip("[]")):
                sock=socket.socket(family,kind,proto);sock.settimeout(15)
                try:sock.connect(addr);remote=sock;break
                except OSError:sock.close()
            if remote is None:raise OSError("Connection failed")
            self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n");self.wfile.flush()
            while not self.server.stop.is_set():
                ready,_,_=select.select([self.request,remote],[],[],1)
                for peer in ready:
                    data=peer.recv(65536)
                    if not data:return
                    if peer is remote:self.server.consume(len(data))
                    (self.request if peer is remote else remote).sendall(data)
        except (OSError,ValueError,UnicodeError):
            if remote is None:
                try:self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                except OSError:pass
        finally:
            if remote is not None:remote.close()

@contextmanager
def guarded_proxy(budget):
    server=Gate(budget)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f"http://127.0.0.1:{server.server_address[1]}",server
    finally:
        server.stop.set();server.shutdown();server.server_close();thread.join(2)
