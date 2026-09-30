// 01 · Connexion (+ liens « Sign up as artist » et « Forgot password ? »)
import { authMemo, homeFor, login } from '../auth.js';
import { clearErrors, field, showFieldErrors } from '../components/form.js';
import { h } from '../dom.js';
import { navigate } from '../router.js';

export function loginView() {
  const fields = {
    login: field({ label: 'Username', name: 'login', autocomplete: 'username' }),
    password: field({ label: 'Password', name: 'password', type: 'password', autocomplete: 'current-password' }),
  };
  const formError = h('p', { class: 'form-error', role: 'alert' });
  const submit = h('button', { type: 'submit', class: 'btn btn--auth' }, 'Log in');

  const form = h('form', { class: 'card', novalidate: true },
    h('h1', { class: 'card__title' }, 'Welcome !'),
    fields.login.el,
    fields.password.el,
    formError,
    h('div', { class: 'card__actions' }, submit),
  );

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(fields, formError);
    if (!fields.login.input.value.trim() || !fields.password.input.value) {
      formError.textContent = 'Enter your username and password.';
      return;
    }
    submit.disabled = true;
    try {
      const user = await login(fields.login.input.value.trim(), fields.password.input.value);
      navigate(homeFor(user.role), { replace: true });
    } catch (err) {
      // Codes explicites de l'API -> bon écran
      if (err.code === 'EMAIL_NOT_VERIFIED') navigate('/not-verified');
      else if (err.code === 'ARTIST_PENDING') navigate('/artist-pending');
      else if (err.code === 'ARTIST_REJECTED') {
        authMemo.set('rejectionReason', err.details.reason || '');
        navigate('/artist-rejected');
      } else showFieldErrors(fields, err, formError);
    } finally {
      submit.disabled = false;
    }
  });

  return h('div', { class: 'auth-page' },
    form,
    h('p', { class: 'auth-footer' }, 'Do not have an account ? ', h('a', { class: 'link', href: '#/register' }, 'Sign up')),
    h('p', { class: 'auth-footer' }, 'Are you an artist ? ', h('a', { class: 'link', href: '#/register-artist' }, 'Sign up as artist')),
    h('p', { class: 'auth-footer' }, h('a', { class: 'link', href: '#/forgot-password' }, 'Forgot password ?')),
  );
}
