// Adicione caminhos relativos para screenshots reais em image (ex.: assets/biblioteca.webp).
const screens = {
  biblioteca: {title: 'Biblioteca', description: 'Seu acervo, capas e progresso em uma única visão.', image: 'assets/biblioteca.png', alt: 'Biblioteca do PANEL com capas e progresso de leitura'},
  leitor: {title: 'Leitor', description: 'A história em primeiro plano. Zoom, miniaturas e marcadores ao alcance.', image: 'assets/leitor.png', alt: 'Tela de leitura do PANEL'},
  colecoes: {title: 'Coleções', description: 'Suas séries organizadas, do primeiro volume à próxima leitura.', image: 'assets/colecoes.png', alt: 'Tela de coleções do PANEL'}
};
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
document.documentElement.classList.add('js');
const menu = document.querySelector('#menu');
const toggle = document.querySelector('.menu-toggle');
function setMenu(open) {
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
  menu.classList.toggle('open', open);
  menu.inert = !open && matchMedia('(max-width:760px)').matches;
}
toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
document.addEventListener('keydown', e => {if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {setMenu(false); toggle.focus();}});
matchMedia('(max-width:760px)').addEventListener('change', () => setMenu(false));
setMenu(false);

if ('IntersectionObserver' in window && !reduced.matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const siblings = [...entry.target.parentElement.children];
    const delay = entry.target.classList.contains('feature') ? (siblings.indexOf(entry.target) % 3) * 65 : 0;
    entry.target.animate([{opacity: .25, transform: 'translateY(22px)'}, {opacity: 1, transform: 'none'}], {duration: 600, delay, easing: 'cubic-bezier(.2,.75,.25,1)'});
    observer.unobserve(entry.target);
  }), {threshold: .12});
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

const art = document.querySelector('.hero-art');
const tilt = document.querySelector('.tilt');
let raf;
art.addEventListener('pointermove', e => {
  if (reduced.matches || !matchMedia('(hover:hover) and (pointer:fine) and (min-width:761px)').matches) return;
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(() => {
    const rect = art.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - .5;
    const y = (e.clientY - rect.top) / rect.height - .5;
    tilt.style.transform = `rotate(-5deg) rotateY(${x * 8}deg) rotateX(${-y * 6}deg)`;
  });
});
art.addEventListener('pointerleave', () => {cancelAnimationFrame(raf); tilt.style.transform = '';});
reduced.addEventListener('change', () => {cancelAnimationFrame(raf); tilt.style.transform = '';});

const tabs = [...document.querySelectorAll('[data-tab]')];
const tablist = document.querySelector('.gallery-controls');
const body = document.querySelector('#gallery-body');
const lightbox = document.querySelector('#lightbox');
let selected = 'biblioteca';
tablist.setAttribute('role', 'tablist');
body.setAttribute('role', 'tabpanel');
body.tabIndex = 0;
function contentFor(key) {
  const screen = screens[key];
  if (screen.image) {
    const img = document.createElement('img');
    img.src = screen.image; img.alt = screen.alt; img.loading = 'lazy'; img.decoding = 'async';
    img.addEventListener('error', () => img.replaceWith(placeholderFor(key)), {once:true});
    return img;
  }
  return placeholderFor(key);
}
function placeholderFor(key) {
  const screen = screens[key];
  const div = document.createElement('div'); div.className = 'placeholder';
  for (const [tag, className, text] of [
    ['span', 'placeholder-tag', 'ESPAÇO PARA CAPTURA REAL'], ['strong', '', screen.title],
    ['p', '', screen.description], ['span', 'placeholder-foot', 'A imagem oficial desta tela será adicionada aqui. Esta composição não é uma captura do aplicativo.']
  ]) {const node = document.createElement(tag); node.className = className; node.textContent = text; div.append(node);}
  return div;
}
function selectTab(key) {
  selected = key;
  tabs.forEach(tab => {const active = tab.dataset.tab === key; tab.classList.toggle('selected', active); tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;});
  body.setAttribute('aria-labelledby', `tab-${key}`);
  body.replaceChildren(contentFor(key));
  document.querySelector('#gallery-title').textContent = `PANEL / ${screens[key].title}`;
  if (!reduced.matches) body.animate([{opacity:.1,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{duration:320,easing:'ease-out'});
}
tabs.forEach((tab, index) => {
  tab.id = `tab-${tab.dataset.tab}`; tab.setAttribute('role','tab'); tab.setAttribute('aria-controls','gallery-body');
  tab.addEventListener('click', () => selectTab(tab.dataset.tab));
  tab.addEventListener('keydown', e => {
    let next;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = tabs.length - 1;
    if (next !== undefined) {e.preventDefault(); tabs[next].focus(); selectTab(tabs[next].dataset.tab);}
  });
});
selectTab(selected);
document.querySelector('#expand').addEventListener('click', () => {
  document.querySelector('#modal-title').textContent = `PANEL / ${screens[selected].title}`;
  document.querySelector('#modal-content').replaceChildren(contentFor(selected));
  lightbox.showModal();
  if (!reduced.matches) lightbox.animate([{opacity:0,transform:'translateY(12px) scale(.98)'},{opacity:1,transform:'none'}],{duration:250,easing:'ease-out'});
});
document.querySelector('#close-modal').addEventListener('click', () => lightbox.close());
lightbox.addEventListener('click', e => {if(e.target === lightbox) {const r=lightbox.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom) lightbox.close();}});

document.querySelectorAll('.questions details').forEach(details => {
  let animation = null;
  let targetOpen = false;
  const summary = details.querySelector('summary');
  summary.addEventListener('click', e => {
    if (reduced.matches || !details.animate) return;
    e.preventDefault();
    const start = details.getBoundingClientRect().height;
    targetOpen = animation ? !targetOpen : !details.open;
    if (animation) animation.cancel();
    details.open = true;
    const end = targetOpen ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height + 1;
    details.style.overflow = 'hidden';
    animation = details.animate({height:[`${start}px`,`${end}px`]},{duration:260,easing:'cubic-bezier(.2,.75,.25,1)'});
    animation.onfinish = () => {details.open = targetOpen; details.style.overflow = ''; animation = null;};
  });
});
