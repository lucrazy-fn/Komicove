// The early head script sets the theme before CSS; this file manages controls.
(() => {
  const key = 'komicove.site.theme';
  const system = matchMedia('(prefers-color-scheme: dark)');
  const root = document.documentElement;
  const stored = () => {
    try { return localStorage.getItem(key); } catch { return null; }
  };
  const chosen = () => stored() === 'light' || stored() === 'dark';
  const label = theme => {
    const language = root.lang === 'pt-BR' ? 'pt-BR' : 'en';
    const messages = window.KOMICOVE_MESSAGES?.[language];
    return messages?.[theme === 'dark' ? 'theme.toLight' : 'theme.toDark'] || (theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  };
  function syncLabels() {
    const theme = root.dataset.theme === 'dark' ? 'dark' : 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-label', label(theme));
      button.setAttribute('title', label(theme));
      button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
  }
  function apply(theme, save = false) {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = theme === 'dark' ? '#101217' : '#f5f3ef';
    const favicon = document.querySelector('link[rel="icon"]');
    if (favicon) favicon.href = 'assets/komicove.ico';
    if (save) { try { localStorage.setItem(key, theme); } catch { /* The current page still switches. */ } }
    syncLabels();
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
    apply(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
  }));
  system.addEventListener('change', event => { if (!chosen()) apply(event.matches ? 'dark' : 'light'); });
  window.addEventListener('storage', event => {
    if (event.key === key) apply(event.newValue === 'light' || event.newValue === 'dark' ? event.newValue : system.matches ? 'dark' : 'light');
  });
  window.KomicoveTheme = {syncLabels};
  apply(root.dataset.theme === 'dark' ? 'dark' : 'light');
})();
