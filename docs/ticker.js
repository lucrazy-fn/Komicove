// Move one exact copy at a constant speed so the ticker loops without a visible reset.
(() => {
  const track = document.querySelector('.product-ticker-track');
  const group = track?.querySelector('.product-ticker-group');
  if (!track || !group || !Element.prototype.animate) return;

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let animation;
  let queued = false;

  function start() {
    animation?.cancel();
    animation = null;
    track.style.transform = '';
    track.classList.remove('is-animated');
    if (reduced.matches) return;

    const distance = Math.round(group.getBoundingClientRect().width);
    if (!distance) return;
    const pixelsPerSecond = innerWidth < 700 ? 42 : 52;
    track.classList.add('is-animated');
    animation = track.animate(
      [
        {transform: 'translate3d(0,0,0)'},
        {transform: `translate3d(-${distance}px,0,0)`}
      ],
      {
        duration: distance / pixelsPerSecond * 1000,
        iterations: Infinity,
        easing: 'linear'
      }
    );
  }

  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      start();
    });
  }

  new ResizeObserver(schedule).observe(group);
  reduced.addEventListener('change', start);
  document.fonts?.ready.then(start);
  start();
})();
