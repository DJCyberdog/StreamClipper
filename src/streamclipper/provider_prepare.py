"""Provider-specific preparation, without transmitting media.
TikTok desktop PKCE uses hex SHA-256, unlike Google's base64url challenge.
Confidential-client token exchange belongs to an approved backend; this
module provides the request contract, not an embedded distribution secret.
"""
from dataclasses import dataclass,field
from urllib.parse import urlencode,urlsplit,parse_qs
import hashlib,hmac,secrets,re,math,time
from .publish_prepare import PublishAdapter,PublishAsset,Token

TIKTOK_AUTH="https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN="https://open.tiktokapis.com/v2/oauth/token/"
SCOPES={"video.upload","video.publish"}

@dataclass(frozen=True)
class TikTokGrant:
    client_key:str
    redirect:str
    scope:str
    state:str=field(repr=False)
    verifier:str=field(repr=False)
    def url(self):
        return TIKTOK_AUTH+"?"+urlencode(dict(client_key=self.client_key,redirect_uri=self.redirect,
            scope=self.scope,response_type="code",state=self.state,code_challenge_method="S256",
            code_challenge=hashlib.sha256(self.verifier.encode("ascii")).hexdigest()))
    def callback(self,target):
        p=urlsplit(target);expected=urlsplit(self.redirect)
        if (p.scheme,p.netloc,p.path)!=(expected.scheme,expected.netloc,expected.path):raise ValueError("Invalid redirect")
        q=parse_qs(p.query,keep_blank_values=True)
        if len(q.get("state",[]))!=1 or not hmac.compare_digest(q["state"][0],self.state):raise ValueError("Invalid state")
        if q.get("error"):raise PermissionError("Authorization denied")
        if len(q.get("code",[]))!=1 or not 1<=len(q["code"][0])<=4096:raise ValueError("Invalid code")
        if set(q.get("scopes",[""])[0].split(","))!={self.scope}:raise PermissionError("Requested scope not granted")
        return q["code"][0]
    def exchange_fields(self,code):
        # Confidential client secret is added only by the approved backend.
        if not isinstance(code,str) or not 1<=len(code)<=4096:raise ValueError("Invalid code")
        return dict(client_key=self.client_key,code=code,redirect_uri=self.redirect,
                    grant_type="authorization_code",code_verifier=self.verifier)

def prepare_tiktok(client_key,redirect,scope="video.upload",*,authorized=False):
    if not authorized:raise ValueError("Explicit authorization required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,128}",client_key) or scope not in SCOPES:raise ValueError("Invalid client/scope")
    p=urlsplit(redirect)
    if p.scheme not in ("http","https") or p.hostname!="127.0.0.1" or not p.port or p.username or p.password or p.query or p.fragment or p.path!="/callback/":
        raise ValueError("Registered loopback redirect required")
    return TikTokGrant(client_key,redirect,scope,secrets.token_urlsafe(32),secrets.token_urlsafe(64))

def parse_tiktok_token(doc,scope,now=None):
    if scope not in SCOPES or doc.get("error") or doc.get("token_type","").lower()!="bearer" or set(doc.get("scope","").split(","))!={scope}:
        raise PermissionError("Token scope not granted")
    access=doc.get("access_token");refresh=doc.get("refresh_token");expires=doc.get("expires_in")
    if not isinstance(access,str) or not 1<=len(access)<=8192 or not isinstance(refresh,str) or not 1<=len(refresh)<=8192 or type(expires) is not int or not 0<expires<=86400:
        raise ValueError("Invalid token response")
    return Token(access,refresh,(time.time() if now is None else now)+expires,scope)

class TikTokPreparation(PublishAdapter):
    def authorize(self,*args,**kwargs):
        # Returns an ephemeral grant, not a connected account.
        return prepare_tiktok(*args,**kwargs)
    def validate(self,asset):
        if not isinstance(asset,PublishAsset):raise TypeError("QA asset required")
        fresh=PublishAsset.from_export(asset.path,asset.rights)
        if fresh!=asset:raise ValueError("Asset changed")
        if asset.codec not in ("h264","hevc") or not 23<=asset.fps<=60 or not 360<=asset.width<=4096 or not 360<=asset.height<=4096 or not 0<asset.duration<=600:
            raise ValueError("TikTok preliminary video constraints")
        from pathlib import Path
        if Path(asset.path).stat().st_size>4_000_000_000:raise ValueError("TikTok size limit")
        return True

# Registration status is an external gate, not something a local adapter can assert.
PROVIDER_GATES={
 "youtube":("registered desktop client","actual account/API verification"),
 "tiktok":("registered Login Kit and Content Posting scope","approved confidential token backend","provider audit"),
 "instagram":("eligible professional account","approved Instagram Business Login and confidential backend"),
 "snapchat":("Public Profile API allowlist","approved OAuth application and confidential backend"),
}

def retry_decision(operation,status,*,attempt,ambiguous=False,retry_after=None):
    """Only retry read-only checks automatically; ambiguous writes require reconciliation."""
    if operation not in ("authorize","validate","upload","publish","status") or type(attempt) is not int or attempt<0:raise ValueError("Invalid retry state")
    if ambiguous and operation in ("upload","publish"):return ("RECONCILE",None)
    if status in (401,403):return ("REQUIRES_ACTION",None)
    if operation not in ("validate","status"):return ("REQUIRES_ACTION",None)
    if status in (429,500,502,503,504) and attempt<4:
        delay=min(60,2**attempt)
        if isinstance(retry_after,(int,float)) and math.isfinite(retry_after) and retry_after>=0:delay=min(300,max(delay,retry_after))
        return ("RETRY",delay)
    return ("FAILED",None)

def operation_key(provider,account,asset,metadata_hash):
    if provider not in PROVIDER_GATES or not isinstance(account,str) or not 1<=len(account)<=256 or not isinstance(asset,PublishAsset) or not re.fullmatch(r"[0-9a-f]{64}",metadata_hash):
        raise ValueError("Invalid operation identity")
    # Local dedup identity; no claim that providers honor an idempotency header.
    return hashlib.sha256(("\0".join((provider,account,asset.sha256,metadata_hash))).encode()).hexdigest()


# Confidential web-app grants. No app secret or provider token belongs in
# the portable client. The registered backend owns the state and exchange.
WEB_PROVIDERS={
    "instagram":{"authorize":"https://www.instagram.com/oauth/authorize",
        "token":"https://api.instagram.com/oauth/access_token",
        "scopes":("instagram_business_basic","instagram_business_content_publish"),
        "delimiter":","},
    "snapchat":{"authorize":"https://accounts.snapchat.com/login/oauth2/authorize",
        "token":"https://accounts.snapchat.com/login/oauth2/token",
        "scopes":("snapchat-profile-api",),"delimiter":" "},
}
@dataclass(frozen=True)
class WebGrant:
    provider:str
    client_id:str
    redirect:str
    state:str=field(repr=False)
    expires:float=0.
    def url(self):
        cfg=WEB_PROVIDERS[self.provider]
        return cfg["authorize"]+"?"+urlencode(dict(client_id=self.client_id,
            redirect_uri=self.redirect,response_type="code",
            scope=cfg["delimiter"].join(cfg["scopes"]),state=self.state))
    def callback(self,target,now=None):
        if (time.time() if now is None else now)>=self.expires:raise PermissionError("Authorization request expired")
        p=urlsplit(target);expected=urlsplit(self.redirect)
        if (p.scheme,p.netloc,p.path)!=(expected.scheme,expected.netloc,expected.path):
            raise ValueError("Invalid redirect")
        if p.fragment not in ("","_"):raise ValueError("Invalid redirect fragment")
        q=parse_qs(p.query,keep_blank_values=True)
        if len(q.get("state",[]))!=1 or not hmac.compare_digest(q["state"][0],self.state):
            raise ValueError("Invalid state")
        if q.get("error"):raise PermissionError("Authorization denied")
        if len(q.get("code",[]))!=1 or not 1<=len(q["code"][0])<=4096:raise ValueError("Invalid code")
        return q["code"][0]
    def exchange_fields(self,code):
        if not isinstance(code,str) or not 1<=len(code)<=4096:raise ValueError("Invalid code")
        return {"client_id":self.client_id,"redirect_uri":self.redirect,"grant_type":"authorization_code","code":code}

def prepare_web_grant(provider,client_id,redirect,*,authorized=False,now=None):
    if not authorized:raise PermissionError("Explicit authorization required")
    if provider not in WEB_PROVIDERS:raise ValueError("Unsupported provider")
    if not isinstance(client_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{5,128}",client_id):
        raise ValueError("Invalid app ID")
    if provider=="instagram" and not client_id.isascii() or provider=="instagram" and not client_id.isdecimal():
        raise ValueError("Instagram app ID must be numeric")
    p=urlsplit(redirect)
    if p.scheme!="https" or not p.hostname or p.username or p.password or p.port not in (None,443) or p.query or p.fragment or not p.path.startswith("/"):
        raise ValueError("Registered HTTPS backend redirect required")
    # Do not open the browser or exchange the code in this preparation API.
    return WebGrant(provider,client_id,redirect,secrets.token_urlsafe(32),(time.time() if now is None else now)+600)

def parse_instagram_grant(doc):
    """Validate the documented short-lived grant; permissions must be explicit."""
    rows=doc.get("data")
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):raise ValueError("Invalid Instagram grant")
    row=rows[0];permissions=row.get("permissions")
    scopes=set(permissions.split(",")) if isinstance(permissions,str) else set(permissions or ())
    if not set(WEB_PROVIDERS["instagram"]["scopes"]).issubset(scopes):raise PermissionError("Publishing permissions missing")
    token=row.get("access_token");uid=str(row.get("user_id",""))
    if not isinstance(token,str) or not 1<=len(token)<=8192 or not re.fullmatch(r"[0-9]{1,40}",uid):raise ValueError("Invalid Instagram grant")
    # Token response does not provide an exact expiry here. Do not invent one.
    return uid,Token(token,None,0.,",".join(WEB_PROVIDERS["instagram"]["scopes"]))

def parse_snapchat_grant(doc,now=None):
    if doc.get("error") or doc.get("token_type","").lower()!="bearer" or set(doc.get("scope","").split())!={"snapchat-profile-api"}:
        raise PermissionError("Public Profile scope missing")
    access=doc.get("access_token");refresh=doc.get("refresh_token");expires=doc.get("expires_in")
    if not isinstance(access,str) or not 1<=len(access)<=8192 or not isinstance(refresh,str) or not 1<=len(refresh)<=8192 or type(expires) is not int or not 0<expires<=86400:
        raise ValueError("Invalid Snapchat grant")
    return Token(access,refresh,(time.time() if now is None else now)+expires,"snapchat-profile-api")

class InstagramPreparation(PublishAdapter):
    def authorize(self,client_id,redirect,**kwargs):
        return prepare_web_grant("instagram",client_id,redirect,**kwargs)

class SnapchatPreparation(PublishAdapter):
    def authorize(self,client_id,redirect,**kwargs):
        return prepare_web_grant("snapchat",client_id,redirect,**kwargs)
