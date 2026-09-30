// Pop-ups : élément natif <dialog> + showModal() (fond grisé, fermeture avec Échap, accessibilité).
// La fermeture est traitée de façon synchrone (croix, clic sur le fond, Échap via « cancel »)
// pour ne pas dépendre du moment où le navigateur émet l'événement « close ».
import { h, iconButton } from '../dom.js';

let current = null;   // { dialog, finish }

/** Crée un <dialog> modal ; finish(fromUser) le ferme une seule fois. */
function createDialog(className, label, onFinish) {
  const dialog = h('dialog', { class: className, 'aria-label': label, tabindex: '-1' });
  let done = false;
  const finish = (fromUser) => {
    if (done) return;
    done = true;
    if (current?.dialog === dialog) current = null;
    if (dialog.open) dialog.close();
    dialog.remove();
    onFinish(fromUser);
  };
  dialog.addEventListener('cancel', (e) => { e.preventDefault(); finish(true); });   // touche Échap
  dialog.addEventListener('close', () => finish(true));                             // filet de sécurité
  return { dialog, finish };
}

/** Ouvre un pop-up ; onClose est appelé quand l'utilisateur le ferme (Échap, croix, fond). */
export function openModal({ label, small = false, onClose } = {}) {
  closeModal();
  const body = h('div', { class: 'modal__body' });
  const { dialog, finish } = createDialog(`modal${small ? ' modal--small' : ''}`, label, (fromUser) => {
    if (fromUser && onClose) onClose();
  });
  const close = iconButton('close', 'Close', () => finish(true));
  close.classList.add('modal__close');
  dialog.append(h('div', { class: 'modal__inner' }, close, body));
  dialog.addEventListener('click', (e) => { if (e.target === dialog) finish(true); });   // clic sur le fond
  document.body.append(dialog);
  dialog.showModal();
  dialog.focus();   // le focus est sur le pop-up lui-même (Échap et Tab restent disponibles)
  current = { dialog, finish };
  return { dialog, body, close: () => finish(true) };
}

/** Fermeture déclenchée par le code (changement de route) : sans rappel onClose. */
export function closeModal() {
  if (current) current.finish(false);
}

/** Petite fenêtre de confirmation (suppression…) ; résout true si confirmé. */
export function confirmDialog(message, confirmLabel = 'Delete') {
  return new Promise((resolve) => {
    let answer = false;
    const { dialog, finish } = createDialog('modal modal--small', 'Confirmation', () => resolve(answer));
    const yes = h('button', { type: 'button', class: 'btn btn--small', onclick: () => { answer = true; finish(true); } }, confirmLabel);
    const no = h('button', { type: 'button', class: 'btn btn--small btn--ghost', onclick: () => finish(true) }, 'Cancel');
    dialog.append(h('div', { class: 'modal__body' }, h('p', { class: 'modal__text' }, message), h('div', { class: 'modal__actions' }, yes, no)));
    document.body.append(dialog);
    dialog.showModal();
    no.focus();
  });
}
