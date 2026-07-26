"""Lattice MCP server -- Indian Address Intelligence for agents.

Bridges MCP tools to the Lattice REST API (local or deployed), so any
MCP-capable agent (Claude Code, Cursor, ...) can parse, resolve, dedupe and
score Indian addresses.

Run:
    LATTICE_API=http://127.0.0.1:8077 python -m server.lattice_mcp

Register (Claude Code):
    claude mcp add lattice \
      --env LATTICE_API=<api-url> --env LATTICE_KEY=<ltk_key> \
      -- <venv>/bin/python -m server.lattice_mcp

Auth: requests carry X-API-Key from LATTICE_KEY (or, when run inside this
repo, the .env master key) -- mint one via POST /keys.

Design notes:
- Dependencies: the `mcp` SDK + httpx (async client -- required, see _call).
- Tools mirror the public API 1:1 and return the API's JSON verbatim --
  no reshaping, so tool output always matches the OpenAPI schema at /docs.
- Text -> DIGIPIN is NOT offered: DIGIPIN tools take coordinates, per the
  project's claims discipline.
"""

import json
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

API = os.environ.get("LATTICE_API", "http://127.0.0.1:8077").rstrip("/")

# The SDK's DNS-rebinding protection rejects any Host it doesn't know
# (421 Invalid Host header). That default only lists localhost, which
# breaks the deployed endpoint -- so allow localhost AND the public host.
# Render sets RENDER_EXTERNAL_HOSTNAME; other deploys can set it too.
_ALLOWED_HOSTS = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
_ext = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _ext:
    _ALLOWED_HOSTS += [_ext, f"{_ext}:*"]


def _api_key() -> str:
    """LATTICE_KEY env, falling back to the repo's .env master key so the
    local server Just Works without pasting secrets into .mcp.json."""
    key = (os.environ.get("LATTICE_KEY") or os.environ.get("LATTICE_API_KEY") or "").strip()
    if key:
        return key
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), ".env")) as fh:
            for line in fh:
                if line.strip().startswith("LATTICE_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""

mcp = FastMCP(
    "lattice",
    # Also served remotely: server/app.py mounts this over streamable HTTP at
    # {api}/mcp, so agents can register the deployed URL with no local code.
    # stateless_http: each request stands alone -- survives Render restarts.
    stateless_http=True,
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(allowed_hosts=_ALLOWED_HOSTS),
    instructions=(
        "Indian address intelligence. Free-text Indian addresses are "
        "landmark-led, multi-script and non-canonical; these tools parse them "
        "into structure, decide whether two strings are the same physical "
        "door, deduplicate batches, and score deliverability risk. "
        "All tools call a running Lattice API (LATTICE_API env)."
    ),
)


async def _call(method: str, path: str, body: dict | None = None) -> dict:
    """Async on purpose: when this server is mounted INSIDE the API process
    (server/app.py, /mcp over HTTP), a blocking client here would freeze the
    event loop while waiting on a request the same loop must serve -- a
    deadlock. httpx.AsyncClient yields the loop instead."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.request(
                method, API + path,
                content=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json", "X-API-Key": _api_key()},
            )
    except httpx.HTTPError as e:
        return {"error": "lattice API unreachable",
                "detail": f"{e} -- is it running at {API}?"}
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "detail": r.text[:400]}
    return r.json()


@mcp.tool()
async def parse_address(address: str) -> dict:
    """Parse one messy Indian address (any script) into structured components.

    Returns house_number/building/street/locality/post_office/city/district/
    state/pincode, landmarks with spatial relations, a deliverability risk
    score with reasons and the single best field to ask the customer for,
    and an offline postal-directory check of the pincode.
    """
    return await _call("POST", "/parse", {"address": address})


@mcp.tool()
async def compare_addresses(a: str, b: str) -> dict:
    """Do two address strings refer to the same physical door?

    Returns score (0-1), verdict (same/likely/different), coarse vs fine
    signal breakdown, matched landmarks, and any veto (e.g. house-number
    mismatch). Decision threshold used downstream is 0.75.
    """
    return await _call("POST", "/compare", {"a": a, "b": b})


@mcp.tool()
async def dedupe_batch(addresses: list[str]) -> dict:
    """Deduplicate up to 40 address strings to unique physical locations.

    Returns cluster ids, unique_locations, duplicates_collapsed, one golden
    (canonical merged) record per cluster with provenance, and per-address
    deliverability scores.
    """
    return await _call("POST", "/batch", {"addresses": addresses})


@mcp.tool()
async def match_address(address: str, top_k: int = 5) -> dict:
    """Match an incoming address against the reference corpus.

    Answers: has this address (under any spelling) been seen before?
    Returns top-k candidates with scores and evidence.
    """
    return await _call("POST", "/match", {"address": address, "top_k": top_k})


@mcp.tool()
async def check_pincode(pincode: str) -> dict:
    """Look up a 6-digit PIN in the offline postal directory (19,238 pins):
    does it exist, which state/district does it belong to, which areas
    does it serve."""
    return await _call("GET", f"/pincode/{pincode}")


@mcp.tool()
async def digipin_encode(latitude: float, longitude: float) -> dict:
    """Coordinates -> DIGIPIN code (India Post's official 4m x 4m grid).
    Coordinates only -- free-text addresses need geocoding first, which
    Lattice deliberately does not claim to do."""
    return await _call("POST", "/digipin/encode",
                 {"latitude": latitude, "longitude": longitude})


@mcp.tool()
async def digipin_decode(digipin: str) -> dict:
    """DIGIPIN code -> cell centre coordinates and bounds."""
    return await _call("POST", "/digipin/decode", {"digipin": digipin})


if __name__ == "__main__":
    mcp.run()
