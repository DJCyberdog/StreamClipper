"""M18 account and publish-adapter preparation. No upload/publish implementation."""
from dataclasses import dataclass,field
from pathlib import Path
import base64,hashlib,hmac,json,re,secrets,time,webbrowser
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler
from .media import CancelledError
from .export_qa import read_report

YOUTUBE_SCOPE="https://www.googleapis.com/auth/youtube.upload"
AUTH="https://accounts.google.com/o/oauth2/v2/auth"
TOKEN="https://oauth2.googleapis.com/token"

@dataclass(frozen=True)
class Token:
    access:str=field(repr=False)
    refresh:str|None=field(default=None,repr=False)
    expires:float=0.
    scope:str=YOUTUBE_SCOPE

def pkce():
    verifier=secrets.token_urlsafe(64)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier,challenge

def callback_code(target,expected_state):
    p=urlsplit(target)
    if p.path!="/callback" or p.scheme or p.netloc:raise ValueError("OAuth-Callback ungültig")
    q=parse_qs(p.query,keep_blank_values=True)
    if len(q.get("state",[]))!=1 or not hmac.compare_digest(q["state"][0],expected_state):raise ValueError("OAuth-State ungültig")
    if q.get("error"):raise PermissionError("Autorisierung abgelehnt")
    if len(q.get("code",[]))!=1 or not 1<=len(q["code"][0])<=4096:raise ValueError("OAuth-Code ungültig")
    return q["code"][0]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def exchange(client_id,secret,code,verifier,redirect):
    data=urlencode(dict(client_id=client_id,client_secret=secret,code=code,code_verifier=verifier,
                         redirect_uri=redirect,grant_type="authorization_code")).encode()
    request=Request(TOKEN,data=data,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=20) as response:
            raw=response.read(65537)
        if len(raw)>65536:raise ValueError("Token-Antwort zu groß")
        doc=json.loads(raw)
        if doc.get("token_type","").lower()!="bearer" or YOUTUBE_SCOPE not in doc.get("scope","").split():raise ValueError("Scope fehlt")
        if not isinstance(doc.get("access_token"),str) or not 1<=len(doc["access_token"])<=8192:raise ValueError("Token fehlt")
        expires=int(doc["expires_in"])
        if not 0<expires<=86400:raise ValueError("Tokenablauf ungültig")
        return Token(doc["access_token"],doc.get("refresh_token"),time.time()+expires,doc["scope"])
    except Exception:raise RuntimeError("OAuth-Token-Austausch fehlgeschlagen") from None

def authorize_youtube(client_id,client_secret,*,authorized=False,cancelled=None,open_browser=webbrowser.open):
    if not authorized:raise ValueError("Explizite Kontofreigabe erforderlich")
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,150}\.apps\.googleusercontent\.com",client_id) or not 1<=len(client_secret)<=512:
        raise ValueError("Registrierte Desktop-App-Konfiguration erforderlich")
    verifier,challenge=pkce();state=secrets.token_urlsafe(32);result=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass # code/state never logged
        def do_GET(self):
            try:
                if self.headers.get("Host")!=f"127.0.0.1:{self.server.server_port}":raise ValueError
                code=callback_code(self.path,state);result.append((code,None))
                status=200;body=b"Authorization received. Return to StreamClipper."
            except PermissionError:
                result.append((None,"Authorization denied"));status=400;body=b"Authorization denied."
            except ValueError:
                status=400;body=b"Invalid callback."
            self.send_response(status);self.send_header("Content-Type","text/plain")
            self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    with HTTPServer(("127.0.0.1",0),Handler) as server:
        server.timeout=.25;redirect=f"http://127.0.0.1:{server.server_port}/callback"
        if cancelled and cancelled():raise CancelledError("OAuth abgebrochen")
        url=AUTH+"?"+urlencode(dict(client_id=client_id,redirect_uri=redirect,response_type="code",
                     scope=YOUTUBE_SCOPE,state=state,code_challenge=challenge,code_challenge_method="S256",
                     access_type="offline",prompt="consent"))
        if not open_browser(url):raise RuntimeError("Systembrowser konnte nicht geöffnet werden")
        deadline=time.monotonic()+180
        while not result:
            if cancelled and cancelled():raise CancelledError("OAuth abgebrochen")
            if time.monotonic()>deadline:raise RuntimeError("OAuth-Zeitlimit")
            server.handle_request()
        code,error=result[0]
    if error:raise RuntimeError(error)
    if cancelled and cancelled():raise CancelledError("OAuth abgebrochen")
    return exchange(client_id,client_secret,code,verifier,redirect)

@dataclass(frozen=True)
class PublishAsset:
    path:str
    sha256:str
    duration:float
    width:int
    height:int
    codec:str
    audio_codec:str|None
    fps:float
    rights:str
    @classmethod
    def from_export(cls,path,rights):
        from .media import probe_video
        p=Path(path).resolve(strict=True)
        if not rights.strip() or len(rights)>1000:raise ValueError("Rechtehinweis erforderlich")
        qa=read_report(p)
        digest=hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):digest.update(block)
        if qa.status!="PASS" or digest.hexdigest()!=qa.file_sha256 or p.stat().st_size!=qa.file_bytes:
            raise ValueError("Export ist nicht unverändert QA-validiert")
        info=probe_video(p)
        return cls(str(p),qa.file_sha256,qa.duration,qa.width,qa.height,qa.actual_codec,qa.audio_codec,info.fps,rights.strip())

PROVIDERS={
    "youtube":"OAuth desktop pilot; official registered client required",
    "tiktok":"BLOCKED: provider app approval / authorized redirect and scopes",
    "instagram":"BLOCKED: eligible professional account and approved app flow",
    "snapchat":"BLOCKED: Public Profile API approval"}
class PublishAdapter:
    """M19 must supply provider-specific methods. Base fails closed."""
    def authorize(self,*args,**kwargs):raise NotImplementedError("Provider authorization not available")
    def validate(self,*args,**kwargs):raise NotImplementedError("Provider asset validation not available")
    def upload(self,*args,**kwargs):raise NotImplementedError("M19 upload not implemented")
    def publish(self,*args,**kwargs):raise NotImplementedError("M19 publish not implemented")
    def status(self,*args,**kwargs):raise NotImplementedError("M19 status not implemented")
class YouTubePreparation(PublishAdapter):
    def authorize(self,*args,**kwargs):return authorize_youtube(*args,**kwargs)
