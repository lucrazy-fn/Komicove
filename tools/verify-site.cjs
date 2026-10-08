// Run with: node tools/verify-site.cjs
// Check shared translations, internal navigation, and local dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../docs');
const pages = ['index.html', 'novidades.html'];
const htmlByPage = Object.fromEntries(pages.map(file => [file, fs.readFileSync(path.join(root, file), 'utf8')]));
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'translations.js'), 'utf8'), context);
const messages = context.window.KOMICOVE_MESSAGES;

assert.deepEqual(Object.keys(messages.en).sort(), Object.keys(messages['pt-BR']).sort());
let translatedElements = 0;
for (const [file, html] of Object.entries(htmlByPage)) {
  const keys = [...html.matchAll(/data-i18n(?:-aria-label|-alt)?="([^"]+)"/g)].map(match => match[1]);
  translatedElements += keys.length;
  for (const key of keys) {
    for (const language of ['en', 'pt-BR']) assert.ok(messages[language][key]?.trim(), `Missing ${language} translation in ${file}: ${key}`);
  }

  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length, `Duplicate HTML ids in ${file}`);
  for (const [, href] of html.matchAll(/href="(#[^"]+)"/g)) assert.ok(ids.includes(href.slice(1)), `Broken anchor in ${file}: ${href}`);

  for (const [, asset] of html.matchAll(/(?:src|href)="((?:assets\/|screenshots\/|styles\.|design\.|app\.|news\.|translations\.)[^"]+)"/g)) {
    assert.ok(fs.existsSync(path.join(root, asset.split('?')[0])), `Missing asset in ${file}: ${asset}`);
  }
}

const indexHtml = htmlByPage['index.html'];
const indexIds = [...indexHtml.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
for (const id of ['conteudo', 'recursos', 'novidades', 'interface', 'roadmap', 'community', 'formatos', 'faq', 'downloads', 'linux', 'android', 'lightbox']) {
  assert.ok(indexIds.includes(id), `Missing section: ${id}`);
}

for (const asset of [
  'Komicove-Setup-0.2.1.1.exe',
  'Komicove-Windows-0.2.1.1-portable.zip',
  'Komicove-Linux-0.2.1.1-x86_64.tar.gz',
  'Komicove-Linux-0.2.1.1-x86_64.flatpak',
  'Komicove-Android-0.2.1.1.apk'
]) {
  assert.ok(indexHtml.includes(`releases/download/v0.2.1.1/${asset}`), `Missing direct download: ${asset}`);
}

const screenshots = {
  biblioteca: 'desktop-biblioteca.png',
  leitor: 'desktop-leitor.png',
  pastas: 'desktop-pastas.png'
};
for (const [name, file] of Object.entries(screenshots)) {
  assert.ok(fs.existsSync(path.join(root, 'screenshots', file)), `Missing screenshot: ${file}`);
  for (const property of ['title', 'description', 'alt']) {
    assert.ok(messages.en[`screen.${name}.${property}`] && messages['pt-BR'][`screen.${name}.${property}`]);
  }
}

for (const file of ['app.js', 'translations.js', 'news.js']) {
  new vm.Script(fs.readFileSync(path.join(root, file), 'utf8'), {filename: file});
}
for (const [file, html] of Object.entries(htmlByPage)) {
  assert.match(html, /<html lang="en">/, `${file} must use English as its static language`);
  assert.doesNotMatch(html, /\u2014/, `${file} contains an em dash`);
}
for (const file of ['app.js', 'news.js', 'translations.js', 'design.css', 'styles.css']) {
  assert.doesNotMatch(fs.readFileSync(path.join(root, file), 'utf8'), /\u2014/, `${file} contains an em dash`);
}

console.log(`Site checks passed: ${translatedElements} translated elements, ${Object.keys(messages.en).length} messages per language, all pages, sections, screenshots and local assets present.`);
