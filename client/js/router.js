// Routage par hash (#/home, #/album/12…) avec garde selon le rôle.
// Les pop-ups ont leur propre URL : « retour » ferme le pop-up, et un lien peut être partagé.
import { getUser, homeFor } from './auth.js';
import { closeModal } from './components/dialog.js';

const routes = [];
let view = null;            // vue affichée sous les pop-ups : { raw, destroy }
let popupDepth = 0;         // nombre d'entrées d'historique ouvertes par des pop-ups
let popupFromApp = false;

/**
 * access : 'guest' (seulement déconnecté), 'public' (tout le monde), ou liste de rôles.
 * render(ctx) renvoie un élément ou { el, destroy } ; mount(el, ctx) place l'élément (coque ou pleine page).
 */
export function route(pattern, options) {
  const keys = [];
  const regex = new RegExp(`^${pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return '([^/]+)'; })}$`);
  routes.push({ regex, keys, ...options });
}

export function navigate(path, { replace = false } = {}) {
  const hash = `#${path}`;
  if (replace) location.replace(hash);
  else if (location.hash === hash) resolve();
  else location.hash = hash;
}

export function openPopup(path) {
  popupFromApp = true;
  navigate(path);
}

function parseHash() {
  const raw = decodeURI(location.hash.slice(1)) || '/';
  const [path, qs = ''] = raw.split('?');
  return { raw, path, query: new URLSearchParams(qs) };
}

function match(path) {
  for (const r of routes) {
    const m = r.regex.exec(path);
    if (m) return { route: r, params: Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])])) };
  }
  return null;
}

function allowed(route, user) {
  if (route.access === 'public') return true;
  if (route.access === 'guest') return !user;
  return Boolean(user) && route.access.includes(user.role);
}

async function renderView(found, query, raw) {
  if (view?.destroy) view.destroy();
  const ctx = { params: found.params, query, raw };
  const result = await found.route.render(ctx);
  const el = result instanceof Node ? result : result.el;
  found.route.mount(el, found.route);
  view = { raw, destroy: result instanceof Node ? null : result.destroy };
}

function closePopupFromUser() {
  if (popupDepth > 0) {
    const depth = popupDepth;
    popupDepth = 0;
    history.go(-depth);
  } else {
    navigate(view ? view.raw : homeFor(getUser()?.role), { replace: true });
  }
}

export async function resolve() {
  const { raw, path, query } = parseHash();
  const user = getUser();
  const found = match(path);
  const fallback = user ? homeFor(user.role) : '/login';

  if (!found) return navigate(fallback, { replace: true });
  if (!allowed(found.route, user)) {
    return navigate(found.route.access === 'guest' ? fallback : (user ? fallback : '/login'), { replace: true });
  }

  if (found.route.popup) {
    popupDepth = popupFromApp ? popupDepth + 1 : Math.max(popupDepth - 1, 0);
    popupFromApp = false;
    if (!view) {
      // Lien partagé ouvert directement : on affiche l'accueil du rôle sous le pop-up
      const home = match(homeFor(user.role));
      await renderView(home, new URLSearchParams(), homeFor(user.role));
      popupDepth = 0;
    }
    closeModal();
    found.route.render({ params: found.params, query, onClose: closePopupFromUser });
    return undefined;
  }

  popupFromApp = false;
  popupDepth = 0;
  closeModal();
  if (view && view.raw === raw) return undefined;   // retour depuis un pop-up : la vue est déjà là
  return renderView(found, query, raw);
}

/** Une vue met à jour sa propre URL (ex. #/search?q=…) sans être ré-affichée. */
export function updateViewUrl(path) {
  history.replaceState(null, '', `#${path}`);
  if (view) view.raw = path;
}

/** Recharge la vue quand un contenu change (suppression dans un pop-up…) ; renvoie la fonction de nettoyage. */
export function onContentChanged(fn) {
  window.addEventListener('musicapp:changed', fn);
  return () => window.removeEventListener('musicapp:changed', fn);
}

export function reset() {
  if (view?.destroy) view.destroy();
  view = null;
  popupDepth = 0;
}

export function start() {
  window.addEventListener('hashchange', () => resolve());
  return resolve();
}
