// 21 · Artiste · Album (« my albums ») : albums publiés de l'artiste (sans cœur)
import { api } from '../api.js';
import { albumHeader, albumRow } from '../components/rows.js';
import { loadList } from '../components/states.js';
import { h } from '../dom.js';
import { onContentChanged } from '../router.js';

export function artistAlbumsView() {
  const list = h('ul', { class: 'list list--gradient', 'aria-label': 'My albums' });
  const load = () => loadList(list, () => api('/artist/me/albums'), (a) => albumRow(a), 'No album found', { blankRows: false });
  load();
  return { el: h('section', { 'aria-label': 'My albums' }, albumHeader(), list), destroy: onContentChanged(load) };
}
