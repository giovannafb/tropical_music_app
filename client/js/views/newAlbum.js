// 22 · Artiste · New album : cover, titre, upload de plusieurs pistes (une par requête, avec progression),
// renommage au crayon, bouton « Upload » = publication. Le brouillon en cours est repris automatiquement.
import { api, upload } from '../api.js';
import { getUser } from '../auth.js';
import { coverPicker, editRow, titleField, tracksBlock } from '../components/editor.js';
import { errorMessage, h, iconButton, toast } from '../dom.js';
import { navigate } from '../router.js';

const MAX_AUDIO_BYTES = 50 * 1024 * 1024;

export function newAlbumView() {
  let draft = null;   // album brouillon (API)
  const artistName = getUser().artist?.name || '';

  const title = titleField('Title');
  const cover = coverPicker({ label: 'Add album cover', onFile: (file) => saveDraft({ cover: file }) });
  const audioInput = h('input', { type: 'file', accept: '.mp3,audio/mpeg', multiple: true, class: 'visually-hidden', tabindex: '-1' });
  const block = tracksBlock(() => audioInput.click());
  const error = h('p', { class: 'form-error', role: 'alert' });
  const submit = h('button', { type: 'button', class: 'btn btn--primary editor__submit' }, 'Upload');

  function requireTitle() {
    const value = title.input.value.trim();
    if (!value) {
      error.textContent = 'Enter the album title first.';
      title.input.focus();
      return null;
    }
    return value;
  }

  /** Crée le brouillon au premier besoin, sinon met à jour titre / cover. */
  async function saveDraft({ cover: coverFile } = {}) {
    error.textContent = '';
    const value = requireTitle();
    if (!value) return null;
    const form = new FormData();
    if (!draft || value !== draft.title) form.append('title', value);
    if (coverFile) form.append('cover', coverFile);
    if (draft && ![...form.keys()].length) return draft;
    try {
      draft = draft
        ? await api(`/artist/albums/${draft.id}`, { method: 'PATCH', form })
        : await api('/artist/albums', { method: 'POST', form });
      cover.setUrl(draft.cover_url);
      if (coverFile) renderTracks();   // les lignes affichent la nouvelle cover
      return draft;
    } catch (err) {
      error.textContent = errorMessage(err);
      return null;
    }
  }

  function trackRowFor(track) {
    const { row, titleCell } = editRow({
      coverUrl: draft?.cover_small_url, title: track.title, artist: artistName, duration: track.duration_s,
    });
    const pen = iconButton('pen', `Rename ${track.title}`, () => {
      const input = h('input', { value: track.title, maxlength: 200, 'aria-label': 'Track title' });
      let done = false;
      const finish = async (saveIt) => {
        if (done) return;
        done = true;
        const value = input.value.trim();
        if (saveIt && value && value !== track.title) {
          try {
            const updated = await api(`/artist/tracks/${track.id}`, { method: 'PATCH', json: { title: value } });
            track.title = updated.title;
          } catch (err) {
            toast(errorMessage(err), 'error');
          }
        }
        titleCell.replaceChildren(h('span', { class: 'cell' }, track.title), pen);
      };
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') finish(true);
        if (e.key === 'Escape') { e.preventDefault(); finish(false); }
      });
      input.addEventListener('blur', () => finish(true), { once: true });
      titleCell.replaceChildren(input);
      input.focus();
    }, { class: 'icon-btn edit-row__pen' });
    titleCell.append(pen);
    return row;
  }

  function renderTracks() {
    block.list.replaceChildren(...(draft?.tracks || []).map(trackRowFor));
  }

  audioInput.addEventListener('change', async () => {
    const files = [...audioInput.files];
    audioInput.value = '';
    if (!files.length || !(await saveDraft())) return;
    for (const file of files) {
      // Une piste par requête, avec barre de progression
      const progress = h('progress', { class: 'edit-row__progress', max: '1', value: '0' });
      const { row } = editRow({ coverUrl: draft.cover_small_url, title: file.name, artist: artistName, duration: null });
      row.append(progress);
      block.list.append(row);
      if (file.size > MAX_AUDIO_BYTES) {
        row.remove();
        toast(`${file.name}: file too large (max 50 MB)`, 'error');
        continue;
      }
      const form = new FormData();
      form.append('file', file);
      try {
        const track = await upload(`/artist/albums/${draft.id}/tracks`, form, { onProgress: (p) => { progress.value = p; } });
        draft.tracks.push(track);
        row.replaceWith(trackRowFor(track));
      } catch (err) {
        row.remove();
        toast(`${file.name}: ${errorMessage(err)}`, 'error');
      }
    }
  });

  title.input.addEventListener('change', () => { if (draft) saveDraft(); });

  submit.addEventListener('click', async () => {
    error.textContent = '';
    if (!(await saveDraft())) return;
    submit.disabled = true;
    try {
      await api(`/artist/albums/${draft.id}/publish`, { method: 'POST' });
      toast('Album published');
      navigate('/artist/albums');
    } catch (err) {
      error.textContent = errorMessage(err);
      submit.disabled = false;
    }
  });

  // Reprise du brouillon en cours
  api('/artist/me/draft').then((d) => {
    if (!d) return;
    draft = d;
    title.input.value = d.title;
    cover.setUrl(d.cover_url);
    renderTracks();
  }).catch((err) => { error.textContent = errorMessage(err); });

  return h('section', { class: 'editor editor--album', 'aria-label': 'New album' },
    cover.el,
    h('div', { class: 'editor__form' }, title.el, error, block.el, audioInput),
    submit,
  );
}
