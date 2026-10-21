/* Keep every package link and download count tied to one selected GitHub release. */
(() => {
  const repository = 'lucrazy-fn/PANEL-ComicBookReader';
  const endpoint = `https://api.github.com/repos/${repository}/releases?per_page=100`;
  const cacheKey = 'komicove.site.releaseCatalog.v2';
  // Version the preference key when a release must become the default for everyone.
  // Existing visitors start on 0.2.2 once, then their next manual choice is remembered.
  const choiceKey = 'komicove.site.downloadVersion.v022';
  const fallbackFiles = {
    'v0.2.2': ['Komicove-Android-0.2.2.apk', 'Komicove-Linux-0.2.2-x86_64.flatpak', 'Komicove-Linux-0.2.2-x86_64.tar.gz', 'Komicove-Setup-0.2.2.exe', 'Komicove-Windows-0.2.2-portable.zip'],
    'v0.2.1.1': ['Komicove-Android-0.2.1.1.apk', 'Komicove-Linux-0.2.1.1-x86_64.flatpak', 'Komicove-Linux-0.2.1.1-x86_64.tar.gz', 'Komicove-Setup-0.2.1.1.exe', 'Komicove-Windows-0.2.1.1-portable.zip'],
    'v0.2.1': ['Komicove-Android-0.2.1.apk', 'Komicove-Linux-0.2.1-x86_64.flatpak', 'Komicove-Linux-0.2.1-x86_64.tar.gz', 'Komicove-Setup-0.2.1.exe', 'Komicove-Windows-0.2.1-portable.zip'],
    'v0.2.0': ['Komicove-Android-0.2.0.apk', 'Komicove-Linux-0.2.0-x86_64.flatpak', 'Komicove-Linux-0.2.0-x86_64.tar.gz', 'Komicove-Setup-0.2.0.exe'],
    'v0.1.0': ['Komicove-Android-0.1.0.apk', 'Komicove-Linux-0.1.0-x86_64.flatpak', 'Komicove-Linux-0.1.0-x86_64.tar.gz', 'Komicove-Setup-0.1.0.exe'],
    'v1.7.1': ['PANEL-Android-1.6.1.apk', 'PANEL-Linux-1.7.1-x86_64.flatpak', 'PANEL-Linux-1.7.1-x86_64.tar.gz', 'PANEL-Setup-1.7.1.exe'],
    'v1.7': ['PANEL-Android-1.6.0.apk', 'PANEL-Linux-1.7.0-x86_64.flatpak', 'PANEL-Linux-1.7.0-x86_64.tar.gz', 'PANEL-Setup-1.7.0.exe'],
    'Correção': ['PANEL-Linux-1.7.0-correction-x86_64.flatpak', 'PANEL-Linux-1.7.0-correction-x86_64.tar.gz'],
    'v1.6.1': ['PANEL-Android-1.5.1.apk', 'PANEL-Setup-1.6.1.exe'],
    'v1.6': ['PANEL-Android-1.5.0.apk', 'PANEL-Setup-1.6.0.exe'],
    'v1.5': ['PANEL-Android-1.4.0.apk', 'PANEL-Setup-1.5.0.exe'],
    'v1.4.2': ['PANEL-ComicReader-1.3.2.apk', 'PANEL-Setup-1.4.2.exe'],
    'v1.4.1': ['PANEL-ComicReader-1.3.1.apk', 'PANEL-Setup-1.4.1.exe'],
    'v1.4': ['PANEL-ComicReader-1.3.0.apk', 'PANEL-Setup-1.4.0.exe'],
    'v1.3': ['PANEL-Setup-1.3.0.exe'],
    'v1.2-Beta': ['Panel_Reader_Setup_v1.2_Beta.exe'],
    'v1.1': ['Panel_Reader_Setup_v1.1.exe'],
    'v1.0': ['Panel_ComicReader_Setup.exe']
  };
  const releaseUrl = tag => `https://github.com/${repository}/releases/tag/${encodeURIComponent(tag)}`;
  const assetUrl = (tag, name) => `https://github.com/${repository}/releases/download/${encodeURIComponent(tag)}/${encodeURIComponent(name)}`;
  const fallback = Object.entries(fallbackFiles).map(([tag, names]) => ({
    tag,
    url: releaseUrl(tag),
    family: names.some(name => /^Komicove-/i.test(name)) ? 'komicove' : 'panel',
    assets: names.map(name => ({name, url: assetUrl(tag, name), count: null}))
  }));

  function assetKind(name) {
    if (/\.apk$/i.test(name)) return 'android';
    if (/portable\.zip$/i.test(name)) return 'portable';
    if (/\.exe$/i.test(name)) return 'windows';
    if (/\.tar\.gz$/i.test(name)) return 'linux';
    if (/\.flatpak$/i.test(name)) return 'flatpak';
    return null;
  }
  function normalizeReleases(raw) {
    if (!Array.isArray(raw)) throw new Error('Invalid release catalog');
    const releases = raw.filter(item => !item.draft && typeof item.tag_name === 'string')
      .map(item => ({
        tag: item.tag_name,
        url: releaseUrl(item.tag_name),
        family: (item.assets || []).some(asset => /^Komicove-/i.test(asset.name)) ? 'komicove' : 'panel',
        publishedAt: Date.parse(item.published_at || item.created_at || '') || 0,
        assets: (Array.isArray(item.assets) ? item.assets : []).map(asset => ({
          name: asset.name,
          url: asset.browser_download_url?.startsWith('https://github.com/') ? asset.browser_download_url : assetUrl(item.tag_name, asset.name),
          count: Number.isFinite(Number(asset.download_count)) ? Number(asset.download_count) : null
        }))
      })).filter(item => item.assets.length).sort((a, b) => b.publishedAt - a.publishedAt);
    if (!releases.length) throw new Error('No packages in release catalog');
    const allTotal = releases.reduce((sum, release) => sum + release.assets.reduce((assetSum, asset) => assetSum + (asset.count || 0), 0), 0);
    return {releases, allTotal};
  }
  function releaseCounts(release) {
    const available = release.assets.every(asset => Number.isFinite(asset.count));
    const platforms = {android: 0, windows: 0, linux: 0};
    for (const asset of release.assets) {
      const kind = assetKind(asset.name);
      const platform = kind === 'portable' ? 'windows' : kind === 'flatpak' ? 'linux' : kind;
      if (platform && available) platforms[platform] += asset.count;
    }
    return {available, total: available ? release.assets.reduce((sum, asset) => sum + asset.count, 0) : null, platforms};
  }
  window.KomicoveReleaseCatalog = {assetKind, normalizeReleases, releaseCounts, fallback};

  if (typeof document === 'undefined') return;
  const picker = document.querySelector('[data-download-picker]');
  if (!picker) return;
  const details = picker.querySelector('[data-download-details]');
  const options = picker.querySelector('[data-download-options]');
  const summary = details.querySelector('summary');
  const messages = window.KOMICOVE_MESSAGES;
  const t = key => {
    const language = document.documentElement.lang === 'pt-BR' ? 'pt-BR' : 'en';
    return messages[language]?.[key] ?? messages.en[key] ?? key;
  };
  const formatter = () => new Intl.NumberFormat(document.documentElement.lang === 'pt-BR' ? 'pt-BR' : 'en');
  let catalog = {releases: fallback, allTotal: null};
  let selectedTag = null;
  try { selectedTag = localStorage.getItem(choiceKey); } catch { /* The selector still works for this visit. */ }
  let preferredTag = selectedTag;

  function render() {
    const releases = catalog.releases;
    if (!releases.some(item => item.tag === selectedTag)) selectedTag = releases[0].tag;
    const release = releases.find(item => item.tag === selectedTag);
    document.querySelectorAll('[data-download-current]').forEach(node => { node.textContent = release.tag; });
    document.querySelectorAll('[data-download-current-meta]').forEach(node => {
      node.textContent = release.family === 'panel' ? t('downloads.panelLegacy') : release.tag === releases[0].tag ? t('downloads.latest') : t('downloads.komicoveEdition');
    });
    const choiceNodes = [];
    for (const family of ['komicove', 'panel']) {
      const group = releases.filter(item => (item.family || 'komicove') === family);
      if (!group.length) continue;
      const heading = document.createElement('p');
      heading.className = 'download-options-heading';
      heading.textContent = t(family === 'panel' ? 'downloads.panelGroup' : 'downloads.komicoveGroup');
      choiceNodes.push(heading);
      for (const item of group) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'download-option';
        button.setAttribute('aria-pressed', String(item.tag === selectedTag));
        const name = document.createElement('strong');
        name.textContent = item.tag;
        const meta = document.createElement('span');
        const kinds = new Set(item.assets.map(asset => assetKind(asset.name)));
        const platforms = [kinds.has('android') ? 'Android' : null, kinds.has('windows') || kinds.has('portable') ? 'Windows' : null, kinds.has('linux') || kinds.has('flatpak') ? 'Linux' : null].filter(Boolean).join(' / ');
        const count = releaseCounts(item);
        meta.textContent = `${item.tag === releases[0].tag ? `${t('downloads.latest')} · ` : ''}${platforms}${count.available ? ` · ${formatter().format(count.total)} ${t(count.total === 1 ? 'downloads.countSingle' : 'downloads.countPlural')}` : ''}`;
        button.append(name, meta);
        button.addEventListener('click', () => {
          selectedTag = item.tag;
          preferredTag = selectedTag;
          try { localStorage.setItem(choiceKey, selectedTag); } catch { /* Keep the current selection. */ }
          details.open = false;
          render();
          summary.focus();
        });
        choiceNodes.push(button);
      }
    }
    options.replaceChildren(...choiceNodes);
    const assets = Object.fromEntries(release.assets.map(asset => [assetKind(asset.name), asset]));
    document.querySelectorAll('[data-download-version]').forEach(node => { node.textContent = release.tag; });
    document.querySelectorAll('[data-download-selected]').forEach(node => {
      node.textContent = t('downloads.selected').replace('{version}', release.tag);
    });
    document.querySelectorAll('[data-download-older-note]').forEach(node => {
      node.textContent = t('downloads.olderNote');
      node.hidden = release.tag === 'v0.2.2';
    });
    document.querySelectorAll('[data-download-release-link]').forEach(link => {
      link.href = release.url;
      link.textContent = t('downloads.release');
    });
    document.querySelectorAll('[data-download-notes-link]').forEach(link => {
      link.href = release.tag === 'v0.2.2' ? 'novidades.html' : release.url;
    });
    document.querySelectorAll('[data-download-asset]').forEach(link => {
      const asset = assets[link.dataset.downloadAsset];
      link.hidden = !asset;
      if (asset) link.href = asset.url;
      if (link.dataset.downloadAsset === 'android') {
        const label = link.querySelector('[data-i18n="downloads.apk"]');
        const fileVersion = asset?.name.match(/(?:Android|ComicReader)[-_]v?(\d+(?:\.\d+){1,3})/i)?.[1];
        if (label) label.textContent = fileVersion ? t('downloads.apkVersion').replace('{version}', fileVersion) : t('downloads.apkGeneric');
      }
    });
    for (const [platform, kinds] of Object.entries({android: ['android'], windows: ['windows', 'portable'], linux: ['linux', 'flatpak']})) {
      document.querySelectorAll(`[data-download-platform="${platform}"]`).forEach(node => { node.hidden = !kinds.some(kind => assets[kind]); });
    }
    document.querySelectorAll('.guide-index a[href^="#get-"]').forEach(link => {
      const platform = link.hash.slice(5);
      link.hidden = !document.querySelector(`[data-download-platform="${platform}"]:not([hidden])`);
    });
    const counts = releaseCounts(release);
    const total = document.querySelector('#download-total');
    if (total) {
      total.hidden = !counts.available;
      if (counts.available) {
        total.querySelector('[data-download-total]').textContent = formatter().format(counts.total);
        total.querySelector('[data-download-total-label]').textContent = t(counts.total === 1 ? 'downloads.totalSingle' : 'downloads.totalPlural');
        total.querySelector('[data-download-all-total]').textContent = formatter().format(catalog.allTotal ?? counts.total);
        total.querySelector('[data-download-all-count]').textContent = t((catalog.allTotal ?? counts.total) === 1 ? 'downloads.countSingle' : 'downloads.countPlural');
      }
    }
    document.querySelectorAll('[data-download-count]').forEach(node => {
      const count = counts.platforms[node.dataset.downloadCount];
      node.hidden = !counts.available || !document.querySelector(`[data-download-platform="${node.dataset.downloadCount}"]:not([hidden])`);
      if (counts.available) {
        node.querySelector('strong').textContent = formatter().format(count);
        node.querySelector('span').textContent = t(count === 1 ? 'downloads.countSingle' : 'downloads.countPlural');
      }
    });
  }
  document.documentElement.classList.add('versions-ready');
  document.addEventListener('click', event => {
    if (details.open && !details.contains(event.target)) details.open = false;
  });
  details.addEventListener('keydown', event => {
    if (event.key === 'Escape') { details.open = false; summary.focus(); }
  });
  document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => queueMicrotask(render)));
  window.addEventListener('storage', event => {
    if (event.key === 'komicove.site.language') queueMicrotask(render);
    if (event.key === choiceKey) { selectedTag = preferredTag = event.newValue; render(); }
  });
  render();
  (async () => {
    let cached;
    try { cached = JSON.parse(localStorage.getItem(cacheKey)); } catch { /* Use the bundled releases. */ }
    if (cached?.catalog?.releases?.length) {
      catalog = cached.catalog;
      if (preferredTag) selectedTag = preferredTag;
      render();
      if (Date.now() - cached.savedAt < 15 * 60 * 1000) return;
    }
    try {
      const response = await fetch(endpoint, {headers: {Accept: 'application/vnd.github+json'}});
      if (!response.ok) throw new Error('GitHub releases unavailable');
      catalog = normalizeReleases(await response.json());
      if (preferredTag) selectedTag = preferredTag;
      try { localStorage.setItem(cacheKey, JSON.stringify({savedAt: Date.now(), catalog})); } catch { /* Live data stays visible. */ }
      render();
    } catch { /* Bundled links or the last cached catalog remain available. */ }
  })();
})();
