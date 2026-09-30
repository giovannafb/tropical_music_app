// Formats d'affichage repris du Figma : « 2:20 » pour un titre, « 34 min 30 » pour un album / une playlist.

export function trackLength(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function totalLength(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')}`;
}

export function trackCount(n) {
  return `${n} track${n === 1 ? '' : 's'}`;
}

export function releaseDate(iso) {
  if (!iso) return '—';
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}
