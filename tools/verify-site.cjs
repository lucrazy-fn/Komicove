// Run with: node tools/verify-site.cjs
// Check shared translations, internal navigation, and local dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../docs');
const pages = ['index.html', 'novidades.html', 'docs.html', 'tutoriais.html', 'apoie.html', 'download.html'];
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
  for (const [, fragment] of html.matchAll(/href="\.\/#([^"]+)"/g)) assert.ok(htmlByPage['index.html'].includes(`id="${fragment}"`), `Broken homepage anchor in ${file}: ${fragment}`);
  assert.ok(!html.includes('href="index.html'), `Legacy homepage link in ${file}`);
  assert.match(html, /src="home-url\.js\?v=\d+"/, `Missing clean homepage URL helper in ${file}`);

  for (const [, asset] of html.matchAll(/(?:src|href|poster)="((?:assets\/|screenshots\/|styles\.|cinematic\.|mobile\.|help\.|help-hub\.|home-url\.|download-versions\.|app\.|news\.|guide\.|float-nav\.|theme\.|translations\.)[^"]+)"/g)) {
    assert.ok(fs.existsSync(path.join(root, asset.split('?')[0])), `Missing asset in ${file}: ${asset}`);
  }
  assert.match(html, /data-theme-toggle/, `Missing theme control in ${file}`);
  assert.match(html, /komicove\.site\.theme/, `Missing early theme bootstrap in ${file}`);
  for (const [, target, fragment] of html.matchAll(/href="(index\.html|novidades\.html|docs\.html|tutoriais\.html|apoie\.html|download\.html)#([^"?]+)"/g)) {
    assert.ok(htmlByPage[target].includes(`id="${fragment}"`), `Broken cross-page anchor in ${file}: ${target}#${fragment}`);
  }
  for (const [, target] of html.matchAll(/href="(index\.html|novidades\.html|docs\.html|tutoriais\.html|apoie\.html|download\.html)"/g)) {
    assert.ok(htmlByPage[target], `Broken page link in ${file}: ${target}`);
  }
  assert.match(html, /class="brand-official" src="assets\/logo\.png"/, `Missing official logo in ${file}`);
  assert.match(html, /href="apoie\.html"/, `Missing support link in ${file}`);
  assert.match(html, /href="mobile\.css\?v=\d+"/, `Missing phone layout in ${file}`);
}

const indexHtml = htmlByPage['index.html'];
assert.match(indexHtml, /rel="canonical" href="https:\/\/komicove\.online\/"/, 'Homepage canonical URL');
const sitemap = fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8');
assert.match(sitemap, /<loc>https:\/\/komicove\.online\/<\/loc>/, 'Clean homepage URL in sitemap');
assert.doesNotMatch(sitemap, /index\.html/, 'Legacy homepage URL in sitemap');
assert.match(fs.readFileSync(path.join(root, 'robots.txt'), 'utf8'), /Sitemap: https:\/\/komicove\.online\/sitemap\.xml/, 'Sitemap discovery');
const indexIds = [...indexHtml.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
for (const id of ['conteudo', 'recursos', 'novidades', 'interface', 'roadmap', 'community', 'formatos', 'faq', 'downloads', 'linux', 'android', 'lightbox']) {
  assert.ok(indexIds.includes(id), `Missing section: ${id}`);
}
assert.ok(indexHtml.indexOf('class="journey-index"') < indexHtml.indexOf('id="downloads"'), 'Quick paths should precede downloads');
assert.ok(indexHtml.indexOf('id="downloads"') < indexHtml.indexOf('id="interface"'), 'Downloads should be available before the product tour');
assert.ok(indexHtml.indexOf('id="interface"') < indexHtml.indexOf('id="recursos"'), 'Interface should precede feature details');
assert.ok(indexHtml.indexOf('id="community"') < indexHtml.indexOf('id="novidades"'), 'Project news should follow community');
assert.ok(indexHtml.indexOf('class="support-spotlight"') < indexHtml.indexOf('id="faq"'), 'Support should precede the final help section');
assert.match(indexHtml, /class="hero cinematic-hero"/, 'Missing cinematic cover');
assert.match(indexHtml, /class="hero-scene"/, 'Missing cover artwork');
assert.match(indexHtml, /class="button mobile-android-link"[^>]*Komicove-Android-0\.2\.1\.1\.apk/, 'Missing direct phone download in the cover');
assert.match(indexHtml, /<video id="product-demo"[^>]*controls muted loop playsinline/, 'Missing accessible product video');
assert.match(indexHtml, /<video id="android-demo"[^>]*controls muted loop playsinline/, 'Missing accessible Android video');
assert.match(indexHtml, /id="android-demo-play"[^>]*aria-controls="android-demo"/, 'Missing Android play control');
assert.match(indexHtml, /class="demo-duo"/, 'Desktop and Android videos should share the same section');
assert.ok(indexHtml.indexOf('id="product-demo"') < indexHtml.indexOf('class="gallery-controls"'), 'Product video should precede screenshot gallery');
assert.match(indexHtml, /class="journey-float" inert/, 'Missing floating quick paths');
assert.match(indexHtml, /class="journey-float-bars" aria-hidden="true"><span><\/span><span><\/span><span><\/span>/, 'Missing three-line floating control');
assert.match(indexHtml, /id="journey-float-panel"[^>]+hidden/, 'Floating menu should start closed');
for (const href of ['#downloads', '#interface', 'docs.html', 'novidades.html']) {
  assert.ok(indexHtml.match(/<nav id="journey-float-panel"[\s\S]*?<\/nav>/)?.[0].includes(`href="${href}"`), `Missing floating quick path: ${href}`);
}
assert.match(indexHtml, /class="nav-primary"/, 'Missing direct primary navigation');
assert.match(indexHtml, /supportPage\.costShort/, 'Missing known annual domain cost on the homepage');
const docsHtml = htmlByPage['docs.html'];
const tutorialsHtml = htmlByPage['tutoriais.html'];
const supportHtml = htmlByPage['apoie.html'];
const downloadHtml = htmlByPage['download.html'];
for (const file of ['index.html', 'download.html']) {
  const html = htmlByPage[file];
  assert.match(html, /data-download-picker/, `Missing version picker with no-JavaScript fallback in ${file}`);
  assert.match(html, /data-download-current>v0\.2\.1\.1/, `Missing static latest release in ${file}`);
  assert.match(html, /data-download-options/, `Missing release options in ${file}`);
  assert.match(html, /src="download-versions\.js\?v=\d+"/, `Missing release selector logic in ${file}`);
  assert.match(html, /href="download-versions\.css\?v=\d+"/, `Missing release selector styles in ${file}`);
  assert.match(html, /data-download-release-link/, `Missing selected release destination in ${file}`);
  for (const kind of ['android', 'windows', 'portable', 'linux', 'flatpak']) {
    assert.ok(html.includes(`data-download-asset="${kind}"`), `Missing ${kind} package control in ${file}`);
  }
}
for (const id of ['android-guide', 'desktop-guide', 'biblioteca', 'leitor', 'arquivos', 'backup', 'ajuda']) {
  assert.ok(docsHtml.includes(`id="${id}"`), `Missing docs topic: ${id}`);
}
for (const id of ['tutorial-android', 'tutorial-desktop', 'tutorial-reader', 'tutorial-library', 'tutorial-backup', 'tutorial-help']) {
  assert.ok(tutorialsHtml.includes(`id="${id}"`), `Missing tutorial: ${id}`);
}
assert.match(docsHtml, /data-i18n="docs\.backupNote"/, 'Docs must explain that comic files are not backed up');
assert.match(supportHtml, /data-i18n="supportPage\.costAmount"/, 'Support page must show the known annual domain cost');
for (const asset of ['Komicove-Setup-0.2.1.1.exe', 'Komicove-Windows-0.2.1.1-portable.zip', 'Komicove-Linux-0.2.1.1-x86_64.tar.gz', 'Komicove-Linux-0.2.1.1-x86_64.flatpak', 'Komicove-Android-0.2.1.1.apk']) {
  assert.ok(downloadHtml.includes(`releases/download/v0.2.1.1/${asset}`), `Missing download page package: ${asset}`);
}
for (const id of ['get-android', 'get-windows', 'get-linux', 'before-install']) assert.ok(downloadHtml.includes(`id="${id}"`));
for (const file of ['docs.html', 'tutoriais.html', 'download.html']) {
  assert.match(htmlByPage[file], /href="help\.css\?v=\d+"/, `Missing help layout in ${file}`);
  assert.match(htmlByPage[file], /src="help-hub\.js\?v=\d+"/, `Missing shared help navigation in ${file}`);
}
assert.match(messages.en['supportPage.costAmount'], /7\.08.*year/);
assert.match(messages['pt-BR']['supportPage.costAmount'], /7,08.*ano/);
for (const file of pages) {
  const nav = htmlByPage[file].match(/<nav id="menu"[\s\S]*?<\/nav>/)?.[0];
  assert.ok(nav, `Missing primary navigation in ${file}`);
  for (const target of ['./#interface', 'docs.html', 'tutoriais.html', 'apoie.html', 'download.html']) {
    assert.ok(nav.includes(`href="${target}"`), `Missing primary destination in ${file}: ${target}`);
  }
}
assert.match(indexHtml, /data-open-support/, 'Missing existing Pix dialog trigger');
assert.match(indexHtml, /id="support-dialog"/, 'Missing existing Pix dialog');
assert.ok(indexHtml.includes('class="wrap footer-grid"'), 'Missing footer navigation');

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

for (const asset of ['hero-noir.webp', 'comic-cover.webp']) {
  assert.ok(fs.existsSync(path.join(root, 'assets', asset)), `Missing cinematic artwork: ${asset}`);
}
for (const asset of ['logo.png', 'komicove.ico', 'pix-qr.png']) assert.ok(fs.existsSync(path.join(root, 'assets', asset)), `Missing official asset: ${asset}`);
const socialCard = fs.readFileSync(path.join(root, 'assets', 'social-card.png'));
assert.equal(socialCard.readUInt32BE(16), 1200, 'Social card width');
assert.equal(socialCard.readUInt32BE(20), 630, 'Social card height');
const visualCss = fs.readFileSync(path.join(root, 'cinematic.css'), 'utf8');
assert.equal((visualCss.match(/{/g) || []).length, (visualCss.match(/}/g) || []).length, 'Unbalanced visual CSS');
const versionsCss = fs.readFileSync(path.join(root, 'download-versions.css'), 'utf8');
assert.equal((versionsCss.match(/{/g) || []).length, (versionsCss.match(/}/g) || []).length, 'Unbalanced release selector CSS');
for (const [, asset] of visualCss.matchAll(/url\(['"]?(assets\/[^)'" ]+)/g)) {
  assert.ok(fs.existsSync(path.join(root, asset)), `Missing CSS artwork: ${asset}`);
}

for (const file of ['app.js', 'translations.js', 'news.js', 'guide.js', 'help-hub.js', 'home-url.js', 'download-versions.js', 'float-nav.js', 'theme.js']) {
  new vm.Script(fs.readFileSync(path.join(root, file), 'utf8'), {filename: file});
}
const homepageUrlScript = fs.readFileSync(path.join(root, 'home-url.js'), 'utf8');
let cleanedHomepageUrl = '';
vm.runInNewContext(homepageUrlScript, {
  location: {protocol: 'https:', pathname: '/index.html', search: '?from=search', hash: '#downloads'},
  history: {state: null, replaceState(_state, _title, url) {cleanedHomepageUrl = url;}},
  document: {}
});
assert.equal(cleanedHomepageUrl, '/?from=search#downloads');
const localHomeLink = {href: './#downloads', getAttribute() {return this.href;}, setAttribute(_name, value) {this.href = value;}};
vm.runInNewContext(homepageUrlScript, {
  location: {protocol: 'file:'},
  document: {querySelectorAll: () => [localHomeLink]}
});
assert.equal(localHomeLink.href, 'index.html#downloads');
const floatClasses = new Set();
const floatHandlers = {};
const floatButton = {
  attrs: {'aria-expanded': 'false'}, handlers: {}, tabIndex: -1, focused: false,
  setAttribute(name, value) {this.attrs[name] = value;},
  getAttribute(name) {return this.attrs[name];},
  addEventListener(name, handler) {this.handlers[name] = handler;},
  focus() {this.focused = true;}
};
const floatPanel = {
  hidden: true, handlers: {},
  addEventListener(name, handler) {this.handlers[name] = handler;},
  querySelector() {return null;}
};
const floatRoot = {
  inert: true,
  classList: {
    contains(name) {return floatClasses.has(name);},
    toggle(name, enabled) {if (enabled) floatClasses.add(name); else floatClasses.delete(name);}
  },
  querySelector(selector) {return selector === '.journey-float-toggle' ? floatButton : floatPanel;},
  contains(target) {return target === floatButton || target === floatPanel;}
};
const floatSection = {bottom: 400, getBoundingClientRect() {return {bottom: this.bottom};}};
const floatDocument = {
  documentElement: {lang: 'en'},
  querySelector(selector) {return selector === '.journey-index' ? floatSection : floatRoot;},
  addEventListener(name, handler) {floatHandlers[name] = handler;}
};
const floatWindow = {
  KOMICOVE_MESSAGES: messages,
  addEventListener(name, handler) {floatHandlers[name] = handler;}
};
vm.runInNewContext(fs.readFileSync(path.join(root, 'float-nav.js'), 'utf8'), {
  window: floatWindow, document: floatDocument, requestAnimationFrame: callback => callback()
});
assert.equal(floatRoot.inert, true, 'Floating control should begin inactive');
floatSection.bottom = 80;
floatHandlers.scroll();
assert.equal(floatRoot.inert, false, 'Floating control should appear after the quick paths leave');
assert.ok(floatClasses.has('is-visible'));
floatButton.handlers.click({detail: 1});
assert.equal(floatPanel.hidden, false, 'Floating menu should open');
assert.equal(floatButton.attrs['aria-expanded'], 'true');
floatHandlers.keydown({key: 'Escape'});
assert.equal(floatPanel.hidden, true, 'Escape should close the floating menu');
assert.equal(floatButton.focused, true, 'Escape should restore focus');
floatButton.handlers.click({detail: 1});
floatHandlers.pointerdown({target: {}});
assert.equal(floatPanel.hidden, true, 'Outside click should close the floating menu');
floatDocument.documentElement.lang = 'pt-BR';
floatWindow.KomicoveFloat.syncLabels();
assert.equal(floatButton.attrs['aria-label'], messages['pt-BR']['journey.floatOpen']);
floatButton.handlers.click({detail: 1});
floatSection.bottom = 400;
floatHandlers.scroll();
assert.equal(floatRoot.inert, true, 'Floating control should disappear when the quick paths return');
assert.equal(floatPanel.hidden, true, 'Floating menu should close when the quick paths return');
for (const [file, html] of Object.entries(htmlByPage)) {
  const boot = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(boot, `Missing inline theme bootstrap in ${file}`);
  for (const [preference, systemDark, expected] of [[null, true, 'dark'], [null, false, 'light'], ['light', true, 'light'], ['dark', false, 'dark']]) {
    const page = {documentElement: {dataset: {}}};
    vm.runInNewContext(boot, {document: page, localStorage: {getItem: () => preference}, matchMedia: () => ({matches: systemDark})});
    assert.equal(page.documentElement.dataset.theme, expected, `Wrong initial theme in ${file}`);
  }
}
const themeButton = {
  attrs: {}, handlers: {},
  setAttribute(name, value) {this.attrs[name] = value;},
  addEventListener(name, handler) {this.handlers[name] = handler;}
};
const themeRoot = {dataset: {theme: 'dark'}, style: {}, lang: 'en'};
const themeMeta = {content: ''};
const themeIcon = {href: ''};
const themeStorage = new Map();
const themeWindow = {KOMICOVE_MESSAGES: messages, addEventListener() {}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'theme.js'), 'utf8'), {
  window: themeWindow,
  document: {
    documentElement: themeRoot,
    querySelectorAll: () => [themeButton],
    querySelector: selector => selector.includes('theme-color') ? themeMeta : themeIcon
  },
  localStorage: {getItem: key => themeStorage.get(key) ?? null, setItem: (key, value) => themeStorage.set(key, value)},
  matchMedia: () => ({matches: true, addEventListener() {}})
});
assert.equal(themeButton.attrs['aria-label'], messages.en['theme.toLight']);
themeButton.handlers.click();
assert.equal(themeRoot.dataset.theme, 'light');
assert.equal(themeStorage.get('komicove.site.theme'), 'light');
assert.equal(themeIcon.href, 'assets/komicove.ico');
themeRoot.lang = 'pt-BR';
themeWindow.KomicoveTheme.syncLabels();
assert.equal(themeButton.attrs['aria-label'], messages['pt-BR']['theme.toDark']);
const adminHtml = fs.readFileSync(path.join(__dirname, '../komicove_backend/web/moderators.html'), 'utf8');
assert.match(adminHtml, /id="panelTheme"/, 'Missing admin theme control');
assert.match(adminHtml, /brand-emblem/, 'Missing admin K mark');
const adminScripts = [...adminHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
for (const source of adminScripts) new vm.Script(source);
const adminRoot = {dataset: {theme: 'light'}, style: {}};
const adminSymbol = {textContent: ''};
const adminControl = {
  attrs: {}, handlers: {},
  setAttribute(name, value) {this.attrs[name] = value;},
  addEventListener(name, handler) {this.handlers[name] = handler;},
  querySelector: () => adminSymbol
};
const adminLanguage = {addEventListener() {}};
const adminStorage = new Map();
vm.runInNewContext(adminScripts[1], {
  document: {documentElement: adminRoot, getElementById: id => id === 'panelTheme' ? adminControl : adminLanguage},
  localStorage: {getItem: key => adminStorage.get(key) ?? null, setItem: (key, value) => adminStorage.set(key, value)},
  matchMedia: () => ({matches: false, addEventListener() {}}),
  window: {addEventListener() {}},
  panelLanguage: 'en'
});
adminControl.handlers.click();
assert.equal(adminRoot.dataset.theme, 'dark', 'Admin theme toggle');
assert.equal(adminControl.attrs['aria-label'], 'Switch to light mode');
assert.equal(adminStorage.get('komicove.site.theme'), 'dark', 'Admin theme persistence');
assert.doesNotMatch(adminHtml, /\u2014/, 'Admin page contains an em dash');
for (const [file, html] of Object.entries(htmlByPage)) {
  assert.match(html, /<html lang="en">/, `${file} must use English as its static language`);
  assert.doesNotMatch(html, /\u2014/, `${file} contains an em dash`);
}
for (const file of ['app.js', 'news.js', 'guide.js', 'help-hub.js', 'home-url.js', 'download-versions.js', 'float-nav.js', 'theme.js', 'translations.js', 'cinematic.css', 'mobile.css', 'help.css', 'download-versions.css', 'styles.css']) {
  assert.doesNotMatch(fs.readFileSync(path.join(root, file), 'utf8'), /\u2014/, `${file} contains an em dash`);
}

console.log(`Site checks passed: ${translatedElements} translated elements, ${Object.keys(messages.en).length} messages per language, all pages, sections, screenshots and local assets present.`);
