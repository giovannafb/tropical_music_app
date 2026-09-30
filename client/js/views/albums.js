// 12 · User · Album : albums likés
import { api } from '../api.js';
import { albumHeader, albumRow } from '../components/rows.js';
import { emptyState, loadList } from '../components/states.js';
import { h } from '../dom.js';
import { onContentChanged } from '../router.js';

export function albumsView() {
  const list = h('ul', { class: 'list list--gradient', 'aria-label': 'Liked albums' });
  const load = () => loadList(list, () => api('/me/likes/albums'), (album) => {
    const row = albumRow(album, {
      like: true,
      onLikeChange: (liked) => {
        if (liked) return;
        row.remove();
        if (!list.children.length) emptyState(list, 'No album found', { blankRows: false });
      },
    });
    return row;
  }, 'No album found', { blankRows: false });
  load();
  return { el: h('section', { 'aria-label': 'Albums' }, albumHeader(), list), destroy: onContentChanged(load) };
}
