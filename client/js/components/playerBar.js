// Barre de lecture (Group 32) + panneau du bouton ≡ (file de lecture, volume, aléatoire, répétition).
import { coverImg, h, icon, iconButton } from '../dom.js';
import { trackLength } from '../format.js';
import * as player from '../player.js';

export function playerBar() {
  let cover = h('span');
  const title = h('div', { class: 'player__title cell' });
  const artist = h('div', { class: 'player__artist cell' });

  const playBtn = iconButton('play-circle', 'Play', () => player.toggle());
  const prevBtn = iconButton('prev', 'Previous', () => player.prev());
  const nextBtn = iconButton('next', 'Next', () => player.next());

  const elapsed = h('span', { class: 'player__time' }, '0:00');
  const total = h('span', { class: 'player__time' }, '0:00');
  const progress = h('input', { type: 'range', class: 'range', min: '0', max: '1000', value: '0', 'aria-label': 'Position in the track' });
  let dragging = false;
  progress.addEventListener('input', () => { dragging = true; setFill(progress); });
  progress.addEventListener('change', () => { dragging = false; player.seek(progress.value / 1000); });

  // ---------- Panneau ≡ ----------
  const shuffleBtn = iconButton('shuffle', 'Shuffle', () => player.toggleShuffle());
  const repeatBtn = iconButton('repeat', 'Repeat', () => player.cycleRepeat());
  const repeatLabel = h('span');
  const muteBtn = iconButton('volume', 'Mute', () => {
    const { volume } = player.getState();
    if (volume > 0) { lastVolume = volume; player.setVolume(0); } else player.setVolume(lastVolume || 1);
  });
  let lastVolume = 1;
  const volume = h('input', { type: 'range', class: 'range', min: '0', max: '100', 'aria-label': 'Volume' });
  volume.addEventListener('input', () => { player.setVolume(volume.value / 100); setFill(volume); });
  const queueList = h('div', { class: 'player-panel__queue', role: 'list' });
  const panel = h('div', { class: 'player-panel', id: 'player-panel', hidden: true },
    h('div', { class: 'player-panel__row' }, shuffleBtn, repeatBtn, repeatLabel),
    h('div', { class: 'player-panel__row' }, muteBtn, volume),
    h('p', { class: 'player-panel__title' }, 'Queue'),
    queueList,
  );
  const menuBtn = iconButton('menu', 'Queue and settings', () => {
    panel.hidden = !panel.hidden;
    menuBtn.setAttribute('aria-expanded', String(!panel.hidden));
    if (!panel.hidden) renderQueue();
  }, { class: 'icon-btn player__menu', 'aria-controls': 'player-panel', 'aria-expanded': 'false' });

  const el = h('section', { class: 'player', 'aria-label': 'Player' },
    h('div', { class: 'player__now' }, cover, h('div', { class: 'player__meta' }, title, artist)),
    h('div', { class: 'player__center' },
      h('div', { class: 'player__controls' }, prevBtn, playBtn, nextBtn),
      h('div', { class: 'player__progress' }, elapsed, progress, total),
    ),
    menuBtn,
    panel,
  );

  function setFill(range) {
    range.style.setProperty('--p', `${(range.value / range.max) * 100}%`);
  }

  function renderTrack() {
    const track = player.current();
    const newCover = coverImg(track?.album.cover_small_url, 'player__cover');
    cover.replaceWith(newCover);
    cover = newCover;
    title.textContent = track ? track.title : '';
    artist.textContent = track ? track.artist.name : '';
    for (const b of [playBtn, prevBtn, nextBtn, progress]) b.disabled = !track;
    renderTime();
    renderState();
    if (!panel.hidden) renderQueue();
  }

  function renderState() {
    const { paused } = player.getState();
    playBtn.replaceChildren(icon(paused ? 'play-circle' : 'pause-circle'));
    playBtn.setAttribute('aria-label', paused ? 'Play' : 'Pause');
    playBtn.title = paused ? 'Play' : 'Pause';
  }

  function renderTime() {
    const { currentTime, duration } = player.getState();
    elapsed.textContent = trackLength(currentTime);
    total.textContent = trackLength(duration);
    if (!dragging) {
      progress.value = duration ? Math.round((currentTime / duration) * 1000) : 0;
      setFill(progress);
    }
  }

  function renderMode() {
    const { shuffle, repeat } = player.getState();
    shuffleBtn.setAttribute('aria-pressed', String(shuffle));
    repeatBtn.setAttribute('aria-pressed', String(repeat !== 'off'));
    repeatBtn.replaceChildren(icon(repeat === 'one' ? 'repeat-one' : 'repeat'));
    repeatLabel.textContent = { off: 'Repeat off', all: 'Repeat all', one: 'Repeat one' }[repeat];
    if (!panel.hidden) renderQueue();
  }

  function renderVolume() {
    const { volume: v } = player.getState();
    volume.value = Math.round(v * 100);
    setFill(volume);
    muteBtn.replaceChildren(icon(v === 0 ? 'volume-off' : 'volume'));
  }

  function renderQueue() {
    const { queue, currentIndex } = player.getState();
    if (!queue.length) {
      queueList.replaceChildren(h('p', { class: 'form-info' }, 'The queue is empty.'));
      return;
    }
    queueList.replaceChildren(...queue.map((t, i) => h('button', {
      type: 'button', role: 'listitem', class: `queue-item${i === currentIndex ? ' is-current' : ''}`,
      onclick: () => player.jumpTo(i),
    }, coverImg(t.album.cover_small_url, 'queue-item__cover'), h('span', { class: 'cell' }, `${t.title} — ${t.artist.name}`), trackLength(t.duration_s))));
  }

  const unsubscribe = player.subscribe((type) => {
    if (type === 'track') renderTrack();
    else if (type === 'state') renderState();
    else if (type === 'time') renderTime();
    else if (type === 'mode') renderMode();
    else if (type === 'volume') renderVolume();
  });
  renderTrack();
  renderMode();
  renderVolume();

  // Barre d'espace : pause / reprise, où que soit le focus (sauf pendant une saisie de texte).
  // Sans cela, Espace « recliquerait » le bouton qui a le focus (ex. le ▷ d'un titre -> relance au début).
  function onSpace(e) {
    if (e.code !== 'Space' || e.ctrlKey || e.altKey || e.metaKey) return;
    if (!player.current() || isTyping(e.target)) return;
    e.preventDefault();   // ni clic sur le bouton qui a le focus, ni défilement de la page
    if (e.type === 'keydown' && !e.repeat) player.toggle();
  }
  window.addEventListener('keydown', onSpace, true);
  window.addEventListener('keyup', onSpace, true);

  return {
    el,
    destroy() {
      unsubscribe();
      window.removeEventListener('keydown', onSpace, true);
      window.removeEventListener('keyup', onSpace, true);
    },
  };
}

const NON_TEXT_INPUTS = new Set(['button', 'checkbox', 'radio', 'range', 'submit', 'reset', 'file', 'color', 'image']);

function isTyping(el) {
  if (!(el instanceof HTMLElement)) return false;
  if (el.isContentEditable || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return true;
  return el.tagName === 'INPUT' && !NON_TEXT_INPUTS.has(el.type);
}
