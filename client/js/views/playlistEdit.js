// 12 · User · create playlist (#/playlists/new) — réutilisé pour modifier une playlist (#/playlists/7/edit).
// Cover optionnelle ; « + » ouvre la recherche ; chaque ligne a un bouton « retirer ».
import { api } from '../api.js';
import { coverPicker, editRow, titleField, tracksBlock } from '../components/editor.js';
import { openTrackPicker } from '../components/trackPicker.js';
import { errorMessage, h, iconButton, toast } from '../dom.js';
import { navigate } from '../router.js';

export function playlistEditView({ params }) {
  const editing = Boolean(params.id);
  let original = null;           // playlist chargée (mode édition)
  let coverFile = null;
  let tracks = [];               // titres sélectionnés, dans l'ordre

  const name = titleField('Playlist name');
  const cover = coverPicker({
    label: 'Add playlist cover',
    onFile: (file) => { coverFile = file; cover.setUrl(URL.createObjectURL(file)); },
  });
  const block = tracksBlock(() => openTrackPicker({
    isAdded: (id) => tracks.some((t) => t.id === id),
    onAdd: async (track) => { tracks.push(track); renderTracks(); },
  }));
  const error = h('p', { class: 'form-error', role: 'alert' });
  const submit = h('button', { type: 'button', class: 'btn btn--primary editor__submit' }, editing ? 'Save' : 'Create');

  function renderTracks() {
    block.list.replaceChildren(...tracks.map((t) => editRow({
      coverUrl: t.album.cover_small_url,
      title: t.title,
      artist: t.artist.name,
      duration: t.duration_s,
      action: iconButton('minus', `Remove ${t.title}`, () => {
        tracks = tracks.filter((x) => x.id !== t.id);
        renderTracks();
      }),
    }).row));
  }

  async function save() {
    error.textContent = '';
    const value = name.input.value.trim();
    if (!value) { error.textContent = 'Enter a playlist name.'; name.input.focus(); return; }
    submit.disabled = true;
    try {
      if (!editing) {
        const form = new FormData();
        form.append('name', value);
        if (coverFile) form.append('cover', coverFile);
        tracks.forEach((t) => form.append('track_ids', String(t.id)));
        await api('/playlists', { method: 'POST', form });
        toast('Playlist created');
      } else {
        const form = new FormData();
        if (value !== original.name) form.append('name', value);
        if (coverFile) form.append('cover', coverFile);
        if ([...form.keys()].length) await api(`/playlists/${original.id}`, { method: 'PATCH', form });
        const before = new Set(original.tracks.map((t) => t.id));
        const after = new Set(tracks.map((t) => t.id));
        for (const id of before) if (!after.has(id)) await api(`/playlists/${original.id}/tracks/${id}`, { method: 'DELETE' });
        for (const id of after) if (!before.has(id)) await api(`/playlists/${original.id}/tracks`, { method: 'POST', json: { track_id: id } });
        toast('Playlist saved');
      }
      navigate('/playlists');
    } catch (err) {
      error.textContent = errorMessage(err);
      submit.disabled = false;
    }
  }
  submit.addEventListener('click', save);

  const el = h('section', { class: 'editor', 'aria-label': editing ? 'Edit playlist' : 'Create playlist' },
    cover.el,
    h('div', { class: 'editor__form' }, name.el, error, block.el),
    submit,
  );

  if (editing) {
    submit.disabled = true;
    api(`/playlists/${params.id}`).then((p) => {
      original = p;
      name.input.value = p.name;
      cover.setUrl(p.cover_url);
      tracks = p.tracks.slice();
      renderTracks();
      submit.disabled = false;
    }).catch((err) => { error.textContent = errorMessage(err); });
  }
  return el;
}
