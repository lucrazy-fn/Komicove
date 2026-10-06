"""Check the moderator panel scripts and the new form's safety constraints."""
from pathlib import Path
import re
import subprocess
import tempfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / 'komicove_backend/web/moderators.html').read_text(encoding='utf-8')
scripts = re.findall(r'<script>([\s\S]*?)</script>', page)
assert len(scripts) == 1
assert '${t(' not in page.split('<script')[0]
assert 'type="file"' not in page
class FormIds(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for key, value in attrs if key == 'id')
parser = FormIds()
parser.feed(page)
ids = parser.ids
assert len(ids) == len(set(ids))
assert all(repo in page for repo in ('lucrazy-fn/PANEL-ComicBookReader', 'lucrazy-fn/Komicove'))
for source in ('moderators-i18n.js', 'moderators-features.js'):
    subprocess.run(['node', '--check', str(ROOT / 'komicove_backend/web' / source)], check=True)
with tempfile.TemporaryDirectory(prefix='komicove-panel-check-') as directory:
    inline = Path(directory) / 'inline.js'
    inline.write_text(scripts[0], encoding='utf-8')
    subprocess.run(['node', '--check', str(inline)], check=True)
print('Moderator panel: scripts, unique form IDs, import sources and no upload control verified.')
