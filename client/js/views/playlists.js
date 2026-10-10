// 12 · User · Playlist : liste des playlists (nombre de titres, durée totale) + « New playlist »
import { api } from '../api.js';
import { playlistRow } from '../components/rows.js';
import { loadList } from '../components/states.js';
import { h, icon } from '../dom.js';
import { onContentChanged } from '../router.js';

export function playlistsView() {
  const list = h('ul', { class: 'list list--gradient', 'aria-label': 'Playlists' });
  const load = () => loadList(list, () => api('/me/playlists'), (p) => playlistRow(p), 'No playlist found', { blankRows: false });
  load();
  return {
    el: h('section', { 'aria-label': 'Playlists' },
      h('div', { class: 'playlists__bar' },
        h('a', { class: 'new-link', href: '#/playlists/new' }, icon('plus'), h('span', {}, 'New playlist')),
      ),
      list,
    ),
    destroy: onContentChanged(load),
  };
}
