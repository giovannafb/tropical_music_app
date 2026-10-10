// Espace admin (écran ajouté) : valider / refuser (avec motif) les artistes en attente.
import { api } from '../api.js';
import { openModal } from '../components/dialog.js';
import { field } from '../components/form.js';
import { emptyState, loadList } from '../components/states.js';
import { errorMessage, h, icon, toast } from '../dom.js';

export function adminArtistsView() {
  const list = h('ul', { class: 'list list--gradient', 'aria-label': 'Artists waiting for validation' });

  function removeRow(row) {
    row.remove();
    if (!list.children.length) emptyState(list, 'No artist waiting for validation', { blankRows: false });
  }

  function askReason(artist, row) {
    const modal = openModal({ label: 'Refuse artist', small: true });
    const reason = field({ label: 'Reason', name: 'reason', multiline: true, maxlength: 2000 });
    const confirm = h('button', { type: 'submit', class: 'btn btn--small' }, 'Refuse');
    const form = h('form', { novalidate: true },
      h('h2', { class: 'modal__title' }, `Refuse ${artist.name}`),
      reason.el,
      h('div', { class: 'modal__actions' }, confirm),
    );
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const value = reason.input.value.trim();
      if (!value) { reason.error.textContent = 'The reason is sent to the artist by email'; return; }
      confirm.disabled = true;
      try {
        await api(`/admin/artists/${artist.id}/reject`, { method: 'POST', json: { reason: value } });
        modal.close();
        removeRow(row);
        toast(`${artist.name} refused`);
      } catch (err) {
        reason.error.textContent = errorMessage(err);
        confirm.disabled = false;
      }
    });
    modal.body.append(form);
    reason.input.focus();
  }

  function renderRow(artist) {
    const approve = h('button', { type: 'button', class: 'btn btn--small' }, 'Approve');
    const reject = h('button', { type: 'button', class: 'btn btn--small btn--ghost' }, 'Refuse');
    const row = h('li', { class: 'review-row' },
      h('span', { class: 'avatar' }, icon('avatar')),
      h('div', { class: 'review-row__info' },
        h('p', { class: 'review-row__name' }, artist.name),
        h('p', { class: 'review-row__meta' }, `${artist.username} · ${artist.email}`),
        h('p', { class: 'review-row__bio' }, artist.bio),
      ),
      h('div', { class: 'review-row__actions' }, approve, reject),
    );
    approve.addEventListener('click', async () => {
      approve.disabled = true;
      try {
        await api(`/admin/artists/${artist.id}/approve`, { method: 'POST' });
        removeRow(row);
        toast(`${artist.name} approved`);
      } catch (err) {
        toast(errorMessage(err), 'error');
        approve.disabled = false;
      }
    });
    reject.addEventListener('click', () => askReason(artist, row));
    return row;
  }

  loadList(list, () => api('/admin/artists?status=pending'), renderRow, 'No artist waiting for validation', { blankRows: false });
  return h('section', { 'aria-label': 'Artists waiting for validation' },
    h('div', { class: 'table-header page-header' }, h('span', {}, 'Artists waiting for validation')),
    list,
  );
}
