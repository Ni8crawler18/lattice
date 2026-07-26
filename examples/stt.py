#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-96cn.onrender.com/stt/parse \\
      -H 'Content-Type: audio/wav' \\
      -H "X-API-Key: $LATTICE_KEY" \\
      --data-binary @spoken_address.wav

Speak an address, get the same JSON as POST /parse, plus `transcript` and
`spoken_language`.

Usage:
    python3 examples/stt.py <audio-file>               # wav, mp3, ogg, webm, m4a...
    python3 examples/stt.py <audio-file> ltk_yourkey https://your-api

Key defaults to $LATTICE_KEY and is minted automatically if unset.
"""

import json
import os
import sys
import urllib.request

if len(sys.argv) < 2:
    sys.exit("usage: python3 examples/stt.py <audio-file> [key] [api-url]")

audio_path = sys.argv[1]
key = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("LATTICE_KEY", "")
url = (sys.argv[3] if len(sys.argv) > 3 else
       os.environ.get("LATTICE_API", "https://lattice-api-96cn.onrender.com")).rstrip("/")

with open(audio_path, "rb") as fh:
    audio = fh.read()
content_type = "audio/" + audio_path.rsplit(".", 1)[-1].lower()

if not key:  # self-service: mint one (shown once -- save it)
    req = urllib.request.Request(
        url + "/keys", data=json.dumps({"name": "stt-example"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        key = json.load(r)["api_key"]
    print(f"minted key (save it):  export LATTICE_KEY={key}\n", file=sys.stderr)

req = urllib.request.Request(
    url + "/stt/parse", data=audio,
    headers={"Content-Type": content_type, "X-API-Key": key})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), ensure_ascii=False, indent=2))
