// Keep the quick paths available after their full section scrolls away.
(() => {
  const section = document.querySelector('.journey-index');
  const root = document.querySelector('.journey-float');
  if (!section || !root) return;

  const button = root.querySelector('.journey-float-toggle');
  const panel = root.querySelector('.journey-float-panel');
  let framePending = false;

  function syncLabels() {
    const language = document.documentElement.lang === 'pt-BR' ? 'pt-BR' : 'en';
    const key = button.getAttribute('aria-expanded') === 'true' ? 'journey.floatClose' : 'journey.floatOpen';
    const label = window.KOMICOVE_MESSAGES[language][key];
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
  }

  function setOpen(open) {
    const next = open && root.classList.contains('is-visible');
    panel.hidden = !next;
    button.setAttribute('aria-expanded', String(next));
    root.classList.toggle('is-open', next);
    syncLabels();
  }

  function updateVisibility() {
    const visible = section.getBoundingClientRect().bottom <= 96;
    if (!visible) setOpen(false);
    root.classList.toggle('is-visible', visible);
    root.inert = !visible;
    button.tabIndex = visible ? 0 : -1;
  }

  function scheduleVisibility() {
    if (framePending) return;
    framePending = true;
    requestAnimationFrame(() => {
      framePending = false;
      updateVisibility();
    });
  }

  button.addEventListener('click', event => {
    const opening = button.getAttribute('aria-expanded') !== 'true';
    setOpen(opening);
    if (opening && event.detail === 0) panel.querySelector('a')?.focus();
  });
  panel.addEventListener('click', event => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('pointerdown', event => {
    if (!root.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || button.getAttribute('aria-expanded') !== 'true') return;
    setOpen(false);
    button.focus();
  });
  window.addEventListener('scroll', scheduleVisibility, {passive: true});
  window.addEventListener('resize', scheduleVisibility);
  window.addEventListener('pageshow', scheduleVisibility);
  window.KomicoveFloat = {syncLabels};
  syncLabels();
  updateVisibility();
  requestAnimationFrame(updateVisibility);
})();
