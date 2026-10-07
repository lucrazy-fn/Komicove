import os, re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from komicove_client import releases, api_client

CURRENT_VERSION = "0.2.1.1"
RELEASES_URL = f"https://github.com/{releases.REPOSITORIES[0]}/releases"
API_URL = f"https://api.github.com/repos/{releases.REPOSITORIES[0]}/releases/latest"
SECOND_API_URL = f"https://api.github.com/repos/{releases.REPOSITORIES[1]}/releases/latest"


def _version(value):
    return tuple(int(x) for x in re.findall(r"\d+", str(value))[:3]) or (0,)


def deduplicate(items):
    selected = {}
    for item in items:
        if releases.version_key(item.get("version")) is None:
            continue
        key = releases.version_id(item["version"])
        previous = selected.get(key)
        priority = (item.get("source") == "panel", item.get("created_at") or "")
        if previous is None or priority > (previous.get("source") == "panel", previous.get("created_at") or ""):
            selected[key] = item
    return sorted(selected.values(), key=lambda i: (releases.compatible(i["version"], CURRENT_VERSION), releases.version_key(i["version"])), reverse=True)


def fetch():
    override = os.environ.get("KOMICOVE_UPDATE_MANIFEST_URL") or os.environ.get("PANEL_UPDATE_MANIFEST_URL")
    items, errors, succeeded = [], [], 0
    for repository, url in zip(releases.REPOSITORIES, (override or API_URL, SECOND_API_URL)):
        try:
            response = requests.get(url, timeout=5, headers=releases.HEADERS)
            if response.status_code == 404:
                succeeded += 1
                continue
            response.raise_for_status()
            raw = response.json()
            if raw.get("draft") or raw.get("prerelease"):
                succeeded += 1
                continue
            data = releases.normalize_release(raw, repository) if "tag_name" in raw else dict(raw)
            succeeded += 1
            data.setdefault("source", "github")
            data.setdefault("title", f"Komicove {data.get('version', '')}")
            if releases.compatible(data.get("version"), CURRENT_VERSION):
                items.append(data)
        except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
            errors.append(error)
    try:
        response = requests.get(f"{api_client.BASE_URL}/updates", timeout=5)
        if response.status_code == 404:
            succeeded += 1
        else:
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError("Invalid update feed")
            for row in rows:
                items.append(dict(row, source="panel", origin=row.get("source"), url=row.get("download_url")))
            succeeded += 1
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        errors.append(error)
    if not succeeded and errors:
        raise errors[0]
    return deduplicate(items)


def is_newer(data):
    return (releases.compatible(data.get("version"), CURRENT_VERSION)
            and releases.version_key(data["version"]) > releases.version_key(CURRENT_VERSION))


def check(seen_messages=None):
    return next((data for data in fetch() if is_newer(data)
        or (seen_messages is not None and data.get("source") == "panel"
            and data.get("id") not in seen_messages and releases.compatible(data["version"], CURRENT_VERSION))), None)


def display_date(value):
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return ""


def plain_notes(value):
    text = re.sub(r"(?m)^#{1,6}\s*", "", value or "")
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return re.sub(r"(`+|\*\*)", "", text).strip()


def safe_url(value):
    try:
        parsed = urlparse(str(value or ""))
        return value if parsed.scheme == "https" and parsed.netloc and not parsed.username else RELEASES_URL
    except ValueError:
        return RELEASES_URL
