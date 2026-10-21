"""Official release sources and version ordering shared by desktop and API."""
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote, quote
from xml.etree import ElementTree
import requests

REPOSITORIES = ("lucrazy-fn/PANEL-ComicBookReader", "lucrazy-fn/Komicove")
SITE_DOWNLOAD_URL = "https://lucrazy-fn.github.io/Komicove/#downloads"
HEADERS = {"Accept": "application/vnd.github+json"}
VERSION_PATTERN = r"[vV]?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?"


def _headers(accept="application/vnd.github+json"):
    headers = dict(HEADERS)
    headers["Accept"] = accept
    token = (os.environ.get("KOMICOVE_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def release_url(version):
    tag = "v" + str(version).strip().removeprefix("v").removeprefix("V")
    return f"https://github.com/{REPOSITORIES[0]}/releases/tag/{quote(tag, safe='.-')}"


def tag_url(repository, tag):
    if repository not in REPOSITORIES or version_key(tag) is None:
        raise ValueError("Release inválida.")
    return f"https://github.com/{repository}/releases/tag/{quote(str(tag).strip(), safe='.-')}"


def version_key(value):
    if len(str(value or "")) > 64:
        return None
    match = re.fullmatch(VERSION_PATTERN, str(value or "").strip())
    if not match:
        return None
    major, minor, patch, revision, prerelease = match.groups()
    suffix = tuple((0, int(part)) if part.isdecimal() else (1, part)
                   for part in (prerelease or "").split("."))
    return (int(major), int(minor), int(patch or 0), int(revision or 0), 0 if prerelease else 1, suffix)


def version_id(value):
    value = str(value).strip()
    key = version_key(value)
    if key is None:
        return str(value)
    suffix = str(value).split("-", 1)[1].split("+", 1)[0] if key[4] == 0 else ""
    numbers = key[:4] if key[3] else key[:3]
    return ".".join(map(str, numbers)) + ("-" + suffix if suffix else "")


def platform_version(version, notes, platform="desktop"):
    if platform == "android":
        match = re.search(r"(?im)^[ \t]*(?:[-*#]+[ \t]*)?android[ \t]*(?:version[ \t]*)?(\d+\.\d+(?:\.\d+){0,2})", notes or "")
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
    response = requests.get(f"https://api.github.com/repos/{repository}/releases{endpoint}", headers=_headers(), timeout=(5, 10))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


class _ReleaseText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "pre"}:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()


def github_atom(repository):
    if repository not in REPOSITORIES:
        raise ValueError("Repositório não permitido.")
    response = requests.get(f"https://github.com/{repository}/releases.atom",
        headers=_headers("application/atom+xml"), timeout=(5, 10))
    response.raise_for_status()
    root = ElementTree.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    rows = []
    for entry in root.findall("atom:entry", namespace):
        link = next((item.get("href") for item in entry.findall("atom:link", namespace)
            if item.get("rel") == "alternate"), None)
        if not github_url(link):
            continue
        marker = "/releases/tag/"
        tag = unquote(urlparse(link).path.split(marker, 1)[1]) if marker in urlparse(link).path else ""
        if version_key(tag) is None:
            continue
        content = entry.findtext("atom:content", default="", namespaces=namespace)
        parser = _ReleaseText(); parser.feed(content)
        rows.append({"id": None, "tag_name": tag,
            "name": entry.findtext("atom:title", default=tag, namespaces=namespace),
            "body": parser.text(), "html_url": link,
            "published_at": entry.findtext("atom:updated", default="", namespaces=namespace)})
    return rows


def github_releases(repository, page=1):
    try:
        return github_get(repository, "?per_page=30" + (f"&page={page}" if page > 1 else "")) or []
    except requests.RequestException:
        return github_atom(repository) if page == 1 else []


def github_release_by_tag(repository, tag):
    if version_key(tag) is None:
        raise ValueError("Release inválida.")
    try:
        raw = github_get(repository, "/tags/" + quote(str(tag).strip(), safe=".-"))
    except requests.RequestException:
        raw = None
    if not isinstance(raw, dict):
        wanted = version_id(tag)
        raw = next((item for item in github_atom(repository)
            if version_id(item.get("tag_name")) == wanted), None)
    if not isinstance(raw, dict) or raw.get("draft") or not github_url(raw.get("html_url")):
        raise ValueError("Release não encontrada.")
    return raw


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
