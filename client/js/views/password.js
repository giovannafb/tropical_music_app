// Écrans ajoutés : mot de passe oublié et réinitialisation (lien reçu par email).
import { api } from '../api.js';
import { clearErrors, field, showFieldErrors } from '../components/form.js';
import { h } from '../dom.js';

const PASSWORD_MIN = 8;

export function forgotPasswordView() {
  const fields = { email: field({ label: 'Email adress', name: 'email', type: 'email', autocomplete: 'email' }) };
  const formError = h('p', { class: 'form-error', role: 'alert' });
  const info = h('p', { class: 'form-info', 'aria-live': 'polite' });
  const submit = h('button', { type: 'submit', class: 'btn btn--auth' }, 'Send link');
  const form = h('form', { class: 'card', novalidate: true },
    h('h1', { class: 'card__title' }, 'Forgot password ?'),
    fields.email.el, formError, info,
    h('div', { class: 'card__actions' }, submit),
  );
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(fields, formError);
    info.textContent = '';
    if (!fields.email.input.value || !fields.email.input.checkValidity()) {
      fields.email.error.textContent = 'Enter a valid email address';
      return;
    }
    submit.disabled = true;
    try {
      await api('/auth/forgot-password', { method: 'POST', json: { email: fields.email.input.value.trim() } });
      info.textContent = 'If an account exists with this address, we sent you a link to reset your password.';
    } catch (err) {
      showFieldErrors(fields, err, formError);
    } finally {
      submit.disabled = false;
    }
  });
  return h('div', { class: 'auth-page' },
    form,
    h('p', { class: 'auth-footer' }, h('a', { class: 'link', href: '#/login' }, 'Back to login')),
  );
}

export function resetPasswordView({ query }) {
  const fields = {
    password: field({ label: 'New password', name: 'password', type: 'password', autocomplete: 'new-password', eye: true }),
    confirm: field({ label: 'Confirm new password', name: 'confirm', type: 'password', autocomplete: 'new-password', eye: true }),
  };
  const formError = h('p', { class: 'form-error', role: 'alert' });
  const info = h('p', { class: 'form-info', 'aria-live': 'polite' });
  const submit = h('button', { type: 'submit', class: 'btn btn--auth' }, 'Confirm');
  const form = h('form', { class: 'card', novalidate: true },
    h('h1', { class: 'card__title' }, 'New password'),
    fields.password.el, fields.confirm.el, formError, info,
    h('div', { class: 'card__actions' }, submit),
  );
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(fields, formError);
    const password = fields.password.input.value;
    if (password.length < PASSWORD_MIN) { fields.password.error.textContent = `At least ${PASSWORD_MIN} characters`; return; }
    if (fields.confirm.input.value !== password) { fields.confirm.error.textContent = 'Passwords do not match'; return; }
    submit.disabled = true;
    try {
      await api('/auth/reset-password', { method: 'POST', json: { token: query.get('token') || '', password } });
      form.replaceChildren(
        h('h1', { class: 'card__title' }, 'Password changed !'),
        h('div', { class: 'card__actions' }, h('a', { class: 'btn btn--auth', href: '#/login' }, 'Log in')),
      );
    } catch (err) {
      showFieldErrors(fields, err, formError);
      submit.disabled = false;
    }
  });
  return h('div', { class: 'auth-page' }, form);
}
