// Espace admin (écran ajouté) : titres de la playlist « à la une » affichée sur l'accueil des users.
import { api } from '../api.js';
import { editRow, tracksBlock } from '../components/editor.js';
import { openTrackPicker } from '../components/trackPicker.js';
import { errorMessage, h, iconButton, toast } from '../dom.js';

export function adminFeaturedView() {
  let tracks = [];
  const info = h('p', { class: 'form-error', role: 'alert' });
  const block = tracksBlock(() => openTrackPicker({
    isAdded: (id) => tracks.some((t) => t.id === id),
    onAdd: async (track) => {
      await api('/admin/featured-playlist/tracks', { method: 'POST', json: { track_id: track.id } });
      tracks.push(track);
      render();
    },
  }));

  function render() {
    block.list.replaceChildren(...(tracks.length
      ? tracks.map((t) => editRow({
        coverUrl: t.album.cover_small_url,
        title: t.title,
        artist: t.artist.name,
        duration: t.duration_s,
        action: iconButton('minus', `Remove ${t.title}`, async () => {
          try {
            await api(`/admin/featured-playlist/tracks/${t.id}`, { method: 'DELETE' });
            tracks = tracks.filter((x) => x.id !== t.id);
            render();
          } catch (err) {
            toast(errorMessage(err), 'error');
          }
        }),
      }).row)
      : [h('li', { class: 'edit-row edit-row--empty' }, 'No track found')]));
  }

  block.list.replaceChildren(h('li', { class: 'edit-row edit-row--empty' }, 'Loading…'));
  api('/admin/featured-playlist')
    .then((p) => { tracks = p.tracks; render(); })
    .catch((err) => { info.textContent = errorMessage(err); block.list.replaceChildren(); });

  return h('section', { class: 'featured', 'aria-label': 'Featured playlist' },
    h('h1', { class: 'featured__title' }, 'Featured tracks'),
    info,
    block.el,
  );
}
