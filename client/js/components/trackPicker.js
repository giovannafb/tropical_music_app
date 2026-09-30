// Pop-up de recherche pour ajouter des titres (bloc « Add new tracks » des playlists et de la playlist à la une).
// Debounce de 300 ms + annulation de la requête précédente (AbortController).
import { api } from '../api.js';
import { coverImg, errorMessage, h, iconButton } from '../dom.js';
import { trackLength } from '../format.js';
import { openModal } from './dialog.js';

export function openTrackPicker({ isAdded, onAdd }) {
  const modal = openModal({ label: 'Add tracks' });
  const input = h('input', { type: 'search', class: 'search-bar', placeholder: 'What’s on your mind ?', 'aria-label': 'Search tracks' });
  const results = h('ul', { class: 'list' });
  modal.body.append(h('h2', { class: 'modal__title' }, 'Add new tracks'), input, h('div', { class: 'picker-results' }, results));

  let timer = null;
  let controller = null;

  function row(track) {
    const added = isAdded(track.id);
    const btn = iconButton(added ? 'minus' : 'plus', added ? 'Already added' : `Add ${track.title}`, async () => {
      btn.disabled = true;
      try {
        await onAdd(track);
        btn.replaceChildren(h('span', { class: 'icon icon--minus', 'aria-hidden': 'true' }));
        btn.setAttribute('aria-label', 'Already added');
      } catch (err) {
        btn.disabled = false;
        results.prepend(h('li', { class: 'form-error' }, errorMessage(err)));
      }
    }, { class: 'icon-btn picker-row__add', disabled: added });
    return h('li', { class: 'picker-row' },
      coverImg(track.album.cover_small_url, 'edit-row__cover'),
      h('span', { class: 'cell' }, track.title),
      h('span', { class: 'cell' }, track.artist.name),
      h('span', { class: 'edit-row__length' }, trackLength(track.duration_s)),
      btn,
    );
  }

  async function search(q) {
    if (controller) controller.abort();
    if (!q.trim()) { results.replaceChildren(); return; }
    controller = new AbortController();
    results.replaceChildren(h('li', { class: 'form-info' }, 'Searching…'));
    try {
      const data = await api(`/search?q=${encodeURIComponent(q)}`, { signal: controller.signal });
      results.replaceChildren(...(data.tracks.length ? data.tracks.map(row) : [h('li', { class: 'form-info' }, 'No track found')]));
    } catch (err) {
      if (err.name === 'AbortError') return;
      results.replaceChildren(h('li', { class: 'form-error' }, errorMessage(err)));
    }
  }

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => search(input.value), 300);
  });
  input.focus();
  return modal;
}
