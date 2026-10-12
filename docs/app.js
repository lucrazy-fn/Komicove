// Local assets and shared translations keep the site usable without a build step.
const messages = window.KOMICOVE_MESSAGES;
const languageKey = 'komicove.site.language';
let language = 'en';
try { if (localStorage.getItem(languageKey) === 'pt-BR') language = 'pt-BR'; } catch { /* Storage may be unavailable in private contexts. */ }
const t = key => messages[language][key] ?? messages.en[key] ?? key;
function translatePage() {
  document.documentElement.lang = language;
  document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
  for (const attribute of ['aria-label', 'alt']) {
    document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(node => node.setAttribute(attribute, t(node.getAttribute(`data-i18n-${attribute}`))));
  }
  document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
  document.title = t('meta.title');
  for (const selector of ['meta[name="description"]', 'meta[name="twitter:description"]', 'meta[property="og:description"]']) document.querySelector(selector).content = t('meta.description');
  for (const selector of ['meta[name="twitter:title"]', 'meta[property="og:title"]']) document.querySelector(selector).content = t('meta.title');
  document.querySelector('meta[property="og:locale"]').content = language === 'en' ? 'en_US' : 'pt_BR';
  window.KomicoveTheme?.syncLabels();
  window.KomicoveFloat?.syncLabels();
}
translatePage();
const screens = {
  biblioteca: {image: 'screenshots/desktop-biblioteca.png'},
  leitor: {image: 'screenshots/desktop-leitor.png'},
  pastas: {image: 'screenshots/desktop-pastas.png'}
};
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const demoVideos = [...document.querySelectorAll('.demo-video')];
const androidDemo = document.querySelector('#android-demo');
const androidDemoPlay = document.querySelector('#android-demo-play');
if (androidDemo && androidDemoPlay) {
  const syncAndroidPlay = () => androidDemo.parentElement.classList.toggle('is-playing', !androidDemo.paused);
  androidDemoPlay.addEventListener('click', () => androidDemo.play().catch(() => {}));
  androidDemo.addEventListener('play', syncAndroidPlay);
  androidDemo.addEventListener('pause', syncAndroidPlay);
}
if (demoVideos.length === 2 && 'IntersectionObserver' in window) {
  const compactDemo = matchMedia('(max-width:800px)');
  const visibleDemos = new Set();
  let autoDemo = null;
  const syncDemoPlayback = () => {
    if (reduced.matches || document.hidden) {
      demoVideos.forEach(video => video.pause());
      autoDemo = null;
      return;
    }
    const preferred = compactDemo.matches ? demoVideos[1] : demoVideos[0];
    if (autoDemo && (autoDemo !== preferred || !visibleDemos.has(autoDemo))) {
      autoDemo.pause();
      autoDemo = null;
    }
    if (!visibleDemos.has(preferred) || demoVideos.some(video => video !== preferred && !video.paused)) return;
    if (!autoDemo && preferred.paused) {
      autoDemo = preferred;
      preferred.play().catch(() => { if (autoDemo === preferred) autoDemo = null; });
    }
  };
  const demoObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) visibleDemos.add(entry.target);
      else visibleDemos.delete(entry.target);
    }
    syncDemoPlayback();
  }, {threshold: .35});
  demoVideos.forEach(video => {
    demoObserver.observe(video);
    video.addEventListener('play', () => {
      demoVideos.forEach(other => { if (other !== video) other.pause(); });
      if (autoDemo && autoDemo !== video) autoDemo = null;
    });
  });
  reduced.addEventListener('change', syncDemoPlayback);
  compactDemo.addEventListener('change', syncDemoPlayback);
  document.addEventListener('visibilitychange', syncDemoPlayback);
}
const mobileMenu = matchMedia('(max-width:900px)');
document.documentElement.classList.add('js');
const menu = document.querySelector('#menu');
const toggle = document.querySelector('.menu-toggle');
function setMenu(open) {
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', t(open ? 'nav.close' : 'nav.open'));
  menu.classList.toggle('open', open);
  menu.inert = !open && mobileMenu.matches;
}
toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (toggle.getAttribute('aria-expanded') === 'true') { setMenu(false); toggle.focus(); }
});
mobileMenu.addEventListener('change', () => setMenu(false));
setMenu(false);

if ('IntersectionObserver' in window && !reduced.matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const siblings = [...entry.target.parentElement.children];
    const delay = entry.target.classList.contains('feature') ? (siblings.indexOf(entry.target) % 3) * 65 : 0;
    entry.target.animate([{opacity: .25, transform: 'translateY(22px)'}, {opacity: 1, transform: 'none'}], {duration: 600, delay, easing: 'cubic-bezier(.2,.75,.25,1)'});
    observer.unobserve(entry.target);
  }), {threshold: .12});
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

const tabs = [...document.querySelectorAll('[data-tab]')];
const tablist = document.querySelector('.gallery-controls');
const body = document.querySelector('#gallery-body');
const lightbox = document.querySelector('#lightbox');
let selected = 'biblioteca';
tablist.setAttribute('role', 'tablist');
body.setAttribute('role', 'tabpanel');
body.tabIndex = 0;
function contentFor(key) {
  const screen = screens[key];
  if (screen.image) {
    const img = document.createElement('img');
    img.src = screen.image; img.alt = t(`screen.${key}.alt`); img.loading = 'lazy'; img.decoding = 'async';
    img.addEventListener('error', () => img.replaceWith(placeholderFor(key)), {once:true});
    return img;
  }
  return placeholderFor(key);
}
function placeholderFor(key) {
  const div = document.createElement('div'); div.className = 'placeholder';
  for (const [tag, className, text] of [
    ['span', 'placeholder-tag', t('gallery.error')], ['strong', '', t(`screen.${key}.title`)],
    ['p', '', t(`screen.${key}.description`)], ['span', 'placeholder-foot', t('gallery.errorHelp')]
  ]) {const node = document.createElement(tag); node.className = className; node.textContent = text; div.append(node);}
  return div;
}
function selectTab(key) {
  selected = key;
  tabs.forEach(tab => {const active = tab.dataset.tab === key; tab.classList.toggle('selected', active); tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;});
  body.setAttribute('aria-labelledby', `tab-${key}`);
  body.replaceChildren(contentFor(key));
  document.querySelector('#gallery-title').textContent = `Komicove / ${t(`screen.${key}.title`)}`;
  if (!reduced.matches) body.animate([{opacity:.1,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{duration:320,easing:'ease-out'});
}
tabs.forEach((tab, index) => {
  tab.id = `tab-${tab.dataset.tab}`; tab.setAttribute('role','tab'); tab.setAttribute('aria-controls','gallery-body');
  tab.addEventListener('click', () => selectTab(tab.dataset.tab));
  tab.addEventListener('keydown', e => {
    let next;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = tabs.length - 1;
    if (next !== undefined) {e.preventDefault(); tabs[next].focus(); selectTab(tabs[next].dataset.tab);}
  });
});
selectTab(selected);
document.querySelector('#expand').addEventListener('click', () => {
  document.querySelector('#modal-title').textContent = `Komicove / ${t(`screen.${selected}.title`)}`;
  document.querySelector('#modal-content').replaceChildren(contentFor(selected));
  lightbox.showModal();
  if (!reduced.matches) lightbox.animate([{opacity:0,transform:'translateY(12px) scale(.98)'},{opacity:1,transform:'none'}],{duration:250,easing:'ease-out'});
});
document.querySelector('#close-modal').addEventListener('click', () => lightbox.close());
lightbox.addEventListener('click', e => {if(e.target === lightbox) {const r=lightbox.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom) lightbox.close();}});
lightbox.addEventListener('close', () => document.querySelector('#expand').focus());

const supportDialog = document.querySelector('#support-dialog');
const copyPix = document.querySelector('#copy-pix');
const copyStatus = document.querySelector('#copy-status');
const keyCopyStatus = document.querySelector('#key-copy-status');
let supportTrigger = null;
document.querySelectorAll('[data-open-support]').forEach(button => button.addEventListener('click', () => {
  supportTrigger = button;
  copyStatus.textContent = '';
  keyCopyStatus.textContent = '';
  if (button.closest('#menu')) setMenu(false);
  supportDialog.showModal();
  if (!reduced.matches) supportDialog.animate([{opacity:0,transform:'translateY(12px) scale(.98)'},{opacity:1,transform:'none'}],{duration:250,easing:'ease-out'});
}));
document.querySelector('#close-support').addEventListener('click', () => supportDialog.close());
supportDialog.addEventListener('click', event => {
  if (event.target !== supportDialog) return;
  const rect = supportDialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) supportDialog.close();
});
supportDialog.addEventListener('close', () => supportTrigger?.focus());
copyPix.addEventListener('click', async () => {
  const code = document.querySelector('#pix-code').textContent.trim();
  try {
    await navigator.clipboard.writeText(code);
    copyStatus.textContent = t('support.copied');
  } catch {
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('#pix-code'));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    copyStatus.textContent = t('support.copyError');
  }
});
document.querySelector('#copy-key').addEventListener('click', async () => {
  const key = document.querySelector('#pix-key').textContent.trim();
  try {
    await navigator.clipboard.writeText(key);
    keyCopyStatus.textContent = t('support.keyCopied');
  } catch {
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('#pix-key'));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    keyCopyStatus.textContent = t('support.copyError');
  }
});

function changeLanguage(next, persist = true) {
  language = next === 'pt-BR' ? 'pt-BR' : 'en';
  if (persist) { try { localStorage.setItem(languageKey, language); } catch { /* Language switching still works without storage. */ } }
  translatePage();
  setMenu(toggle.getAttribute('aria-expanded') === 'true');
  selectTab(selected);
  if (lightbox.open) {
    document.querySelector('#modal-title').textContent = `Komicove / ${t(`screen.${selected}.title`)}`;
    document.querySelector('#modal-content').replaceChildren(contentFor(selected));
  }
}
document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => changeLanguage(button.dataset.language)));
window.addEventListener('storage', event => { if (event.key === languageKey) changeLanguage(event.newValue, false); });

// Keep the menu usable with keyboards and close it when clicking outside.
document.addEventListener('click', event => {
  if (!event.target.closest('.header')) {
    if (toggle.getAttribute('aria-expanded') === 'true') setMenu(false);
    more.open = false;
  }
});
document.addEventListener('focusin', event => {
  if (!event.target.closest('.header')) {
    if (toggle.getAttribute('aria-expanded') === 'true') setMenu(false);
    more.open = false;
  }
});

document.querySelectorAll('.questions details').forEach(details => {
  let animation = null;
  let targetOpen = false;
  const summary = details.querySelector('summary');
  summary.addEventListener('click', e => {
    if (reduced.matches || !details.animate) return;
    e.preventDefault();
    const start = details.getBoundingClientRect().height;
    targetOpen = animation ? !targetOpen : !details.open;
    if (animation) animation.cancel();
    details.open = true;
    const end = targetOpen ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height + 1;
    details.style.overflow = 'hidden';
    animation = details.animate({height:[`${start}px`,`${end}px`]},{duration:260,easing:'cubic-bezier(.2,.75,.25,1)'});
    animation.onfinish = () => {details.open = targetOpen; details.style.overflow = ''; animation = null;};
  });
});
