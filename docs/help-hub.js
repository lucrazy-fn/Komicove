/* A compact, shared reading desk for Docs, Tutorials and Downloads. */
(() => {
  const main = document.querySelector('main.guide-main');
  if (!main) return;

  const topics = [
    ['help.downloads', 'download.html', 'download'],
    ['help.release', 'novidades.html', 'release'],
    ['docs.gettingStarted', 'docs.html#inicio', 'docs'],
    ['docs.androidTitle', 'docs.html#android-guide', 'docs'],
    ['docs.desktopTitle', 'docs.html#desktop-guide', 'docs'],
    ['docs.library', 'docs.html#biblioteca', 'docs'],
    ['docs.reader', 'docs.html#leitor', 'docs'],
    ['docs.formats', 'docs.html#arquivos', 'docs'],
    ['docs.backupTitle', 'docs.html#backup', 'docs'],
    ['nav.tutorials', 'tutoriais.html', 'tutorial'],
    ['tutorials.androidTitle', 'tutoriais.html#tutorial-android', 'tutorial'],
    ['tutorials.desktopTitle', 'tutoriais.html#tutorial-desktop', 'tutorial'],
    ['tutorials.readerTitle', 'tutoriais.html#tutorial-reader', 'tutorial'],
    ['tutorials.libraryTitle', 'tutoriais.html#tutorial-library', 'tutorial'],
    ['tutorials.backupTitle', 'tutoriais.html#tutorial-backup', 'tutorial'],
    ['tutorials.helpTitle', 'tutoriais.html#tutorial-help', 'tutorial'],
    ['docs.help', 'docs.html#ajuda', 'help'],
    ['nav.support', 'apoie.html', 'help']
  ];
  const groups = [
    ['help.groupGet', 'download', 'release'],
    ['help.groupRead', 'docs'],
    ['help.groupTutorials', 'tutorial'],
    ['help.groupMore', 'help']
  ];
  const currentPage = document.body.dataset.page;
  const currentFile = location.pathname.split('/').pop() || 'index.html';
  const shell = document.createElement('div');
  shell.className = 'help-shell';
  const sidebar = document.createElement('aside');
  sidebar.className = 'help-sidebar';
  sidebar.id = 'help-sidebar';
  sidebar.setAttribute('aria-label', 'Documentation navigation');
  sidebar.setAttribute('data-i18n-aria-label', 'help.sidebarLabel');
  sidebar.innerHTML = `
    <div class="help-sidebar-head"><img class="help-sidebar-logo" src="assets/logo.png" alt="" width="55" height="37"><div><small data-i18n="help.libraryLabel">KOMICOVE / FIELD NOTES</small><strong data-i18n="help.helpCenter">Reader's desk</strong></div></div>
    <label class="help-search"><span aria-hidden="true">⌕</span><input type="search" autocomplete="off" data-i18n-placeholder="help.search" placeholder="Find a topic" aria-label="Find a topic" data-i18n-aria-label="help.search"><kbd>/</kbd></label>
    <nav aria-label="Documentation topics" data-i18n-aria-label="help.topicsLabel">${groups.map(([label, ...types]) => `<div class="help-nav-group"><p data-i18n="${label}"></p>${topics.filter(([, , type]) => types.includes(type)).map(([key, href]) => `<a href="${href}" data-i18n="${key}"></a>`).join('')}</div>`).join('')}</nav>
    <p class="help-no-results" data-i18n="help.noResults" hidden>No matching topic.</p>
    <a class="help-sidebar-support" href="apoie.html"><span data-i18n="help.supportTitle">Help keep the pages turning</span><span aria-hidden="true">↗</span></a>`;

  const body = document.createElement('div');
  body.className = 'help-article';
  while (main.firstChild) body.append(main.firstChild);
  shell.append(sidebar, body);
  const pageIndex = body.querySelector('.guide-index');
  if (pageIndex) {
    pageIndex.classList.add('help-page-index');
    const rail = document.createElement('aside');
    rail.className = 'help-rail';
    rail.append(pageIndex);
    shell.append(rail);
  }
  main.append(shell);
  const sidebarToggle = document.createElement('button');
  sidebarToggle.className = 'help-sidebar-toggle';
  sidebarToggle.type = 'button';
  sidebarToggle.setAttribute('aria-controls', 'help-sidebar');
  sidebarToggle.setAttribute('aria-expanded', 'false');
  sidebarToggle.innerHTML = '<span aria-hidden="true">☷</span><span data-i18n="help.browse">Browse topics</span>';
  main.prepend(sidebarToggle);
  main.classList.add('help-ready');

  function syncLocale() {
    const selected = document.documentElement.lang === 'pt-BR' ? 'pt-BR' : 'en';
    const dictionary = window.KOMICOVE_MESSAGES?.[selected] || window.KOMICOVE_MESSAGES?.en || {};
    main.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = dictionary[node.dataset.i18n] || node.dataset.i18n; });
    main.querySelectorAll('[data-i18n-aria-label]').forEach(node => node.setAttribute('aria-label', dictionary[node.dataset.i18nAriaLabel] || node.dataset.i18nAriaLabel));
    main.querySelectorAll('[data-i18n-placeholder]').forEach(node => node.placeholder = dictionary[node.dataset.i18nPlaceholder] || node.dataset.i18nPlaceholder);
    filterTopics();
  }
  const search = sidebar.querySelector('input');
  const navLinks = [...sidebar.querySelectorAll('nav a')];
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function filterTopics() {
    const query = normalize(search.value.trim());
    let visible = 0;
    navLinks.forEach(link => {
      const matches = !query || normalize(link.textContent).includes(query);
      link.hidden = !matches;
      if (matches) visible++;
    });
    sidebar.querySelectorAll('.help-nav-group').forEach(group => { group.hidden = !group.querySelector('a:not([hidden])'); });
    sidebar.querySelector('.help-no-results').hidden = visible > 0;
  }
  search.addEventListener('input', filterTopics);
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !event.altKey && !event.ctrlKey && !event.metaKey && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      if (matchMedia('(max-width: 980px)').matches) setSidebar(true);
      search.focus();
    }
    if (event.key === 'Escape' && main.classList.contains('help-sidebar-open')) {
      setSidebar(false);
      sidebarToggle.focus();
    }
  });
  function setSidebar(open) {
    main.classList.toggle('help-sidebar-open', open);
    sidebarToggle.setAttribute('aria-expanded', String(open));
    if (matchMedia('(max-width: 980px)').matches) sidebar.inert = !open;
    else sidebar.inert = false;
  }
  sidebarToggle.addEventListener('click', () => setSidebar(sidebarToggle.getAttribute('aria-expanded') !== 'true'));
  sidebar.addEventListener('click', event => { if (event.target.closest('a')) setSidebar(false); });
  document.addEventListener('click', event => { if (!event.target.closest('.help-sidebar, .help-sidebar-toggle')) setSidebar(false); });
  matchMedia('(max-width: 980px)').addEventListener('change', () => setSidebar(false));
  setSidebar(false);

  const markActive = () => {
    navLinks.forEach(link => {
      const target = link.getAttribute('href');
      const [file, fragment] = target.split('#');
      const active = file === currentFile && (fragment ? fragment === location.hash.slice(1) : !location.hash);
      link.classList.toggle('is-current', active);
      if (active) link.setAttribute('aria-current', fragment ? 'location' : 'page');
      else link.removeAttribute('aria-current');
    });
    if (currentPage === 'docs' && !location.hash) {
      const firstTopic = navLinks.find(link => link.getAttribute('href') === 'docs.html#inicio');
      firstTopic?.classList.add('is-current');
      firstTopic?.setAttribute('aria-current', 'location');
    }
  };
  window.addEventListener('hashchange', markActive);
  markActive();
  const languageButtons = document.querySelectorAll('[data-language]');
  languageButtons.forEach(button => button.addEventListener('click', () => queueMicrotask(syncLocale)));
  window.addEventListener('storage', event => { if (event.key === 'komicove.site.language') queueMicrotask(syncLocale); });
  syncLocale();
})();
