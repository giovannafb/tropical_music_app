// Blocs message : 03 · Email de vérification, 03 · Compte non vérifié,
// + écrans ajoutés : lien de vérification, compte artiste en attente, compte artiste refusé.
import { api } from '../api.js';
import { authMemo } from '../auth.js';
import { errorMessage, h } from '../dom.js';
import { navigate } from '../router.js';

function messagePage(...content) {
  return h('div', { class: 'auth-page' }, h('section', { class: 'message-block' }, ...content));
}

function toLogin(label) {
  return h('button', { type: 'button', class: 'btn btn--auth btn--wide', onclick: () => navigate('/login') }, label);
}

// Après l'inscription : « Click on the link we've sent you… » + renvoi du lien
export function verifyEmailView() {
  const info = h('p', { class: 'message-block__small', 'aria-live': 'polite' });
  const resend = h('button', {
    type: 'button', class: 'link',
    onclick: async () => {
      const email = authMemo.get('pendingEmail');
      if (!email) { info.textContent = 'Please sign up again.'; return; }
      resend.disabled = true;
      try {
        await api('/auth/resend-verification', { method: 'POST', json: { email } });
        info.textContent = 'A new email has been sent.';
      } catch (err) {
        info.textContent = errorMessage(err);
      } finally {
        resend.disabled = false;
      }
    },
  }, 'send it again.');
  return messagePage(
    h('p', { class: 'message-block__text' }, 'Click on the link we’ve sent you by email to verify your account and be able to log in'),
    h('p', { class: 'message-block__small' }, 'Not seeing the email ? ', resend),
    info,
    toLogin('Done ? log in'),
  );
}

export function notVerifiedView() {
  return messagePage(
    h('h1', { class: 'message-block__title' }, 'Sorry ! Account not verified'),
    h('p', { class: 'message-block__text' }, 'Click on the link we’ve sent you by email to verify your account'),
    toLogin('Back to login'),
  );
}

// Lien reçu par email : #/verify?token=…
export function verifyLinkView({ query }) {
  const title = h('h1', { class: 'message-block__title' }, 'Verifying your account…');
  const text = h('p', { class: 'message-block__text' });
  const page = messagePage(title, text, toLogin('Log in'));
  api(`/auth/verify?token=${encodeURIComponent(query.get('token') || '')}`)
    .then(() => {
      title.textContent = 'Your account is verified !';
      text.textContent = 'You can now log in.';
    })
    .catch((err) => {
      title.textContent = 'Sorry !';
      text.textContent = errorMessage(err);
    });
  return page;
}

export function artistPendingView() {
  return messagePage(
    h('h1', { class: 'message-block__title' }, 'Account waiting for validation'),
    h('p', { class: 'message-block__text' }, 'Your artist account must be validated by an administrator. You will receive an email once it is done.'),
    toLogin('Back to login'),
  );
}

export function artistRejectedView() {
  const reason = authMemo.get('rejectionReason');
  return messagePage(
    h('h1', { class: 'message-block__title' }, 'Sorry ! Artist account refused'),
    h('p', { class: 'message-block__text' }, reason ? `Reason: ${reason}` : 'Your artist account was refused.'),
    toLogin('Back to login'),
  );
}
