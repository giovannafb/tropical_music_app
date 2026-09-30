// Création d'éléments sans innerHTML : les données de l'API passent toujours par
// textContent / createTextNode (protection XSS).

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'value') el.value = value;
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, String(value));
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of [children].flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function icon(name) {
  return h('span', { class: `icon icon--${name}`, 'aria-hidden': 'true' });
}

export function iconButton(name, label, onClick, attrs = {}) {
  return h('button', { type: 'button', class: 'icon-btn', 'aria-label': label, title: label, onclick: onClick, ...attrs }, icon(name));
}

export function coverImg(url, className, alt = '') {
  // Sans cover : le placeholder du Figma est affiché en fond (.cover)
  return url
    ? h('img', { class: `cover ${className}`, src: url, alt, loading: 'lazy' })
    : h('span', { class: `cover ${className}`, role: alt ? 'img' : null, 'aria-label': alt || null });
}

export function avatar() {
  return h('span', { class: 'avatar' }, icon('avatar'));
}

export function toast(message, type = 'info') {
  const box = document.getElementById('toasts');
  const el = h('div', { class: `toast${type === 'error' ? ' toast--error' : ''}` }, message);
  box.append(el);
  setTimeout(() => el.remove(), 3500);
}

export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  return err && err.message && err.code !== 'HTTP_ERROR' ? err.message : fallback;
}
