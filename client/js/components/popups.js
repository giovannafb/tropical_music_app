// Pop-ups à URL propre : #/track/33 (œil), #/album/12, #/artist/4, #/playlist/7.
import { api } from '../api.js';
import { getUser } from '../auth.js';
import { coverImg, errorMessage, h, icon, iconButton, toast } from '../dom.js';
import { releaseDate, totalLength, trackCount, trackLength } from '../format.js';
import * as player from '../player.js';
import { navigate, openPopup } from '../router.js';
import { confirmDialog, openModal } from './dialog.js';
import { albumRow, likeButton } from './rows.js';

/** Prévient les vues qu'un contenu a changé (suppression…) pour qu'elles se rechargent. */
export function notifyChanged() {
  window.dispatchEvent(new CustomEvent('musicapp:changed'));
}

function isArtist() {
  return getUser()?.role === 'artist';
}

function link(text, path) {
  return h('button', { type: 'button', class: 'link', onclick: () => openPopup(path) }, text);
}

async function withModal(label, onClose, load) {
  const modal = openModal({ label, onClose });
  modal.body.append(h('p', { class: 'modal__text' }, 'Loading…'));
  try {
    await load(modal);
  } catch (err) {
    modal.body.replaceChildren(h('p', { class: 'modal__text' }, err.status === 404 ? 'Not found.' : errorMessage(err)));
  }
  return modal;
}

function deleteButton(label, question, path, modal) {
  return h('button', {
    type: 'button', class: 'btn btn--small',
    onclick: async () => {
      if (!(await confirmDialog(question))) return;
      try {
        await api(path, { method: 'DELETE' });
        toast(`${label} deleted`);
        modal.close();
        notifyChanged();
      } catch (err) {
        toast(errorMessage(err), 'error');
      }
    },
  }, 'Delete');
}

/** Ligne compacte d'un titre dans un pop-up (lecture, titre, durée, œil). */
function compactTrack(track, onPlay) {
  return h('li', { class: 'track-row compact-grid' },
    onPlay ? iconButton('run', `Play ${track.title}`, onPlay, { class: 'icon-btn track-row__play' }) : h('span'),
    h('span', { class: 'cell' }, track.title),
    h('span', { class: 'track-row__length' }, trackLength(track.duration_s)),
    iconButton('eye', `Details of ${track.title}`, () => openPopup(`/track/${track.id}`), { class: 'icon-btn track-row__eye' }),
  );
}

function trackList(tracks, { playable }) {
  if (!tracks.length) return h('ul', { class: 'list' }, h('li', { class: 'state-row state-row--small' }, 'No track found'));
  return h('ul', { class: 'list' }, tracks.map((t, i) => compactTrack(t, playable ? () => player.playList(tracks, i) : null)));
}

// ---------- Titre (icône œil) ----------
export function trackPopup({ params, onClose }) {
  const artistSpace = isArtist();
  return withModal('Track details', onClose, async (modal) => {
    const track = await api(artistSpace ? `/artist/tracks/${params.id}` : `/tracks/${params.id}`);
    const details = h('dl', { class: 'details' },
      h('dt', {}, 'Title'), h('dd', {}, track.title),
      h('dt', {}, 'Artist'), h('dd', {}, artistSpace ? track.artist.name : link(track.artist.name, `/artist/${track.artist.id}`)),
      h('dt', {}, 'Album'), h('dd', {}, link(track.album.title, `/album/${track.album.id}`)),
      h('dt', {}, 'Length'), h('dd', {}, trackLength(track.duration_s)),
      h('dt', {}, 'Release date'), h('dd', {}, releaseDate(track.release_date)),
      h('dt', {}, 'Plays'), h('dd', {}, String(track.play_count)),
      h('dt', {}, 'Likes'), h('dd', {}, String(track.like_count)),
    );
    const actions = h('div', { class: 'modal__actions' });
    if (artistSpace) {
      actions.append(deleteButton('Track', `Delete the track “${track.title}”?`, `/artist/tracks/${track.id}`, modal));
    } else {
      actions.append(
        likeButton('tracks', track, () => notifyChanged()),
        h('button', { type: 'button', class: 'btn btn--small', onclick: () => showAddToPlaylist(modal, track, render) }, 'Add to playlist'),
      );
    }
    function render() {
      modal.body.replaceChildren(
        h('div', { class: 'modal__head' },
          coverImg(track.album.cover_url, 'modal__cover', track.album.title),
          h('div', {}, h('h2', { class: 'modal__title' }, track.title), details),
        ),
        actions,
      );
    }
    render();
  });
}

/** Choix d'une playlist dans le même pop-up (ajout d'un titre). */
async function showAddToPlaylist(modal, track, back) {
  const list = h('ul', { class: 'list list--gradient' }, h('li', { class: 'state-row state-row--small' }, 'Loading…'));
  modal.body.replaceChildren(
    h('h2', { class: 'modal__title' }, `Add “${track.title}” to a playlist`),
    list,
    h('div', { class: 'modal__actions' },
      h('button', { type: 'button', class: 'btn btn--small btn--ghost', onclick: back }, 'Back'),
      h('button', { type: 'button', class: 'btn btn--small', onclick: () => navigate('/playlists/new') }, 'New playlist'),
    ),
  );
  try {
    const playlists = await api('/me/playlists');
    if (!playlists.length) {
      list.replaceChildren(h('li', { class: 'state-row state-row--small' }, 'No playlist found'));
      return;
    }
    list.replaceChildren(...playlists.map((p) => h('li', {
      class: 'playlist-row', tabindex: '0', role: 'button',
      onclick: async () => {
        try {
          await api(`/playlists/${p.id}/tracks`, { method: 'POST', json: { track_id: track.id } });
          toast(`Added to ${p.name}`);
          notifyChanged();
          back();
        } catch (err) {
          toast(errorMessage(err), 'error');
        }
      },
    },
      coverImg(p.cover_small_url, 'playlist-row__cover'),
      h('span', { class: 'cell playlist-row__name' }, p.name),
      h('span', { class: 'cell playlist-row__meta' }, trackCount(p.track_count)),
      icon('plus'),
    )));
  } catch (err) {
    list.replaceChildren(h('li', { class: 'state-row state-row--small' }, errorMessage(err)));
  }
}

// ---------- Album ----------
export function albumPopup({ params, onClose }) {
  const artistSpace = isArtist();
  return withModal('Album', onClose, async (modal) => {
    const album = await api(artistSpace ? `/artist/albums/${params.id}` : `/albums/${params.id}`);
    const actions = h('div', { class: 'modal__actions' });
    if (artistSpace) {
      actions.append(deleteButton('Album', `Delete the album “${album.title}” and all its tracks?`, `/artist/albums/${album.id}`, modal));
    } else {
      actions.append(likeButton('albums', album, () => notifyChanged()));
    }
    modal.body.replaceChildren(
      h('div', { class: 'modal__head' },
        coverImg(album.cover_url, 'modal__cover', album.title),
        h('div', {},
          h('h2', { class: 'modal__title' }, album.title),
          h('p', { class: 'modal__subtitle' }, artistSpace ? album.artist.name : link(album.artist.name, `/artist/${album.artist.id}`)),
          h('p', { class: 'modal__meta' }, `Released ${releaseDate(album.release_date)}`),
          h('p', { class: 'modal__meta' }, `${trackCount(album.track_count)} · ${totalLength(album.duration_s)} · ${album.like_count} like${album.like_count === 1 ? '' : 's'}`),
          actions,
        ),
      ),
      trackList(album.tracks, { playable: !artistSpace }),
    );
  });
}

// ---------- Artiste (nom + bio + albums) ----------
export function artistPopup({ params, onClose }) {
  return withModal('Artist', onClose, async (modal) => {
    const artist = await api(`/artists/${params.id}`);
    modal.body.replaceChildren(
      h('div', { class: 'modal__head' },
        h('span', { class: 'avatar avatar--large' }, icon('avatar')),
        h('div', {}, h('h2', { class: 'modal__title' }, artist.name)),
      ),
      h('p', { class: 'modal__bio' }, artist.bio),
      artist.albums.length
        ? h('ul', { class: 'list list--gradient' }, artist.albums.map((a) => albumRow(a, { like: true })))
        : h('p', { class: 'modal__text' }, 'No album yet.'),
    );
  });
}

// ---------- Playlist ----------
export function playlistPopup({ params, onClose }) {
  return withModal('Playlist', onClose, async (modal) => {
    const playlist = await api(`/playlists/${params.id}`);
    modal.body.replaceChildren(
      h('div', { class: 'modal__head' },
        coverImg(playlist.cover_url, 'modal__cover', playlist.name),
        h('div', {},
          h('h2', { class: 'modal__title' }, playlist.name),
          h('p', { class: 'modal__meta' }, `${trackCount(playlist.track_count)} · ${totalLength(playlist.duration_s)}`),
          h('div', { class: 'modal__actions' },
            h('button', { type: 'button', class: 'btn btn--small', onclick: () => navigate(`/playlists/${playlist.id}/edit`) }, 'Edit'),
            deleteButton('Playlist', `Delete the playlist “${playlist.name}”?`, `/playlists/${playlist.id}`, modal),
          ),
        ),
      ),
      trackList(playlist.tracks, { playable: true }),
    );
  });
}
