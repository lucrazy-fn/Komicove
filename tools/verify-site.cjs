// Run with: node tools/verify-site.cjs
// Check shared translations, internal navigation, and local dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../docs');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'translations.js'), 'utf8'), context);
const messages = context.window.KOMICOVE_MESSAGES;
assert.deepEqual(Object.keys(messages.en).sort(), Object.keys(messages['pt-BR']).sort());
const keys = [...html.matchAll(/data-i18n(?:-aria-label|-alt)?="([^"]+)"/g)].map(match => match[1]);
for (const key of keys) {
  for (const language of ['en', 'pt-BR']) assert.ok(messages[language][key]?.trim(), `Missing ${language} translation: ${key}`);
}
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(ids).size, ids.length, 'Duplicate HTML ids');
for (const [,href] of html.matchAll(/href="(#[^"]+)"/g)) assert.ok(ids.includes(href.slice(1)), `Broken anchor: ${href}`);
for (const id of ['conteudo','recursos','novidades','interface','community','formatos','faq','downloads','linux','android','lightbox']) assert.ok(ids.includes(id), `Missing section: ${id}`);
for (const [,asset] of html.matchAll(/(?:src|href)="((?:assets\/|styles\.|design\.|app\.|translations\.)[^"]+)"/g)) assert.ok(fs.existsSync(path.join(root,asset.split('?')[0])), `Missing asset: ${asset}`);
for (const name of ['biblioteca','leitor','colecoes']) {
  assert.ok(fs.existsSync(path.join(root,`assets/${name}.png`)));
  for (const property of ['title','description','alt']) assert.ok(messages.en[`screen.${name}.${property}`] && messages['pt-BR'][`screen.${name}.${property}`]);
}
for (const file of ['app.js','translations.js']) new vm.Script(fs.readFileSync(path.join(root,file),'utf8'),{filename:file});
assert.match(html, /<html lang="en">/);
console.log(`Site checks passed: ${keys.length} translated elements, ${Object.keys(messages.en).length} messages per language, all sections and local assets present.`);
