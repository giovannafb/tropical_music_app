// 10 · User · Accueil : titres « à la une » (playlist gérée par l'admin)
import { trackHeader, trackRow } from '../components/rows.js';
import { loadList } from '../components/states.js';
import { h } from '../dom.js';
import * as player from '../player.js';
import { api } from '../api.js';
import { onContentChanged } from '../router.js';

export function homeView() {
  const list = h('ul', { class: 'list', 'aria-label': 'Featured tracks' });
  const load = () => loadList(list, () => api('/home'),
    (t, i, all) => trackRow(t, { onPlay: () => player.playList(all, i), like: true }),
    'No track found');
  load();
  return { el: h('section', { 'aria-label': 'Home' }, trackHeader(), list), destroy: onContentChanged(load) };
}
