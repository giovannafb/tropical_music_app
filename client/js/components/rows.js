// Lignes de liste reprises des composants Figma : titre (7:9441), album (19:12392),
// playlist (30:767), artiste (24:12663), et en-têtes de tableau.
import { api } from '../api.js';
import { coverImg, h, icon, iconButton, toast, errorMessage } from '../dom.js';
import { totalLength, trackCount, trackLength } from '../format.js';
import { openPopup } from '../router.js';

export function trackHeader({ album = true } = {}) {
  return h('div', { class: 'table-header track-grid', role: 'row' },
    h('span'), h('span'),
    h('span', { class: 'cell', role: 'columnheader' }, 'Title'),
    h('span', { class: 'cell', role: 'columnheader' }, 'Artist'),
    h('span', { class: 'cell', role: 'columnheader' }, album ? 'Album' : ''),
    h('span', { class: 'cell track-row__length', role: 'columnheader' }, 'Length'),
  );
}

export function albumHeader() {
  return h('div', { class: 'table-header album-grid', role: 'row' },
    h('span'),
    h('span', { class: 'cell', role: 'columnheader' }, 'Title'),
    h('span', { class: 'cell', role: 'columnheader' }, 'Artist'),
    h('span', { class: 'cell album-row__length', role: 'columnheader' }, 'Length'),
  );
}

/** Bouton cœur : like / unlike d'un titre ou d'un album. */
export function likeButton(kind, item, onChange) {
  const btn = iconButton(item.liked ? 'liked' : 'like', item.liked ? 'Unlike' : 'Like', async (e) => {
    e.stopPropagation();
    const liked = !item.liked;
    btn.disabled = true;
    try {
      await api(`/${kind}/${item.id}/like`, { method: liked ? 'PUT' : 'DELETE' });
      item.liked = liked;
      btn.replaceChildren(icon(liked ? 'liked' : 'like'));
      btn.setAttribute('aria-label', liked ? 'Unlike' : 'Like');
      btn.title = liked ? 'Unlike' : 'Like';
      btn.setAttribute('aria-pressed', String(liked));
      if (onChange) onChange(liked);
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      btn.disabled = false;
    }
  }, { 'aria-pressed': String(Boolean(item.liked)) });
  return btn;
}

/**
 * Ligne de titre.
 * options : onPlay (bouton lecture), like (cœur), eye (pop-up détail), links (artiste/album cliquables)
 */
export function trackRow(track, { onPlay, like = false, onLikeChange, eye = true, links = true } = {}) {
  const artist = links
    ? h('button', { type: 'button', class: 'row-link', onclick: () => openPopup(`/artist/${track.artist.id}`) }, track.artist.name)
    : h('span', { class: 'cell' }, track.artist.name);
  const album = links
    ? h('button', { type: 'button', class: 'row-link', onclick: () => openPopup(`/album/${track.album.id}`) }, track.album.title)
    : h('span', { class: 'cell' }, track.album.title);
  return h('li', { class: 'track-row track-grid', dataset: { trackId: track.id } },
    coverImg(track.album.cover_small_url, 'track-row__cover'),
    onPlay ? iconButton('run', `Play ${track.title}`, onPlay, { class: 'icon-btn track-row__play' }) : h('span'),
    h('span', { class: 'cell' }, track.title),
    artist,
    album,
    h('span', { class: 'cell track-row__length' }, trackLength(track.duration_s)),
    like ? h('span', { class: 'track-row__like' }, likeButton('tracks', track, onLikeChange)) : h('span'),
    eye ? iconButton('eye', `Details of ${track.title}`, () => openPopup(`/track/${track.id}`), { class: 'icon-btn track-row__eye' }) : h('span'),
  );
}

export function albumRow(album, { like = false, onLikeChange } = {}) {
  const open = () => openPopup(`/album/${album.id}`);
  const row = h('li', {
    class: 'album-row album-grid', tabindex: '0', role: 'button', 'aria-label': `Album ${album.title}`,
    onclick: open, onkeydown: (e) => { if (e.key === 'Enter') open(); },
  },
    coverImg(album.cover_small_url, 'album-row__cover'),
    h('span', { class: 'cell' }, album.title),
    h('span', { class: 'cell' }, album.artist.name),
    h('span', { class: 'cell album-row__length' }, totalLength(album.duration_s)),
    like ? h('span', { class: 'album-row__like' }, likeButton('albums', album, onLikeChange)) : h('span'),
  );
  return row;
}

export function playlistRow(playlist) {
  const open = () => openPopup(`/playlist/${playlist.id}`);
  return h('li', {
    class: 'playlist-row', tabindex: '0', role: 'button', 'aria-label': `Playlist ${playlist.name}`,
    onclick: open, onkeydown: (e) => { if (e.key === 'Enter') open(); },
  },
    coverImg(playlist.cover_small_url, 'playlist-row__cover'),
    h('span', { class: 'cell playlist-row__name' }, playlist.name),
    h('span', { class: 'cell playlist-row__meta' }, trackCount(playlist.track_count)),
    h('span', { class: 'cell playlist-row__meta' }, totalLength(playlist.duration_s)),
  );
}

export function artistRow(artist) {
  const open = () => openPopup(`/artist/${artist.id}`);
  return h('li', {
    class: 'artist-row', tabindex: '0', role: 'button', 'aria-label': `Artist ${artist.name}`,
    onclick: open, onkeydown: (e) => { if (e.key === 'Enter') open(); },
  },
    h('span', { class: 'avatar' }, icon('avatar')),
    h('span', { class: 'cell' }, artist.name),
  );
}
