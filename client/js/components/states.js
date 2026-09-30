// États de chaque liste : chargement, vide (« No track found », écran 13), erreur.
import { h } from '../dom.js';

const BLANK_ROWS = 7;   // l'écran « Aucun titre » garde les lignes vides du tableau

export function loadingState(list) {
  list.replaceChildren(h('li', { class: 'state-row state-row--small' }, 'Loading…'));
}

export function emptyState(list, text = 'No track found', { blankRows = true } = {}) {
  const rows = [h('li', { class: 'state-row' }, text)];
  if (blankRows) for (let i = 0; i < BLANK_ROWS; i++) rows.push(h('li', { class: 'state-row state-row--blank', 'aria-hidden': 'true' }));
  list.replaceChildren(...rows);
}

export function errorState(list, retry, text = 'Something went wrong.') {
  list.replaceChildren(h('li', { class: 'state-row state-row--small' },
    text,
    retry ? h('button', { type: 'button', class: 'btn btn--small', onclick: retry }, 'Retry') : null,
  ));
}

/** Charge une liste : affiche le chargement, puis les lignes, l'état vide ou l'erreur. */
export async function loadList(list, fetcher, renderRow, emptyText, options = {}) {
  loadingState(list);
  try {
    const items = await fetcher();
    if (!items.length) emptyState(list, emptyText, options);
    else list.replaceChildren(...items.map((item, i) => renderRow(item, i, items)));
    return items;
  } catch {
    errorState(list, () => loadList(list, fetcher, renderRow, emptyText, options));
    return null;
  }
}
