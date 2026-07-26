#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-96cn.onrender.com/stt/parse \\
      -H 'Content-Type: audio/wav' \\
      -H "X-API-Key: $LATTICE_KEY" \\
      --data-binary @spoken_address.wav

Speak an address; get the same JSON as /parse, plus `transcript` and
`spoken_language`.  Get a key first:  ./examples/createkey.sh
"""

import json
import urllib.request

URL = "https://lattice-api-96cn.onrender.com"
KEY = ""
AUDIO = input("Audio file path (wav/mp3/ogg/webm): ").strip()

req = urllib.request.Request(
    URL.rstrip("/") + "/stt/parse",
    data=open(AUDIO, "rb").read(),
    headers={"Content-Type": "audio/" + AUDIO.rsplit(".", 1)[-1].lower(),
             "X-API-Key": KEY})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), ensure_ascii=False, indent=2))
