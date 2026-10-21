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
    const dx = to.left + to.width / 2 - (from.left + from.width / 2);
    const dy = to.top + to.height / 2 - (from.top + from.height / 2);
    const scale = Math.min(to.width / from.width, to.height / from.height);

    intro.classList.add('is-moving');
    const movement = icon.animate([
      {opacity: 0, transform: 'translate3d(0,18px,0) scale(.72)', offset: 0},
      {opacity: 1, transform: 'translate3d(0,0,0) scale(1)', offset: .2},
      {opacity: 1, transform: 'translate3d(0,0,0) scale(1)', offset: .48},
      {opacity: 1, transform: `translate3d(${dx}px,${dy}px,0) scale(${scale})`, offset: 1}
    ], {
      duration: 1220,
      easing: 'cubic-bezier(.76,0,.24,1)',
      fill: 'forwards'
    });
    movement.finished.then(() => setTimeout(finish, 130), finish);
    setTimeout(finish, 1700);
  }));
})();
