// 11 · User · Likes : titres likés (cœur plein sur chaque ligne)
import { api } from '../api.js';
import { trackHeader, trackRow } from '../components/rows.js';
import { emptyState, loadList } from '../components/states.js';
import { h } from '../dom.js';
import * as player from '../player.js';
import { onContentChanged } from '../router.js';

export function likesView() {
  const list = h('ul', { class: 'list', 'aria-label': 'Liked tracks' });
  const load = () => loadList(list, () => api('/me/likes/tracks'), (t, i, all) => {
    const row = trackRow(t, {
      onPlay: () => player.playList(all, i),
      like: true,
      onLikeChange: (liked) => {
        if (liked) return;
        row.remove();   // n'est plus liké : il sort de la liste
        if (!list.children.length) emptyState(list, 'No track found');
      },
    });
    return row;
  }, 'No track found');
  load();
  return { el: h('section', { 'aria-label': 'Likes' }, trackHeader(), list), destroy: onContentChanged(load) };
}
