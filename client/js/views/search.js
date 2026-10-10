// 12 · User · Search 1 (invite) et Search 2 (résultats Songs / Album / Artists)
// Debounce de 300 ms, requête précédente annulée avec AbortController.
import { api } from '../api.js';
import { albumRow, artistRow, trackRow } from '../components/rows.js';
import { emptyState, errorState, loadingState } from '../components/states.js';
import { h } from '../dom.js';
import * as player from '../player.js';
import { updateViewUrl } from '../router.js';

export function searchView({ query }) {
  const input = h('input', {
    type: 'search', class: 'search-bar', id: 'search-input', autocomplete: 'off',
    'aria-label': 'Search songs, albums and artists', maxlength: 100,
  });
  const hint = h('label', { class: 'search__hint', for: 'search-input' }, 'What’s on your mind ?');
  const songs = h('ul', { class: 'list' });
  const albums = h('ul', { class: 'list list--gradient' });
  const artists = h('ul', { class: 'list list--gradient' });
  const results = h('div', { class: 'search__results' },
    h('h2', { class: 'section-title' }, 'Songs'), songs,
    h('h2', { class: 'section-title' }, 'Album'), albums,
    h('h2', { class: 'section-title' }, 'Artists'), artists,
  );
  const el = h('section', { class: 'search', 'aria-label': 'Search' }, hint, input, results);

  let timer = null;
  let controller = null;

  async function run(q) {
    updateViewUrl(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
    el.classList.toggle('search--active', Boolean(q));
    if (controller) controller.abort();
    if (!q) return;
    controller = new AbortController();
    [songs, albums, artists].forEach(loadingState);
    try {
      const data = await api(`/search?q=${encodeURIComponent(q)}`, { signal: controller.signal });
      if (data.tracks.length) songs.replaceChildren(...data.tracks.map((t, i) => trackRow(t, { onPlay: () => player.playList(data.tracks, i) })));
      else emptyState(songs, 'No track found', { blankRows: false });
      if (data.albums.length) albums.replaceChildren(...data.albums.map((a) => albumRow(a, { like: true })));
      else emptyState(albums, 'No album found', { blankRows: false });
      if (data.artists.length) artists.replaceChildren(...data.artists.map(artistRow));
      else emptyState(artists, 'No artist found', { blankRows: false });
    } catch (err) {
      if (err.name === 'AbortError') return;
      [songs, albums, artists].forEach((list) => errorState(list, () => run(q)));
    }
  }

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => run(input.value.trim()), 300);
  });

  const initial = (query.get('q') || '').trim();
  input.value = initial;
  run(initial);
  setTimeout(() => input.focus(), 0);
  return { el, destroy: () => { clearTimeout(timer); if (controller) controller.abort(); } };
}
