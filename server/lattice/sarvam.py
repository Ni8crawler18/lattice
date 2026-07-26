"""Thin Sarvam client shared by every Lattice layer."""

import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

_KEY_RE = re.compile(r'^\s*SARVAM_API_KEY\s*=\s*["\']?([^"\'\s]+)')


def _key() -> str:
    key = os.getenv("SARVAM_API_KEY")
    if key:
        return key.strip().strip('"').strip("'")
    # .env here is written as KEY = "value"; dotenv handles it, but be defensive
    # so the server still boots if the file is edited by hand at 3am.
    try:
        with open(".env") as fh:
            for line in fh:
                m = _KEY_RE.match(line)
                if m:
                    return m.group(1)
    except FileNotFoundError:
        pass
    raise RuntimeError("SARVAM_API_KEY not found in environment or .env")


@lru_cache(maxsize=1)
def client() -> SarvamAI:
    return SarvamAI(api_subscription_key=_key())


CHAT_MODEL = "sarvam-105b"


def chat(messages, temperature: float = 0.1) -> str:
    """Chat completion -> raw assistant text."""
    resp = client().chat.completions(
        model=CHAT_MODEL,
        messages=messages,
        temperature=temperature,
    )
    # SDK returns an object; fall back to dict access across versions.
    try:
        return resp.choices[0].message.content
    except AttributeError:
        return resp["choices"][0]["message"]["content"]


def identify_language(text: str) -> dict:
    r = client().text.identify_language(input=text)
    try:
        return {"language_code": r.language_code, "script_code": r.script_code}
    except AttributeError:
        return {"language_code": r.get("language_code"), "script_code": r.get("script_code")}


STT_URL = "https://api.sarvam.ai/speech-to-text"
STT_MODEL = "saaras:v3"


def transcribe(audio: bytes, content_type: str = "audio/webm") -> dict:
    """Speech -> text via Saaras. Auto-detects language; addresses arrive
    spoken in Hinglish/Hindi/Tamil, so no language is assumed."""
    import httpx

    ext = (content_type.split("/")[-1] or "webm").split(";")[0]
    r = httpx.post(
        STT_URL,
        headers={"api-subscription-key": _key()},
        data={"model": STT_MODEL, "language_code": "unknown"},
        files={"file": (f"audio.{ext}", audio, content_type)},
        timeout=60.0,
    )
    if 400 <= r.status_code < 500:
        # Sarvam's body says WHY (verified: undecodable bytes -> 400
        # "Failed to read the file"); don't bury it in a bare status line.
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:200]
        raise ValueError(f"Sarvam rejected the audio ({r.status_code}): {msg}")
    r.raise_for_status()
    d = r.json()
    return {
        "transcript": d.get("transcript", ""),
        "language_code": d.get("language_code"),
        "language_probability": d.get("language_probability"),
    }


def transliterate(text: str, source: str, target: str = "en-IN") -> str:
    r = client().text.transliterate(
        input=text,
        source_language_code=source,
        target_language_code=target,
        spoken_form=False,
    )
    try:
        return r.transliterated_text
    except AttributeError:
        return r.get("transliterated_text", text)
