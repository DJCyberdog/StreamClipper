"""Optional Windows Credential Manager vault for publishing tokens."""
import ctypes,hashlib,json,re
from dataclasses import asdict
from .hf_credentials import (_api,CREDENTIALW,CRED_TYPE_GENERIC,CRED_PERSIST_LOCAL_MACHINE,supported)
from .publish_prepare import Token,YOUTUBE_SCOPE

def target(client_id):
    if not isinstance(client_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{5,150}\.apps\.googleusercontent\.com",client_id):
        raise ValueError("Ungültige Desktop-Client-ID")
    return "StreamClipper/Publishing/YouTube/"+hashlib.sha256(client_id.encode()).hexdigest()

def save(client_id,token):
    if not isinstance(token,Token) or token.scope!=YOUTUBE_SCOPE:raise ValueError("Ungültiger Token")
    api=_api();name=target(client_id)
    encoded=json.dumps(asdict(token),ensure_ascii=True).encode("utf-8")
    # Windows generic credential blobs have a small size limit.
    if not 1<=len(encoded)<=2560:raise ValueError("Token zu groß für Windows Credential Manager; Sitzung verwenden")
    blob=ctypes.create_string_buffer(encoded)
    cred=CREDENTIALW();cred.Type=CRED_TYPE_GENERIC;cred.TargetName=name
    cred.Persist=CRED_PERSIST_LOCAL_MACHINE;cred.UserName="StreamClipper"
    cred.CredentialBlobSize=len(encoded);cred.CredentialBlob=ctypes.cast(blob,ctypes.POINTER(ctypes.c_ubyte))
    try:
        if not api.CredWriteW(ctypes.byref(cred),0):raise OSError("Sicherer Tokenspeicher nicht verfügbar")
    finally:ctypes.memset(ctypes.addressof(blob),0,len(blob))

def read(client_id):
    api=_api();cred=ctypes.POINTER(CREDENTIALW)()
    if not api.CredReadW(target(client_id),CRED_TYPE_GENERIC,0,ctypes.byref(cred)):return None
    try:
        size=cred.contents.CredentialBlobSize
        if not 1<=size<=2560:return None
        doc=json.loads(ctypes.string_at(cred.contents.CredentialBlob,size))
        token=Token(**doc)
        return token if token.scope==YOUTUBE_SCOPE else None
    except (ValueError,TypeError,UnicodeError):return None
    finally:api.CredFree(ctypes.cast(cred,ctypes.c_void_p))

def remove(client_id):
    _api().CredDeleteW(target(client_id),CRED_TYPE_GENERIC,0)
