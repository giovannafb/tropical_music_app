// Champs de formulaire. L'œil ne sert qu'à révéler ce qu'on est EN TRAIN de taper
// (le mot de passe actuel est haché côté serveur et ne peut jamais être affiché).
import { h, icon, iconButton } from '../dom.js';

let uid = 0;

export function field({ label, type = 'text', name, autocomplete, required = true, multiline = false, maxlength, value, eye = false }) {
  const id = `f${++uid}`;
  const input = multiline
    ? h('textarea', { class: 'field__input', id, name, required, maxlength })
    : h('input', { class: 'field__input', id, name, type, autocomplete, required, maxlength });
  if (value !== undefined) input.value = value;
  const error = h('p', { class: 'field__error', id: `${id}-err`, 'aria-live': 'polite' });
  input.setAttribute('aria-describedby', `${id}-err`);
  const control = h('div', { class: 'field__control' }, input);
  if (eye) {
    const toggle = iconButton('eye', 'Show password', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.replaceChildren(icon(show ? 'eye-off' : 'eye'));
      toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    }, { class: 'icon-btn field__eye' });
    control.append(toggle);
  }
  const el = h('div', { class: 'field' }, h('label', { class: 'field__label', for: id }, label), control, error);
  return { el, input, error };
}

/** Affiche les erreurs renvoyées par l'API (422 VALIDATION_ERROR) sous les bons champs. */
export function showFieldErrors(fields, err, formError) {
  Object.values(fields).forEach((f) => { f.error.textContent = ''; });
  if (formError) formError.textContent = '';
  const byField = err?.details?.fields;
  if (err?.code === 'VALIDATION_ERROR' && byField) {
    for (const [name, message] of Object.entries(byField)) {
      const key = Object.keys(fields).find((k) => fields[k].input.name === name);
      if (key) fields[key].error.textContent = message.replace(/^Value error, /, '');
      else if (formError) formError.textContent = message;
    }
    return;
  }
  if (formError) formError.textContent = err?.message || 'Something went wrong. Please try again.';
}

export function clearErrors(fields, formError) {
  Object.values(fields).forEach((f) => { f.error.textContent = ''; });
  if (formError) formError.textContent = '';
}
