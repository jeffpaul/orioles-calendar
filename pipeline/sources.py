"""Downloads with a local cache, so reruns only fetch what changed."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("OC_CACHE", Path(__file__).resolve().parent.parent / ".cache"))
USER_AGENT = "orioles-calendar/1.0 (+https://github.com/jeffpaul/orioles-calendar)"

RETROSHEET_TEAM = "https://www.retrosheet.org/downloads/teams/{code}.zip"
RETROSHEET_BIO = "https://www.retrosheet.org/downloads/biodata.zip"
RETROSHEET_TRANSACTIONS = "https://www.retrosheet.org/transactions/tranDB.zip"
RETROSHEET_GAMELOG = "https://www.retrosheet.org/gamelogs/gl{year}.zip"
BREF_WAR = "https://www.baseball-reference.com/data/war_daily_{kind}.txt"
CHADWICK = "https://raw.githubusercontent.com/chadwickbureau/register/master/data/people-{part}.csv"
STATSAPI = "https://statsapi.mlb.com/api/v1"


def _get(url, headers=None, attempts=4):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for i in range(attempts):
        try:
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code == 304 or e.code < 500:
                raise
        except urllib.error.URLError:
            pass
        time.sleep(2 ** (i + 1))
    return urllib.request.urlopen(req, timeout=120)


def fetch(url, name, max_age_hours=20):
    """Download url to the cache as `name`, revalidating with ETag/Last-Modified.

    Files younger than max_age_hours are used without a request.
    """
    path = CACHE / name
    meta_path = CACHE / (name + ".meta")
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return path
    headers = {}
    if path.exists():
        if meta.get("etag"):
            headers["If-None-Match"] = meta["etag"]
        if meta.get("last_modified"):
            headers["If-Modified-Since"] = meta["last_modified"]
    try:
        with _get(url, headers) as resp:
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
            tmp.replace(path)
            meta = {"url": url, "etag": resp.headers.get("ETag"),
                    "last_modified": resp.headers.get("Last-Modified")}
            meta_path.write_text(json.dumps(meta))
    except urllib.error.HTTPError as e:
        if e.code != 304:
            raise
        path.touch()
    return path


def statsapi(path, name=None, max_age_hours=6, **params):
    """GET a Stats API endpoint as JSON, cached under statsapi/."""
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{STATSAPI}{path}" + (f"?{query}" if query else "")
    name = name or "statsapi/" + (path.strip("/") + ("_" + query if query else "")).replace("/", "_").replace("&", "_").replace("=", "-").replace(",", "+")
    return json.loads(fetch(url, name + ("" if name.endswith(".json") else ".json"), max_age_hours).read_text())
