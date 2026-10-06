"""Official release sources and version ordering shared by desktop and API."""
import re
from urllib.parse import urlparse, unquote, quote
import requests

REPOSITORIES = ("lucrazy-fn/PANEL-ComicBookReader", "lucrazy-fn/Komicove")
SITE_DOWNLOAD_URL = "https://lucrazy-fn.github.io/Komicove/#downloads"
HEADERS = {"Accept": "application/vnd.github+json"}
VERSION_PATTERN = r"[vV]?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?"


def release_url(version):
    tag = "v" + str(version).strip().removeprefix("v").removeprefix("V")
    return f"https://github.com/{REPOSITORIES[0]}/releases/tag/{quote(tag, safe='.-')}"


def version_key(value):
    if len(str(value or "")) > 64:
        return None
    match = re.fullmatch(VERSION_PATTERN, str(value or "").strip())
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    suffix = tuple((0, int(part)) if part.isdecimal() else (1, part)
                   for part in (prerelease or "").split("."))
    return (int(major), int(minor), int(patch or 0), 0 if prerelease else 1, suffix)


def version_id(value):
    value = str(value).strip()
    key = version_key(value)
    if key is None:
        return str(value)
    suffix = str(value).split("-", 1)[1].split("+", 1)[0] if key[3] == 0 else ""
    return ".".join(map(str, key[:3])) + ("-" + suffix if suffix else "")


def platform_version(version, notes, platform="desktop"):
    if platform == "android":
        match = re.search(r"(?im)^[ \t]*(?:[-*#]+[ \t]*)?android[ \t]*(?:version[ \t]*)?(\d+\.\d+(?:\.\d+)?)", notes or "")
        if match:
            return match.group(1)
    return str(version or "").lstrip("vV")


def compatible(version, current):
    remote, installed = version_key(version), version_key(current)
    return bool(remote and installed and (installed[0] != 0 or remote[0] == 0))


def github_url(value):
    parsed = urlparse(str(value or ""))
    path = unquote(parsed.path)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or parsed.query or parsed.fragment:
        return False
    return any(path.lower() == f"/{repo}/releases".lower()
               or path.lower().startswith(f"/{repo}/releases/".lower()) for repo in REPOSITORIES) and not any(part in {".", ".."} for part in path.split("/"))


def github_get(repository, endpoint):
    if repository not in REPOSITORIES:
        raise ValueError("Repositório não permitido.")
    response = requests.get(f"https://api.github.com/repos/{repository}/releases{endpoint}", headers=HEADERS, timeout=(5, 10))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def github_release(repository, release_id):
    if not isinstance(release_id, int) or release_id <= 0:
        raise ValueError("Release inválida.")
    raw = github_get(repository, f"/{release_id}")
    if not isinstance(raw, dict) or raw.get("draft") or not github_url(raw.get("html_url")):
        raise ValueError("Release não encontrada.")
    return raw


def normalize_release(raw, repository, platform="desktop"):
    version = platform_version(raw.get("tag_name"), raw.get("body"), platform)
    return {"title": raw.get("name") or raw.get("tag_name") or "Komicove",
            "version": version, "notes": raw.get("body") or "", "source": "github",
            "repository": repository, "url": raw.get("html_url") or f"https://github.com/{repository}/releases",
            "created_at": raw.get("published_at") or raw.get("created_at") or "",
            "assets": {a.get("name"): a.get("browser_download_url") for a in raw.get("assets", []) if a.get("name")}}
