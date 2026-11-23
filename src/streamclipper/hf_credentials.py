"""Optional Windows Credential Manager persistence for Hugging Face tokens.

Session-only is the default on every platform. We never write secrets to
StreamClipper JSON, environment variables, command lines or debug logs.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

TARGET = "StreamClipper/HuggingFaceReadToken"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def supported() -> bool:
    return os.name == "nt"


def _api():
    if not supported():
        raise RuntimeError("Sichere dauerhafte Speicherung nur unter Windows verfügbar")
    advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    advapi.CredDeleteW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi.CredDeleteW.restype = wintypes.BOOL
    return advapi


def save_token(token: str) -> None:
    if not isinstance(token, str) or not token.startswith("hf_") or len(token) > 4096:
        raise ValueError("Kein gültiges Hugging-Face-Tokenformat")
    api = _api()
    encoded = token.encode("utf-16-le")
    blob = ctypes.create_string_buffer(encoded)
    cred = CREDENTIALW()
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = TARGET
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = "StreamClipper"
    cred.CredentialBlobSize = len(encoded)
    cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    try:
        if not api.CredWriteW(ctypes.byref(cred), 0):
            raise OSError("Windows Credential Manager: Speichern fehlgeschlagen")
    finally:
        ctypes.memset(ctypes.addressof(blob), 0, len(blob))


def read_token() -> str | None:
    api = _api()
    credential = ctypes.POINTER(CREDENTIALW)()
    if not api.CredReadW(TARGET, CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
        return None
    try:
        size = credential.contents.CredentialBlobSize
        if size <= 0 or size > 8192 or size % 2:
            return None
        data = ctypes.string_at(credential.contents.CredentialBlob, size)
        value = data.decode("utf-16-le")
        return value if value.startswith("hf_") else None
    finally:
        api.CredFree(ctypes.cast(credential, ctypes.c_void_p))


def remove_token() -> None:
    api = _api()
    # Missing credentials are normal; clearing a session twice must be safe.
    api.CredDeleteW(TARGET, CRED_TYPE_GENERIC, 0)
