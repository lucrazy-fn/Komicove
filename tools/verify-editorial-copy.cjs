const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'docs', 'translations.js'), 'utf8'), context);
const messages = context.window.KOMICOVE_MESSAGES;
const allCopy = Object.values(messages).flatMap(Object.values).join('\n').toLowerCase();
const rejected = [
  'every story deserves its space',
  'toda história merece seu lugar',
  'your journey, saved',
  'sua jornada, salva',
  'one place to call home',
  'um lugar para chamar de lar',
  'help turn the next page',
  'ajude a virar a próxima página',
  'your next read starts here',
  'sua próxima leitura começa aqui',
  'made for people who always read',
  'feito para quem sempre lê',
  'the story comes first',
  'a história vem primeiro'
];
for (const phrase of rejected) assert.equal(allCopy.includes(phrase), false, `Rejected marketing phrase remains: ${phrase}`);

for (const name of fs.readdirSync(path.join(root, 'docs')).filter(name => name.endsWith('.html'))) {
  const html = fs.readFileSync(path.join(root, 'docs', name), 'utf8');
  for (const match of html.matchAll(/<([a-z][a-z0-9]*)([^>]*\sdata-i18n="([^"]+)"[^>]*)>([^<]*)<\/\1>/gi)) {
    const key = match[3];
    if (messages.en[key] != null) assert.equal(match[4], messages.en[key], `${name} has stale default copy for ${key}`);
  }
}

console.log('Editorial copy checks passed.');
