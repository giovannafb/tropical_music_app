// Coques distinctes selon le rôle (sidebar User / Artist / Admin), comme dans le prototype.
import { ROLE_LABEL, getUser, onUserChange } from '../auth.js';
import { h, icon } from '../dom.js';
import { playerBar } from './playerBar.js';

const NAV = {
  user: {
    items: [
      { key: 'home', label: 'Home', icon: 'home', path: '/home' },
      { key: 'likes', label: 'Likes', icon: 'like', path: '/likes' },
      { key: 'albums', label: 'Albums', icon: 'album', path: '/albums' },
      { key: 'search', label: 'Search', icon: 'search', path: '/search' },
      { key: 'playlists', label: 'Playlist', icon: 'playlist', path: '/playlists' },
    ],
    bottom: { key: 'profile', label: 'Profile', icon: 'profile', path: '/profile' },
    player: true,
  },
  artist: {
    items: [
      { key: 'tracks', label: 'my tracks', icon: 'note', path: '/artist/tracks' },
      { key: 'albums', label: 'my albums', icon: 'album', path: '/artist/albums' },
      { key: 'new-album', label: 'New album', icon: 'plus', path: '/artist/new-album' },
    ],
    bottom: { key: 'profile', label: 'Profile', icon: 'profile', path: '/artist/profile' },
    player: false,   // strictement le Figma : pas de lecture côté artiste
  },
  admin: {
    items: [
      { key: 'artists', label: 'Artists', icon: 'artists', path: '/admin/artists' },
      { key: 'featured', label: 'Featured', icon: 'star', path: '/admin/featured' },
    ],
    bottom: { key: 'profile', label: 'Profile', icon: 'profile', path: '/admin/profile' },
    player: false,
  },
};

let shell = null;

onUserChange((user) => {
  if (shell && user && user.id === shell.userId) shell.title.textContent = headerLabel(user);
});

function navLink(item) {
  return h('a', { class: 'nav-item', href: `#${item.path}`, dataset: { nav: item.key } }, icon(item.icon), h('span', {}, item.label));
}

function headerLabel(user) {
  return `${user.username} - ${ROLE_LABEL[user.role]}`;
}

function build(user) {
  const conf = NAV[user.role];
  const title = h('span', { class: 'cell' }, headerLabel(user));
  const content = h('main', { class: 'main__content', id: 'main-content', tabindex: '-1' });
  const player = conf.player ? playerBar() : null;
  const el = h('div', { class: 'shell' },
    h('aside', { class: 'sidebar' },
      h('div', { class: 'sidebar__header' }, h('span', { class: 'avatar' }, icon('avatar')), title),
      h('nav', { class: 'sidebar__nav', 'aria-label': 'Main' }, conf.items.map(navLink)),
      h('nav', { class: 'sidebar__bottom', 'aria-label': 'Account' }, navLink(conf.bottom)),
    ),
    h('div', { class: 'main' }, content, player ? player.el : null),
  );
  return { el, role: user.role, userId: user.id, title, content, player };
}

/** Place une vue dans la zone principale de la coque du rôle connecté. */
export function mountInShell(viewEl, navKey) {
  const user = getUser();
  const app = document.getElementById('app');
  if (!shell || shell.role !== user.role || shell.userId !== user.id || !app.contains(shell.el)) {
    destroyShell();
    shell = build(user);
    app.replaceChildren(shell.el);
  }
  shell.title.textContent = headerLabel(user);
  shell.content.replaceChildren(viewEl);
  shell.content.scrollTop = 0;
  shell.el.querySelectorAll('.nav-item').forEach((a) => {
    const active = a.dataset.nav === navKey;
    a.classList.toggle('is-active', active);
    if (active) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

/** Pages sans coque (connexion, inscription, messages). */
export function mountFullPage(viewEl) {
  destroyShell();
  document.getElementById('app').replaceChildren(viewEl);
}

export function destroyShell() {
  if (shell?.player) shell.player.destroy();
  shell = null;
}
