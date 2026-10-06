from html import escape
from markdown_it import MarkdownIt
from komicove_client import releases


def markdown(notes):
    parser = MarkdownIt("commonmark", {"html": False, "maxNesting": 20}).enable("table")
    # Release descriptions are text, not remotely loaded images or embedded HTML.
    parser.renderer.rules["image"] = lambda tokens, i, options, env: escape(tokens[i].content)
    return parser.render(notes or "")


def imported(repository, release_id):
    raw = releases.github_release(repository, release_id)
    title = raw.get("name") or raw.get("tag_name") or "Komicove"
    version = raw.get("tag_name") or ""
    notes = raw.get("body") or ""
    if releases.version_key(version) is None or len(version) > 64 or len(title) > 150 or len(notes) > 50000:
        raise ValueError("Release incompatível com os limites da mensagem.")
    return {"title": title, "version": version, "notes": notes, "url": raw["html_url"]}
