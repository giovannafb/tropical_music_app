// Éléments communs aux écrans « create playlist » et « New album » :
// sélecteur de cover (349×349 + « + »), champ titre, bloc « Add new tracks », lignes de piste.
import { coverImg, h, icon, iconButton } from '../dom.js';
import { trackLength } from '../format.js';

const IMAGE_TYPES = 'image/jpeg,image/png,image/webp';

export function coverPicker({ label, url, onFile }) {
  let image = coverImg(url, 'cover-picker__image', label);
  const input = h('input', { type: 'file', accept: IMAGE_TYPES, class: 'visually-hidden', tabindex: '-1' });
  const add = iconButton('plus', label, () => input.click(), { class: 'icon-btn cover-picker__add' });
  const el = h('div', { class: 'cover-picker' }, image, add, h('span', { class: 'cover-picker__label' }, label), input);
  input.addEventListener('change', () => {
    const file = input.files[0];
    input.value = '';
    if (file) onFile(file);
  });
  return {
    el,
    setUrl(src) {
      const next = coverImg(src, 'cover-picker__image', label);
      image.replaceWith(next);
      image = next;
    },
  };
}

export function titleField(label, value = '') {
  const input = h('input', { class: 'title-field__input', id: 'title-field', maxlength: 200, value, autocomplete: 'off' });
  return { el: h('div', { class: 'title-field' }, h('label', { class: 'title-field__label', for: 'title-field' }, label), input), input };
}

export function tracksBlock(onAdd) {
  const list = h('ul', { class: 'list' });
  const el = h('div', { class: 'tracks-block' },
    h('button', { type: 'button', class: 'tracks-block__add', onclick: onAdd }, icon('plus'), h('span', {}, 'Add new tracks')),
    list,
  );
  return { el, list };
}

/** Ligne de piste en édition (composant 10) : cover, titre, artiste, durée, action (crayon ou retirer). */
export function editRow({ coverUrl, title, artist, duration, action }) {
  const titleCell = h('span', { class: 'edit-row__title' }, h('span', { class: 'cell' }, title));
  const row = h('li', { class: 'edit-row' },
    coverImg(coverUrl, 'edit-row__cover'),
    titleCell,
    h('span', { class: 'cell' }, artist),
    h('span', { class: 'edit-row__length' }, duration === null ? '' : trackLength(duration)),
    action || h('span'),
  );
  return { row, titleCell };
}
