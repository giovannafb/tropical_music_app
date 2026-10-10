// 14 · User · Profile et 22 · Artiste · Profile (+ admin) :
// changer le username (crayon), changer le mot de passe (nouveau / confirmation / ancien),
// biographie pour l'artiste, et bouton « Log out ».
// Le champ « Password ****** » du prototype n'est pas repris : le mot de passe actuel est haché.
import { api } from '../api.js';
import { getUser, logout, setUser } from '../auth.js';
import { clearErrors, field, showFieldErrors } from '../components/form.js';
import { errorMessage, h, icon, toast } from '../dom.js';
import * as player from '../player.js';
import { navigate } from '../router.js';

const PASSWORD_MIN = 8;

function usernameBlock() {
  const user = getUser();
  const nameText = h('span', { class: 'profile__name' }, user.username);
  const input = h('input', { class: 'profile__name-input', value: user.username, maxlength: 50, 'aria-label': 'New username', hidden: true });
  const error = h('p', { class: 'form-error', role: 'alert' });
  const action = h('button', { type: 'button', class: 'profile__change' }, icon('pen'), h('span', {}, 'Change username'));
  let editing = false;

  function setEditing(on) {
    editing = on;
    nameText.hidden = on;
    input.hidden = !on;
    action.lastChild.textContent = on ? 'Save username' : 'Change username';
    if (on) { input.value = getUser().username; input.focus(); input.select(); }
  }

  async function save() {
    error.textContent = '';
    const value = input.value.trim();
    if (value.length < 3) { error.textContent = 'At least 3 characters'; return; }
    try {
      const me = await api('/me', { method: 'PATCH', json: { username: value } });
      setUser(me);   // la coque met à jour « username - Role »
      nameText.textContent = me.username;
      setEditing(false);
      toast('Username changed');
    } catch (err) {
      error.textContent = err.details?.fields?.username?.replace(/^Value error, /, '') || errorMessage(err);
    }
  }

  action.addEventListener('click', () => (editing ? save() : setEditing(true)));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') save();
    if (e.key === 'Escape') { e.preventDefault(); setEditing(false); }
  });
  return h('div', {}, h('h1', { class: 'profile__title' }, nameText, input, action), error);
}

function passwordBlock() {
  const fields = {
    new: field({ label: 'New password', name: 'new_password', type: 'password', autocomplete: 'new-password', eye: true }),
    confirm: field({ label: 'Confirm new password', name: 'confirm', type: 'password', autocomplete: 'new-password', eye: true }),
    old: field({ label: 'Old password', name: 'old_password', type: 'password', autocomplete: 'current-password', eye: true }),
  };
  const formError = h('p', { class: 'form-error', role: 'alert' });
  const submit = h('button', { type: 'submit', class: 'btn btn--secondary' }, 'Confirm Password');
  const form = h('form', { class: 'profile__form', novalidate: true },
    h('h2', { class: 'profile__heading' }, 'Change your password'),
    fields.new.el, fields.confirm.el, fields.old.el, formError, submit,
  );
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(fields, formError);
    const next = fields.new.input.value;
    if (next.length < PASSWORD_MIN) { fields.new.error.textContent = `At least ${PASSWORD_MIN} characters`; return; }
    if (fields.confirm.input.value !== next) { fields.confirm.error.textContent = 'Passwords do not match'; return; }
    if (!fields.old.input.value) { fields.old.error.textContent = 'Enter your old password'; return; }
    submit.disabled = true;
    try {
      await api('/me/password', { method: 'POST', json: { old_password: fields.old.input.value, new_password: next } });
      form.reset();
      toast('Password changed');
    } catch (err) {
      if (err.code === 'WRONG_PASSWORD') fields.old.error.textContent = err.message;
      else showFieldErrors(fields, err, formError);
    } finally {
      submit.disabled = false;
    }
  });
  return form;
}

function biographyBlock() {
  const artist = getUser().artist;
  const area = h('textarea', { class: 'profile__bio', 'aria-label': 'Biography', maxlength: 5000, readonly: true });
  area.value = artist.bio;
  const error = h('p', { class: 'form-error', role: 'alert' });
  const pen = h('button', { type: 'button', class: 'icon-btn profile__bio-pen', 'aria-label': 'Edit biography', title: 'Edit biography' }, icon('pen'));
  pen.addEventListener('click', async () => {
    error.textContent = '';
    if (area.readOnly) {
      area.readOnly = false;
      area.focus();
      pen.setAttribute('aria-label', 'Save biography');
      pen.title = 'Save biography';
      pen.classList.add('is-active');
      return;
    }
    const bio = area.value.trim();
    if (!bio) { error.textContent = 'The biography cannot be empty.'; return; }
    try {
      const me = await api('/me/artist', { method: 'PATCH', json: { bio } });
      setUser(me);
      area.readOnly = true;
      pen.setAttribute('aria-label', 'Edit biography');
      pen.title = 'Edit biography';
      pen.classList.remove('is-active');
      toast('Biography saved');
    } catch (err) {
      error.textContent = errorMessage(err);
    }
  });
  return h('div', {},
    h('h2', { class: 'profile__heading' }, 'Change your biography'),
    h('div', { class: 'profile__bio-box' }, area, pen),
    error,
  );
}

export function profileView() {
  const user = getUser();
  const logoutBtn = h('button', {
    type: 'button', class: 'btn btn--secondary',
    onclick: async () => {
      player.stop();
      await logout();
      navigate('/login', { replace: true });
    },
  }, 'Log out');
  return h('section', { class: 'profile', 'aria-label': 'Profile' },
    usernameBlock(),
    passwordBlock(),
    user.role === 'artist' && user.artist ? biographyBlock() : null,
    h('div', { class: 'profile__logout' }, logoutBtn),
  );
}
