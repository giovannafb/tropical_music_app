// 20 · Artiste · Accueil (« my tracks ») : titres publiés de l'artiste (pas de lecture, pas de cœur)
import { api } from '../api.js';
import { trackHeader, trackRow } from '../components/rows.js';
import { loadList } from '../components/states.js';
import { h } from '../dom.js';
import { onContentChanged } from '../router.js';

export function artistTracksView() {
  const list = h('ul', { class: 'list', 'aria-label': 'My tracks' });
  const load = () => loadList(list, () => api('/artist/me/tracks'), (t) => trackRow(t, { links: false }), 'No track found');
  load();
  return { el: h('section', { 'aria-label': 'My tracks' }, trackHeader(), list), destroy: onContentChanged(load) };
}
