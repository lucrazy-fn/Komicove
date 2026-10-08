const messages = window.KOMICOVE_MESSAGES;
const languageKey = 'komicove.site.language';
let language = 'en';
try { if (localStorage.getItem(languageKey) === 'pt-BR') language = 'pt-BR'; } catch { /* Storage may be unavailable. */ }
const t = key => messages[language][key] ?? messages.en[key] ?? key;

function translateNews() {
  document.documentElement.lang = language;
  document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
  for (const attribute of ['aria-label', 'alt']) {
    document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(node => node.setAttribute(attribute, t(node.getAttribute(`data-i18n-${attribute}`))));
  }
  document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
  document.title = t('release.metaTitle');
  document.querySelector('meta[name="description"]').content = t('release.metaDescription');
  document.querySelector('meta[property="og:title"]').content = t('release.metaTitle');
  document.querySelector('meta[property="og:description"]').content = t('release.metaDescription');
  document.querySelector('meta[property="og:locale"]').content = language === 'en' ? 'en_US' : 'pt_BR';
}

function changeLanguage(next, persist = true) {
  language = next === 'pt-BR' ? 'pt-BR' : 'en';
  if (persist) { try { localStorage.setItem(languageKey, language); } catch { /* The page still switches languages. */ } }
  translateNews();
}

document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => changeLanguage(button.dataset.language)));
window.addEventListener('storage', event => { if (event.key === languageKey) changeLanguage(event.newValue, false); });
translateNews();
