// Secondary pages follow the same editorial assembly rhythm as the homepage.
// Elements remain readable without JavaScript or when reduced motion is preferred.
(() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced.matches || !('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const animations = new Set();
  const play = (element, frames, options) => {
    const animation = element.animate(frames, {...options, fill: 'both'});
    animations.add(animation);
    animation.addEventListener('finish', () => {
      animation.cancel();
      animations.delete(animation);
    }, {once: true});
  };

  const intro = document.querySelector('.guide-hero-grid, .news-hero');
  if (intro && !location.hash) {
    [...intro.children].forEach((part, index) => play(part, [
      {opacity: .05, clipPath: 'inset(0 0 28% 0)', transform: `translate3d(${index ? 35 : 0}px, 42px, 0)`},
      {opacity: 1, clipPath: 'inset(0 0 0 0)', transform: 'none'}
    ], {duration: 700, delay: index * 90, easing: 'cubic-bezier(.16, 1, .3, 1)'}));
  }

  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const element = entry.target;
    const index = [...element.parentElement.children].indexOf(element);
    const visual = element.matches('.guide-shot, .news-visual, .pix-panel');
    play(element, visual ? [
      {opacity: .08, clipPath: 'inset(0 22% 0 0)', transform: 'translateX(40px)'},
      {opacity: 1, clipPath: 'inset(0 0 0 0)', transform: 'none'}
    ] : [
      {opacity: .05, clipPath: 'inset(0 0 30% 0)', transform: 'translateY(42px)'},
      {opacity: 1, clipPath: 'inset(0 0 0 0)', transform: 'none'}
    ], {
      duration: visual ? 720 : 610,
      delay: Math.min(index % 4, 3) * 45,
      easing: 'cubic-bezier(.16, 1, .3, 1)'
    });
    element.classList.remove('assembly-pending');
    observer.unobserve(element);
  }), {rootMargin: '0px 0px 60px 0px', threshold: .01});

  document.querySelectorAll('.guide-chapter, .tutorial-row, .support-use-list article, .pix-panel, .news-visual, .news-section, .guide-shot, .download-card').forEach(element => {
    if (intro?.contains(element) || element.closest('.guide-chapter')) return;
    const bounds = element.getBoundingClientRect();
    if (bounds.top < innerHeight && bounds.bottom > 0) return;
    element.classList.add('assembly-pending');
    observer.observe(element);
  });
  reduced.addEventListener('change', () => {
    if (reduced.matches) {
      observer.disconnect();
      document.querySelectorAll('.assembly-pending').forEach(element => element.classList.remove('assembly-pending'));
      animations.forEach(animation => animation.cancel());
      animations.clear();
    }
  });
})();
