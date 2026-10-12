/* Keep the public homepage URL clean while preserving direct file previews. */
(() => {
  if (location.protocol === 'file:') {
    document.querySelectorAll('a[href="./"],a[href^="./#"]').forEach(link => {
      link.setAttribute('href', `index.html${link.getAttribute('href').slice(2)}`);
    });
    return;
  }

  if (/\/index\.html$/i.test(location.pathname)) {
    const homepagePath = location.pathname.slice(0, -'index.html'.length);
    history.replaceState(history.state, '', `${homepagePath}${location.search}${location.hash}`);
  }
})();
