// Run with: node tools/verify-download-versions.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/download-versions.js'), 'utf8'), context);
const {assetKind, normalizeReleases, releaseCounts, fallback} = context.window.KomicoveReleaseCatalog;
assert.equal(fallback.length, 18);
assert.deepEqual(Array.from(fallback.slice(0, 5), item => item.tag), ['v0.2.2', 'v0.2.1.1', 'v0.2.1', 'v0.2.0', 'v0.1.0']);
assert.equal(fallback.find(item => item.tag === 'v1.7.1').family, 'panel');
assert.equal(fallback.find(item => item.tag === 'v0.2.0').assets.some(asset => assetKind(asset.name) === 'portable'), false);
assert.equal(assetKind('PANEL-Android-1.6.1.apk'), 'android');
assert.equal(assetKind('Panel_Reader_Setup_v1.2_Beta.exe'), 'windows');
assert.ok(fallback.every(item => item.assets.every(asset => asset.url.includes(`/releases/download/${encodeURIComponent(item.tag)}/${encodeURIComponent(asset.name)}`))));

const releases = [
  {tag_name: 'v0.2.0', published_at: '2026-10-02T00:00:00Z', draft: false, prerelease: false, assets: [
    {name: 'Komicove-Android-0.2.0.apk', download_count: 41},
    {name: 'Komicove-Setup-0.2.0.exe', download_count: 16},
    {name: 'Komicove-Linux-0.2.0-x86_64.tar.gz', download_count: 1},
    {name: 'Komicove-Linux-0.2.0-x86_64.flatpak', download_count: 1}
  ]},
  {tag_name: 'v0.2.1.1', published_at: '2026-10-07T00:00:00Z', draft: false, prerelease: false, assets: [
    {name: 'Komicove-Android-0.2.1.1.apk', download_count: 102},
    {name: 'Komicove-Setup-0.2.1.1.exe', download_count: 16},
    {name: 'Komicove-Windows-0.2.1.1-portable.zip', download_count: 13},
    {name: 'Komicove-Linux-0.2.1.1-x86_64.tar.gz', download_count: 10},
    {name: 'Komicove-Linux-0.2.1.1-x86_64.flatpak', download_count: 12}
  ]},
  {tag_name: 'v1.7.1', published_at: '2026-09-20T00:00:00Z', draft: false, prerelease: false, assets: [{name: 'PANEL-Android-1.6.1.apk', download_count: 125}, {name: 'PANEL-Setup-1.7.1.exe', download_count: 16}]},
  {tag_name: 'v0.3.0', draft: true, prerelease: false, assets: [{name: 'Komicove-Android-0.3.0.apk', download_count: 1}]}
];
const catalog = normalizeReleases(releases);
assert.deepEqual(Array.from(catalog.releases, item => item.tag), ['v0.2.1.1', 'v0.2.0', 'v1.7.1']);
assert.equal(catalog.allTotal, 353);
assert.equal(catalog.releases[2].family, 'panel');
assert.equal(releaseCounts(catalog.releases[0]).total, 153);
assert.deepEqual({...releaseCounts(catalog.releases[0]).platforms}, {android: 102, windows: 29, linux: 22});
assert.deepEqual({...releaseCounts(catalog.releases[1]).platforms}, {android: 41, windows: 16, linux: 2});
assert.deepEqual({...releaseCounts(catalog.releases[2]).platforms}, {android: 125, windows: 16, linux: 0});
assert.equal(releaseCounts(fallback[0]).available, false);
const messageContext = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/translations.js'), 'utf8'), messageContext);
const textNode = () => ({textContent: '', hidden: false});
const fakeNode = () => ({textContent: '', hidden: false, handlers: {}, children: [], addEventListener(name, handler) {this.handlers[name] = handler;}, replaceChildren(...children) {this.children = children;}, append(...children) {this.children.push(...children);}, setAttribute(name, value) {this[name] = value;}, focus() {this.focused = true;}});
const summary = fakeNode();
const details = {...fakeNode(), open: false, querySelector: selector => selector === 'summary' ? summary : null};
const options = fakeNode();
const picker = {querySelector: selector => ({'[data-download-details]': details, '[data-download-options]': options})[selector]};
const links = Object.fromEntries(['android', 'windows', 'portable', 'linux', 'flatpak'].map(kind => {
  const label = textNode();
  return [kind, {dataset: {downloadAsset: kind}, href: '', hidden: false, label, querySelector: () => kind === 'android' ? label : null}];
}));
const platforms = Object.fromEntries(['android', 'windows', 'linux'].map(kind => [kind, {hidden: false}]));
const counters = Object.fromEntries(['android', 'windows', 'linux'].map(kind => [kind, {dataset: {downloadCount: kind}, hidden: true, querySelector: selector => selector === 'strong' ? counters[kind].strong : counters[kind].label, strong: textNode(), label: textNode()}]));
const totalParts = Object.fromEntries(['[data-download-total]', '[data-download-total-label]', '[data-download-all-total]', '[data-download-all-count]'].map(selector => [selector, textNode()]));
const total = {hidden: true, querySelector: selector => totalParts[selector]};
const selected = textNode();
const current = textNode();
const currentMeta = textNode();
const olderNote = textNode();
const releaseLink = {href: '', textContent: ''};
const notesLink = {href: 'novidades.html'};
const guideLinks = Object.fromEntries(['android', 'windows', 'linux'].map(kind => [kind, {hash: `#get-${kind}`, hidden: false}]));
const version = textNode();
const document = {
  documentElement: {lang: 'en', classList: {add() {}}},
  addEventListener() {},
  querySelector(selector) {
    if (selector === '[data-download-picker]') return picker;
    if (selector === '#download-total') return total;
    const match = selector.match(/^\[data-download-platform="(\w+)"\]:not\(\[hidden\]\)$/);
    return match && !platforms[match[1]]?.hidden ? platforms[match[1]] : null;
  },
  querySelectorAll(selector) {
    if (selector === '[data-download-version]') return [version];
    if (selector === '[data-download-selected]') return [selected];
    if (selector === '[data-download-current]') return [current];
    if (selector === '[data-download-current-meta]') return [currentMeta];
    if (selector === '[data-download-older-note]') return [olderNote];
    if (selector === '[data-download-release-link]') return [releaseLink];
    if (selector === '[data-download-notes-link]') return [notesLink];
    if (selector === '.guide-index a[href^="#get-"]') return Object.values(guideLinks);
    if (selector === '[data-download-asset]') return Object.values(links);
    if (selector === '[data-download-count]') return Object.values(counters);
    if (selector === '[data-language]') return [];
    const match = selector.match(/^\[data-download-platform="(\w+)"\]$/);
    return match ? [platforms[match[1]]] : [];
  },
  createElement() {return fakeNode();}
};
const values = new Map([
  ['komicove.site.downloadVersion', 'v0.2.0'],
  ['komicove.site.releaseCatalog.v2', JSON.stringify({savedAt: Date.now(), catalog})]
]);
const runtime = {
  window: {KOMICOVE_MESSAGES: messageContext.window.KOMICOVE_MESSAGES, addEventListener() {}},
  document,
  localStorage: {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)},
  fetch: () => {throw new Error('Fresh cache must avoid a network request');},
  queueMicrotask
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/download-versions.js'), 'utf8'), runtime);
assert.equal(current.textContent, 'v0.2.1.1');
assert.equal(options.children.filter(item => item.className === 'download-option').length, 3);
assert.match(links.android.href, /v0\.2\.1\.1\/Komicove-Android-0\.2\.1\.1\.apk$/);
assert.equal(links.portable.hidden, false);
assert.equal(totalParts['[data-download-total]'].textContent, '153');
assert.equal(totalParts['[data-download-all-total]'].textContent, '353');
assert.equal(counters.android.strong.textContent, '102');
assert.equal(olderNote.hidden, false);
options.children.find(item => item.className === 'download-option' && item.children[0].textContent === 'v0.2.0').handlers.click();
assert.equal(current.textContent, 'v0.2.0');
assert.equal(values.get('komicove.site.downloadVersion.v022'), 'v0.2.0');
options.children.find(item => item.className === 'download-option' && item.children[0].textContent === 'v0.2.1.1').handlers.click();
assert.equal(links.portable.hidden, false);
assert.match(links.portable.href, /v0\.2\.1\.1\/Komicove-Windows-0\.2\.1\.1-portable\.zip$/);
assert.equal(totalParts['[data-download-total]'].textContent, '153');
assert.equal(counters.windows.strong.textContent, '29');
assert.equal(olderNote.hidden, false);
assert.equal(notesLink.href, 'https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases/tag/v0.2.1.1');
assert.equal(values.get('komicove.site.downloadVersion.v022'), 'v0.2.1.1');
document.documentElement.lang = 'pt-BR';
options.children.find(item => item.className === 'download-option' && item.children[0].textContent === 'v1.7.1').handlers.click();
assert.equal(currentMeta.textContent, 'Versão anterior do PANEL');
assert.equal(counters.android.strong.textContent, '125');
assert.equal(platforms.linux.hidden, true);
assert.equal(links.linux.hidden, true);
assert.equal(guideLinks.linux.hidden, true);
assert.match(notesLink.href, /releases\/tag\/v1\.7\.1$/);
assert.match(links.android.href, /v1\.7\.1\/PANEL-Android-1\.6\.1\.apk$/);
assert.equal(links.android.label.textContent, 'Baixar APK 1.6.1');
console.log('Release picker checks passed: Komicove and PANEL assets, platform availability, saved choice and counts.');
