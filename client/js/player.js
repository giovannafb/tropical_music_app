// Lecteur audio : un seul <audio> global, file de lecture liée au contexte (accueil, album, playlist…),
// aléatoire, répétition, volume, Media Session API, écoute comptée après 30 s.
import { api, refreshSession } from './api.js';

const audio = document.getElementById('audio');
const PLAY_COUNT_AFTER_S = 30;

const state = {
  queue: [],
  order: [],        // ordre de lecture (indices de queue), mélangé si aléatoire
  pos: -1,          // position dans order
  shuffle: false,
  repeat: 'off',    // off | all | one
  listened: 0,
  lastTime: 0,
  counted: false,
  authRetried: false,
};

const listeners = new Set();
export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function emit(type) {
  listeners.forEach((fn) => fn(type));
}

export function current() {
  return state.pos >= 0 ? state.queue[state.order[state.pos]] : null;
}
export function getState() {
  return {
    queue: state.queue,
    currentIndex: state.pos >= 0 ? state.order[state.pos] : -1,
    shuffle: state.shuffle,
    repeat: state.repeat,
    paused: audio.paused,
    currentTime: audio.currentTime || 0,
    duration: Number.isFinite(audio.duration) ? audio.duration : (current()?.duration_s || 0),
    volume: audio.muted ? 0 : audio.volume,
  };
}

function shuffled(indices) {
  const a = indices.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function buildOrder(startIndex) {
  const all = state.queue.map((_, i) => i);
  if (state.shuffle) {
    state.order = [startIndex, ...shuffled(all.filter((i) => i !== startIndex))];
    state.pos = 0;
  } else {
    state.order = all;
    state.pos = startIndex;
  }
}

function load(autoplay = true) {
  const track = current();
  if (!track) return;
  state.listened = 0;
  state.lastTime = 0;
  state.counted = false;
  state.authRetried = false;
  audio.src = `/api/stream/${track.id}`;
  updateMediaSession(track);
  if (autoplay) audio.play().catch(() => {});
  emit('track');
}

/** Lance un titre en mettant toute la liste du contexte dans la file. */
export function playList(tracks, startIndex = 0) {
  if (!tracks.length) return;
  state.queue = tracks.slice();
  buildOrder(startIndex);
  load(true);
}

export function jumpTo(queueIndex) {
  const pos = state.order.indexOf(queueIndex);
  if (pos < 0) return;
  state.pos = pos;
  load(true);
}

export function toggle() {
  if (!current()) return;
  if (audio.paused) audio.play().catch(() => {});
  else audio.pause();
}

export function next(auto = false) {
  if (!current()) return;
  if (state.pos < state.order.length - 1) {
    state.pos += 1;
  } else if (state.repeat === 'all') {
    if (state.shuffle) state.order = shuffled(state.order);
    state.pos = 0;
  } else {
    if (auto) {
      audio.pause();
      audio.currentTime = 0;
      emit('state');
    }
    return;
  }
  load(true);
}

export function prev() {
  if (!current()) return;
  if (audio.currentTime > 3 || state.pos === 0) {
    audio.currentTime = 0;
    return;
  }
  state.pos -= 1;
  load(true);
}

export function seek(fraction) {
  const { duration } = getState();
  if (current() && duration) audio.currentTime = Math.max(0, Math.min(1, fraction)) * duration;
}

export function setVolume(value) {
  audio.volume = Math.max(0, Math.min(1, value));
  audio.muted = value === 0;
  try { localStorage.setItem('musicapp.volume', String(audio.volume)); } catch { /* préférence non conservée */ }
  emit('volume');
}

export function toggleShuffle() {
  state.shuffle = !state.shuffle;
  if (current()) {
    const index = state.order[state.pos];
    buildOrder(index);
  }
  emit('mode');
}

export function cycleRepeat() {
  state.repeat = { off: 'all', all: 'one', one: 'off' }[state.repeat];
  emit('mode');
}

export function stop() {
  audio.pause();
  audio.removeAttribute('src');
  audio.load();
  state.queue = [];
  state.order = [];
  state.pos = -1;
  if ('mediaSession' in navigator) navigator.mediaSession.metadata = null;
  emit('track');
}

// ---------- Media Session API (touches multimédia, écran de verrouillage) ----------
function updateMediaSession(track) {
  if (!('mediaSession' in navigator)) return;
  const artwork = track.album?.cover_url ? [{ src: track.album.cover_url, sizes: '600x600', type: 'image/jpeg' }] : [];
  navigator.mediaSession.metadata = new MediaMetadata({
    title: track.title,
    artist: track.artist?.name || '',
    album: track.album?.title || '',
    artwork,
  });
}

if ('mediaSession' in navigator) {
  const handlers = {
    play: () => audio.play().catch(() => {}),
    pause: () => audio.pause(),
    previoustrack: () => prev(),
    nexttrack: () => next(),
    seekto: (d) => { if (d.seekTime !== undefined) audio.currentTime = d.seekTime; },
  };
  for (const [action, fn] of Object.entries(handlers)) {
    try { navigator.mediaSession.setActionHandler(action, fn); } catch { /* action non supportée */ }
  }
}

// ---------- Événements audio ----------
audio.addEventListener('timeupdate', () => {
  const delta = audio.currentTime - state.lastTime;
  if (delta > 0 && delta < 2) state.listened += delta;   // un saut dans le morceau ne compte pas
  state.lastTime = audio.currentTime;
  const track = current();
  // Titre plus court que 30 s (ex. extraits FMA de 30 s) : compté quand il est écouté presque en entier
  const threshold = Number.isFinite(audio.duration) ? Math.min(PLAY_COUNT_AFTER_S, audio.duration - 1) : PLAY_COUNT_AFTER_S;
  if (track && !state.counted && state.listened >= threshold) {
    state.counted = true;   // une seule fois par lecture
    api(`/tracks/${track.id}/play`, { method: 'POST' }).catch(() => {});
  }
  emit('time');
});
audio.addEventListener('seeked', () => { state.lastTime = audio.currentTime; });
audio.addEventListener('play', () => emit('state'));
audio.addEventListener('pause', () => emit('state'));
audio.addEventListener('loadedmetadata', () => emit('time'));
audio.addEventListener('ended', () => {
  if (state.repeat === 'one') {
    state.listened = 0;
    state.counted = false;
    audio.currentTime = 0;
    audio.play().catch(() => {});
  } else {
    next(true);
  }
});
audio.addEventListener('error', async () => {
  // Session expirée pendant l'écoute : on renouvelle puis on reprend au même endroit
  const track = current();
  if (!track || state.authRetried || !audio.getAttribute('src')) return;
  state.authRetried = true;
  const position = state.lastTime;
  if (await refreshSession()) {
    audio.src = `/api/stream/${track.id}`;
    audio.addEventListener('loadedmetadata', () => { audio.currentTime = position; }, { once: true });
    audio.play().catch(() => {});
  }
});

try {
  const saved = parseFloat(localStorage.getItem('musicapp.volume'));
  if (!Number.isNaN(saved)) audio.volume = saved;
} catch { /* pas de préférence */ }
