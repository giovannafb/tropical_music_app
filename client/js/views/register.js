// 02 · Inscription (bouton renommé « Sign up ») et inscription artiste (page distincte :
// + nom d'artiste et bio).
import { api } from '../api.js';
import { authMemo } from '../auth.js';
import { clearErrors, field, showFieldErrors } from '../components/form.js';
import { h } from '../dom.js';
import { navigate } from '../router.js';

const PASSWORD_MIN = 8;

function registerForm({ artist }) {
  const fields = {
    username: field({ label: 'Username', name: 'username', autocomplete: 'username', maxlength: 50 }),
    email: field({ label: 'Email adress', name: 'email', type: 'email', autocomplete: 'email', maxlength: 255 }),
  };
  if (artist) {
    fields.artistName = field({ label: 'Artist name', name: 'artist_name', maxlength: 100 });
    fields.bio = field({ label: 'Biography', name: 'bio', multiline: true, maxlength: 5000 });
  }
  fields.password = field({ label: 'Password', name: 'password', type: 'password', autocomplete: 'new-password' });
  fields.confirm = field({ label: 'Confirm password', name: 'confirm', type: 'password', autocomplete: 'new-password' });

  const formError = h('p', { class: 'form-error', role: 'alert' });
  const submit = h('button', { type: 'submit', class: 'btn btn--auth' }, 'Sign up');
  const form = h('form', { class: 'card', novalidate: true },
    h('h1', { class: 'card__title' }, 'Welcome !'),
    Object.values(fields).map((f) => f.el),
    formError,
    h('div', { class: 'card__actions' }, submit),
  );

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(fields, formError);
    const v = (k) => fields[k].input.value;
    let ok = true;
    const need = (k, message) => { fields[k].error.textContent = message; ok = false; };
    if (v('username').trim().length < 3) need('username', 'At least 3 characters');
    if (!fields.email.input.checkValidity() || !v('email')) need('email', 'Enter a valid email address');
    if (artist && !v('artistName').trim()) need('artistName', 'Enter your artist name');
    if (artist && !v('bio').trim()) need('bio', 'Tell us about you');
    if (v('password').length < PASSWORD_MIN) need('password', `At least ${PASSWORD_MIN} characters`);
    if (v('confirm') !== v('password')) need('confirm', 'Passwords do not match');
    if (!ok) return;

    const body = { username: v('username').trim(), email: v('email').trim(), password: v('password') };
    if (artist) Object.assign(body, { artist_name: v('artistName').trim(), bio: v('bio').trim() });
    submit.disabled = true;
    try {
      const res = await api(artist ? '/auth/register-artist' : '/auth/register', { method: 'POST', json: body });
      authMemo.set('pendingEmail', res.email);
      navigate('/verify-email');
    } catch (err) {
      if (err.code === 'USERNAME_TAKEN') fields.username.error.textContent = err.message;
      else if (err.code === 'EMAIL_TAKEN') fields.email.error.textContent = err.message;
      else showFieldErrors(fields, err, formError);
    } finally {
      submit.disabled = false;
    }
  });

  return h('div', { class: 'auth-page' },
    form,
    h('p', { class: 'auth-footer' }, 'Already have an account ? ', h('a', { class: 'link', href: '#/login' }, 'Log in')),
  );
}

export const registerView = () => registerForm({ artist: false });
export const registerArtistView = () => registerForm({ artist: true });
