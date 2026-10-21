// Move the opening K into the header logo on every page load.
(() => {
  const intro = document.querySelector('.site-intro');
  const icon = intro?.querySelector('.site-intro-icon');
  const target = document.querySelector('.header .brand-official');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');

  function finish() {
    intro?.remove();
    document.documentElement.classList.remove('intro-playing');
  }

  if (!intro || !icon || !target || reduced.matches || !Element.prototype.animate) {
    finish();
    return;
  }

  requestAnimationFrame(() => requestAnimationFrame(() => {
    const from = icon.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    const targetX = to.left + to.width * .506;
    const targetY = to.top + to.height * .388;
    const dx = targetX - (from.left + from.width / 2);
    const dy = targetY - (from.top + from.height / 2);
    const scale = Math.min(to.width * .32 / from.width, to.height * .49 / from.height);

    intro.classList.add('is-moving');
    const movement = icon.animate([
      {opacity: 0, transform: 'translate3d(0,0,0) scale(.68)', offset: 0},
      {opacity: 1, transform: 'translate3d(0,0,0) scale(1)', offset: .18},
      {opacity: 1, transform: 'translate3d(0,0,0) scale(1)', offset: .61},
      {opacity: 1, transform: `translate3d(${dx}px,${dy}px,0) scale(${scale})`, offset: 1}
    ], {
      duration: 1740,
      easing: 'cubic-bezier(.76,0,.24,1)',
      fill: 'forwards'
    });
    movement.finished.then(() => setTimeout(finish, 190), finish);
    setTimeout(finish, 2300);
  }));
})();
