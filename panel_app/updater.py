import os, re
from urllib.parse import urlparse
import requests
CURRENT_VERSION="1.6.1"
RELEASES_URL="https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases"
API_URL="https://api.github.com/repos/lucrazy-fn/PANEL-ComicBookReader/releases/latest"

def _version(value):
    return tuple(int(x) for x in re.findall(r"\d+", str(value))[:3]) or (0,)

def check():
    url=os.environ.get("PANEL_UPDATE_MANIFEST_URL", API_URL)
    response=requests.get(url,timeout=5,headers={"Accept":"application/vnd.github+json"})
    response.raise_for_status(); raw=response.json()
    if "tag_name" in raw:
        version=raw.get("tag_name","").lstrip("v")
        assets={a.get("name"):a.get("browser_download_url") for a in raw.get("assets",[]) if a.get("name")}
        data={"version":version,"notes":raw.get("body") or "Sem notas publicadas.","url":raw.get("html_url") or RELEASES_URL,"assets":assets}
    else: data=raw
    return data if _version(data.get("version")) > _version(CURRENT_VERSION) else None

def safe_url(value):
    parsed=urlparse(str(value or ""))
    return value if parsed.scheme in {"https"} and parsed.netloc else RELEASES_URL
