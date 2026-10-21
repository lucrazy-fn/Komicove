// Reveal a compact navigation dock after the opening screen leaves view.
(() => {
  const root = document.querySelector('.journey-float');
  const hero = document.querySelector('.cinematic-hero');
  if (!root || !hero) return;

  const links = [...root.querySelectorAll('a[href^="#"]')];
  const sections = links
    .map(link => ({link, section: document.querySelector(link.getAttribute('href'))}))
    .filter(item => item.section);
  let framePending = false;

  function update() {
    const visible = hero.getBoundingClientRect().bottom <= 120;
    root.classList.toggle('is-visible', visible);
    root.inert = !visible;

    if (!visible) return;
    const marker = Math.min(innerHeight * .42, 360);
    let current = sections[0];
    for (const item of sections) {
      if (item.section.getBoundingClientRect().top <= marker) current = item;
    }
    for (const item of sections) {
      const active = item === current;
      item.link.classList.toggle('is-active', active);
      if (active) item.link.setAttribute('aria-current', 'location');
      else item.link.removeAttribute('aria-current');
    }
  }

  function schedule() {
    if (framePending) return;
    framePending = true;
    requestAnimationFrame(() => {
      framePending = false;
      update();
    });
  }

  addEventListener('scroll', schedule, {passive: true});
  addEventListener('resize', schedule);
  addEventListener('pageshow', schedule);
  update();
  requestAnimationFrame(update);
})();
