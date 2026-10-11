const messages = window.KOMICOVE_MESSAGES;
const languageKey = 'komicove.site.language';
const page = document.body.dataset.page;
document.documentElement.classList.add('js');
let language = 'en';
try { if (localStorage.getItem(languageKey) === 'pt-BR') language = 'pt-BR'; } catch { /* Storage may be unavailable. */ }
const t = key => messages[language][key] ?? messages.en[key] ?? key;

function translatePage() {
  document.documentElement.lang = language;
  document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
  for (const attribute of ['aria-label', 'alt']) {
    document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(node => node.setAttribute(attribute, t(node.getAttribute(`data-i18n-${attribute}`))));
  }
  document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
  const prefix = page === 'apoie' ? 'supportPage' : page === 'tutoriais' ? 'tutorials' : page === 'download' ? 'help.download' : 'docs';
  const titleKey = page === 'download' ? `${prefix}MetaTitle` : `${prefix}.metaTitle`;
  const descriptionKey = page === 'download' ? `${prefix}MetaDescription` : `${prefix}.metaDescription`;
  document.title = t(titleKey);
  document.querySelector('meta[name="description"]').content = t(descriptionKey);
  document.querySelector('meta[property="og:title"]').content = t(titleKey);
  document.querySelector('meta[property="og:description"]').content = t(descriptionKey);
  document.querySelector('meta[property="og:locale"]').content = language === 'en' ? 'en_US' : 'pt_BR';
  window.KomicoveTheme?.syncLabels();
}
function changeLanguage(next, persist = true) {
  language = next === 'pt-BR' ? 'pt-BR' : 'en';
  if (persist) { try { localStorage.setItem(languageKey, language); } catch { /* The page still switches. */ } }
  translatePage();
}
document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => changeLanguage(button.dataset.language)));
window.addEventListener('storage', event => { if (event.key === languageKey) changeLanguage(event.newValue, false); });

const menu = document.querySelector('#menu');
const toggle = document.querySelector('.menu-toggle');
const mobileMenu = matchMedia('(max-width:900px)');
function setMenu(open) {
  menu.classList.toggle('open', open);
  menu.inert = !open && mobileMenu.matches;
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', t(open ? 'nav.close' : 'nav.open'));
}
toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
menu.addEventListener('click', event => { if (event.target.closest('a')) setMenu(false); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') setMenu(false); });
document.addEventListener('click', event => { if (!event.target.closest('.nav')) setMenu(false); });
mobileMenu.addEventListener('change', () => setMenu(false));
setMenu(false);

for (const [buttonId, codeId] of [['copy-pix', 'pix-code'], ['copy-key', 'pix-key']]) {
  const button = document.getElementById(buttonId);
  if (!button) continue;
  button.addEventListener('click', async () => {
    const status = document.getElementById('copy-status');
    try {
      await navigator.clipboard.writeText(document.getElementById(codeId).textContent);
      status.textContent = t('supportPage.copied');
    } catch {
      status.textContent = t('supportPage.copyError');
    }
  });
}
translatePage();
